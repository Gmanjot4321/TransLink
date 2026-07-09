"""
TransLink Reliability Tracker - Phase 2: Data Collection & Storage

Polls the GTFS-RT trip updates feed every N minutes, extracts delay data
for a set of routes/stops you care about, and stores each snapshot in
a SQLite database. Let this run for 1-2 weeks to build a real dataset.

Requires:
    pip install requests gtfs-realtime-bindings schedule
"""

import sqlite3
import time
from datetime import datetime, timezone

import requests
import schedule
from google.transit import gtfs_realtime_pb2

API_KEY = "Ko5e94VoHU5G9tXOUcun"
TRIP_UPDATES_URL = f"https://gtfsapi.translink.ca/v3/gtfsrealtime?apikey={API_KEY}"

DB_PATH = "translink_reliability.db"

# The routes you want to track. Add more (route_id -> label) pairs here
# as you look them up via gtfs_lookup.py.
TRACKED_ROUTES = {
    "6705": "321 Surrey Central/WhiteRock",  "6715":"351 Bridgeport/WhiteRock",
    "18705":"531 WhiteRock/WillowBrook" ,"11692":"364 Langley Centre/Scottsdale"
}

POLL_INTERVAL_MINUTES = 2


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            captured_at TEXT NOT NULL,      -- ISO timestamp when we polled
            feed_timestamp INTEGER,          -- timestamp reported by the feed itself
            route_id TEXT NOT NULL,
            route_label TEXT,
            trip_id TEXT NOT NULL,
            stop_id TEXT NOT NULL,
            stop_sequence INTEGER,
            delay_seconds INTEGER
        )
    """)
    # Speeds up the queries you'll run in Phase 3 (group by route/stop/time).
    conn.execute("CREATE INDEX IF NOT EXISTS idx_route ON snapshots(route_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_stop ON snapshots(stop_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_captured_at ON snapshots(captured_at)")
    conn.commit()
    return conn


def fetch_feed() -> gtfs_realtime_pb2.FeedMessage:
    response = requests.get(TRIP_UPDATES_URL, timeout=10)
    response.raise_for_status()
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(response.content)
    return feed


def poll_and_store():
    captured_at = datetime.now(timezone.utc).isoformat()
    print(f"[{captured_at}] Polling feed...")

    try:
        feed = fetch_feed()
    except Exception as e:
        print(f"  ERROR fetching feed: {e}")
        return

    conn = sqlite3.connect(DB_PATH)
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
                continue  # nothing useful to store for this stop yet

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
    print(f"  Stored {rows_inserted} rows.")


if __name__ == "__main__":
    if API_KEY == "paste_your_real_api_key_here":
        raise SystemExit("Set your real API key in API_KEY before running.")

    init_db()
    print(f"Database ready at {DB_PATH}")
    print(f"Tracking routes: {TRACKED_ROUTES}")
    print(f"Polling every {POLL_INTERVAL_MINUTES} minute(s). Press Ctrl+C to stop.\n")

    # Run once immediately, then on the schedule.
    poll_and_store()
    schedule.every(POLL_INTERVAL_MINUTES).minutes.do(poll_and_store)

    while True:
        schedule.run_pending()
        time.sleep(5)

