"""
TransLink Reliability Tracker - Phase 2 (CSV version, daily rotation)

Appends new rows to a per-day CSV file (snapshots_YYYY-MM-DD.csv)
instead of one ever-growing file, so no single file ever approaches
GitHub's 100MB file size limit.
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


TRACKED_ROUTES = {
    "6705": "321 Surrey Central/WhiteRock",
    "6715": "351 Bridgeport/WhiteRock",
    "18705": "531 WhiteRock/WillowBrook",
    "11692": "364 Langley Centre/Scottsdale",
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