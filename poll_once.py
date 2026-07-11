"""
TransLink Reliability Tracker - Phase 2 (GitHub Actions version)

Same logic as collect_data.py, but runs ONE poll and exits, instead of
looping forever. Designed to be triggered on a schedule by GitHub
Actions, so your own machine doesn't need to stay on.

The API key is read from an environment variable (set as a GitHub
Secret in the workflow), not hardcoded, since this file will live in
a public repo.
"""

import os
import sqlite3
from datetime import datetime, timezone

import requests
from google.transit import gtfs_realtime_pb2

API_KEY = os.environ["TRANSLINK_API_KEY"]  # set via GitHub Secrets
TRIP_UPDATES_URL = f"https://gtfsapi.translink.ca/v3/gtfsrealtime?apikey={API_KEY}"

DB_PATH = "translink_reliability.db"

TRACKED_ROUTES = {
    "6705": "321 Surrey Central/WhiteRock",  "6715":"351 Bridgeport/WhiteRock",
    "18705":"531 WhiteRock/WillowBrook" ,"11692":"364 Langley Centre/Scottsdale"
}


def init_db(conn):
    conn.execute("""
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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_route ON snapshots(route_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_stop ON snapshots(stop_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_captured_at ON snapshots(captured_at)")
    conn.commit()


def fetch_feed() -> gtfs_realtime_pb2.FeedMessage:
    response = requests.get(TRIP_UPDATES_URL, timeout=10)
    response.raise_for_status()
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(response.content)
    return feed


def poll_and_store():
    captured_at = datetime.now(timezone.utc).isoformat()
    print(f"[{captured_at}] Polling feed...")

    feed = fetch_feed()

    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    rows_inserted = 0

    for entity in feed.entity:
        if not entity.HasField("trip_update"):
            continue

        tu = entity.trip_update
        route_id = tu.trip.route_id

        if route_id not in TRACKED_ROUTES:
            continue

        route_label = TRACKED_ROUTES[route_id]

        for stu in tu.stop_time_update:
            delay_sec = None
            if stu.HasField("arrival") and stu.arrival.HasField("delay"):
                delay_sec = stu.arrival.delay
            elif stu.HasField("departure") and stu.departure.HasField("delay"):
                delay_sec = stu.departure.delay

            if delay_sec is None:
                continue

            conn.execute(
                """
                INSERT INTO snapshots
                    (captured_at, feed_timestamp, route_id, route_label,
                     trip_id, stop_id, stop_sequence, delay_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    captured_at,
                    feed.header.timestamp,
                    route_id,
                    route_label,
                    tu.trip.trip_id,
                    stu.stop_id,
                    stu.stop_sequence,
                    delay_sec,
                ),
            )
            rows_inserted += 1

    conn.commit()
    conn.close()
    print(f"Stored {rows_inserted} rows.")


if __name__ == "__main__":
    poll_and_store()