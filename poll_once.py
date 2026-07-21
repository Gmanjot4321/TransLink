"""
TransLink Reliability Tracker - Phase 2 (CSV version)

Appends new rows to snapshots.csv instead of writing to a SQLite
database file. Git compresses growing text files efficiently via
line-based diffs, so this avoids the Git LFS storage blowup that
happens when committing a large, ever-changing binary .db file.
"""

import csv
import os
from datetime import datetime, timezone

import requests
from google.transit import gtfs_realtime_pb2

API_KEY = os.environ["TRANSLINK_API_KEY"]
TRIP_UPDATES_URL = f"https://gtfsapi.translink.ca/v3/gtfsrealtime?apikey={API_KEY}"

CSV_HEADER = [
    "captured_at", "feed_timestamp", "route_id", "route_label",
    "trip_id", "stop_id", "stop_sequence", "delay_seconds"
]

def get_csv_path():
    """One file per UTC day, so no single file ever grows unbounded."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"snapshots_{today}.csv"

# Update this with your 4 tracked routes (route_id -> label).
TRACKED_ROUTES = {
    "6705": "321/351",
    # add your other 3 routes here, e.g.:
    # "XXXX": "route_number_2",
    # "YYYY": "route_number_3",
    # "ZZZZ": "route_number_4",
}


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

    csv_path = get_csv_path()
    file_exists = os.path.exists(csv_path)
    rows_written = 0

    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(CSV_HEADER)

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

                writer.writerow([
                    captured_at,
                    feed.header.timestamp,
                    route_id,
                    route_label,
                    tu.trip.trip_id,
                    stu.stop_id,
                    stu.stop_sequence,
                    delay_sec,
                ])
                rows_written += 1

    print(f"Appended {rows_written} rows to {csv_path}.")


if __name__ == "__main__":
    poll_and_store()
