"""
TransLink Reliability Tracker - Phase 2 (Turso version, all bus routes)

Writes directly to a hosted libSQL (Turso) database instead of
committing files to git. This scales to the full Metro Vancouver bus
network (200+ routes) without hitting GitHub's file size limits or
fighting git push conflicts, since no data-carrying commits happen
anymore - the workflow just runs this script.

Requires:
    pip install requests libsql-client
"""

import json
import os
from datetime import datetime, timezone

import libsql_client
import requests
from google.transit import gtfs_realtime_pb2

API_KEY = os.environ["TRANSLINK_API_KEY"]
TRIP_UPDATES_URL = f"https://gtfsapi.translink.ca/v3/gtfsrealtime?apikey={API_KEY}"

TURSO_URL = os.environ["TURSO_DATABASE_URL"]
TURSO_TOKEN = os.environ["TURSO_AUTH_TOKEN"]

VEHICLE_POSITIONS_URL = f"https://gtfsapi.translink.ca/v3/gtfsposition?apikey={API_KEY}"

with open("bus_routes.json", encoding="utf-8") as f:
    BUS_ROUTES = json.load(f)  # route_id -> label, ALL Metro Vancouver bus routes


def fetch_feed(url: str) -> gtfs_realtime_pb2.FeedMessage:
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(response.content)
    return feed


def init_db(client: libsql_client.Client):
    client.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            captured_at TEXT NOT NULL,
            feed_timestamp INTEGER,
            route_id TEXT NOT NULL,
            route_label TEXT,
            trip_id TEXT NOT NULL,
            stop_id TEXT NOT NULL,
            stop_sequence INTEGER,
            delay_seconds INTEGER
        )
    """)
    client.execute("""
        CREATE TABLE IF NOT EXISTS vehicle_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            captured_at TEXT NOT NULL,
            feed_timestamp INTEGER,
            vehicle_id TEXT,
            route_id TEXT,
            route_label TEXT,
            trip_id TEXT,
            latitude REAL,
            longitude REAL,
            bearing REAL,
            speed REAL
        )
    """)


def poll_and_store():
    captured_at = datetime.now(timezone.utc).isoformat()
    print(f"[{captured_at}] Polling feeds for {len(BUS_ROUTES)} tracked bus routes...")

    trip_feed = fetch_feed(TRIP_UPDATES_URL)
    position_feed = fetch_feed(VEHICLE_POSITIONS_URL)

    client = libsql_client.create_client_sync(url=TURSO_URL, auth_token=TURSO_TOKEN)
    init_db(client)

    batch = []
    for entity in trip_feed.entity:
        if not entity.HasField("trip_update"):
            continue

        tu = entity.trip_update
        route_id = tu.trip.route_id

        if route_id not in BUS_ROUTES:
            continue  # skip SkyTrain/SeaBus/untracked routes

        route_label = BUS_ROUTES[route_id]

        for stu in tu.stop_time_update:
            delay_sec = None
            if stu.HasField("arrival") and stu.arrival.HasField("delay"):
                delay_sec = stu.arrival.delay
            elif stu.HasField("departure") and stu.departure.HasField("delay"):
                delay_sec = stu.departure.delay

            if delay_sec is None:
                continue

            batch.append(libsql_client.Statement(
                """
                INSERT INTO snapshots
                    (captured_at, feed_timestamp, route_id, route_label,
                     trip_id, stop_id, stop_sequence, delay_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    captured_at,
                    trip_feed.header.timestamp,
                    route_id,
                    route_label,
                    tu.trip.trip_id,
                    stu.stop_id,
                    stu.stop_sequence,
                    delay_sec,
                ],
            ))

    position_batch = []
    for entity in position_feed.entity:
        if not entity.HasField("vehicle"):
            continue

        v = entity.vehicle
        route_id = v.trip.route_id

        if route_id not in BUS_ROUTES:
            continue  # skip SkyTrain/SeaBus/untracked routes

        route_label = BUS_ROUTES[route_id]

        if not v.HasField("position"):
            continue

        position_batch.append(libsql_client.Statement(
            """
            INSERT INTO vehicle_positions
                (captured_at, feed_timestamp, vehicle_id, route_id,
                 route_label, trip_id, latitude, longitude, bearing, speed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                captured_at,
                position_feed.header.timestamp,
                v.vehicle.id if v.HasField("vehicle") else None,
                route_id,
                route_label,
                v.trip.trip_id,
                v.position.latitude,
                v.position.longitude,
                v.position.bearing if v.position.HasField("bearing") else None,
                v.position.speed if v.position.HasField("speed") else None,
            ],
        ))

    if batch:
        CHUNK = 500
        for i in range(0, len(batch), CHUNK):
            client.batch(batch[i:i + CHUNK])

    if position_batch:
        CHUNK = 500
        for i in range(0, len(position_batch), CHUNK):
            client.batch(position_batch[i:i + CHUNK])

    client.close()
    print(f"Inserted {len(batch)} trip-update rows and "
          f"{len(position_batch)} vehicle-position rows.")


if __name__ == "__main__":
    poll_and_store()
