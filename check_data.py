"""
TransLink Reliability Tracker - sanity check (multi-file CSV version)

Reads every snapshots_YYYY-MM-DD.csv file in the current folder and
gives a combined summary, since data is now rotated into one file
per day instead of a single ever-growing file.

Usage:
    python check_data.py
"""

import csv
import glob
from collections import Counter

files = sorted(glob.glob("snapshots_*.csv"))

if not files:
    print("No snapshots_*.csv files found in this folder.")
    raise SystemExit

all_rows = []
for path in files:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        all_rows.extend(rows)
        print(f"{path}: {len(rows)} rows")

print(f"\nTotal rows across {len(files)} file(s): {len(all_rows)}\n")

print("Row count per route:")
counts = Counter(row["route_id"] for row in all_rows)
for route_id, count in counts.items():
    label = next((r["route_label"] for r in all_rows if r["route_id"] == route_id), "")
    print(f"  route_id={route_id} ({label}): {count} rows")

if all_rows:
    print("\nMost recent 10 rows:")
    for row in all_rows[-10:]:
        print(" ", row["captured_at"], row["route_id"], row["stop_id"], row["delay_seconds"])

    print("\nEarliest and latest capture time:")
    print(all_rows[0]["captured_at"], "->", all_rows[-1]["captured_at"])
