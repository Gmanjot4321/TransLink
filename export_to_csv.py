"""
One-time migration: export existing translink_reliability.db (SQLite)
into snapshots.csv, so historical data collected so far isn't lost
when switching to the CSV-based storage approach.

Run this ONCE, locally, before switching poll_once.py over to CSV.
"""

import csv
import sqlite3

DB_PATH = "translink_reliability.db"
CSV_PATH = "snapshots.csv"

conn = sqlite3.connect(DB_PATH)
cursor = conn.execute("""
    SELECT captured_at, feed_timestamp, route_id, route_label,
           trip_id, stop_id, stop_sequence, delay_seconds
    FROM snapshots
    ORDER BY captured_at
""")

with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow([
        "captured_at", "feed_timestamp", "route_id", "route_label",
        "trip_id", "stop_id", "stop_sequence", "delay_seconds"
    ])
    row_count = 0
    for row in cursor:
        writer.writerow(row)
        row_count += 1

conn.close()
print(f"Exported {row_count} rows to {CSV_PATH}")