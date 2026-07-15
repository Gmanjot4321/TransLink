"""
TransLink Reliability Tracker - quick sanity check

Run this any time while collect_data.py is running (or after) to confirm
rows are actually being stored, and get a first peek at the data.

Usage:
    python check_data.py
"""

import sqlite3

DB_PATH = "translink_reliability.db"

conn = sqlite3.connect(DB_PATH)

print("Row count per route:")
for route_id, label, count in conn.execute("""
    SELECT route_id, route_label, COUNT(*)
    FROM snapshots
    GROUP BY route_id
"""):
    print(f"  route_id={route_id} ({label}): {count} rows")

print("\nMost recent 10 rows:")
for row in conn.execute("""
    SELECT captured_at, route_id, stop_id, delay_seconds
    FROM snapshots
    ORDER BY captured_at DESC
    LIMIT 10
"""):
    print(" ", row)

print("\nEarliest and latest capture time:")
print(conn.execute("SELECT MIN(captured_at), MAX(captured_at) FROM snapshots").fetchone())

conn.close()