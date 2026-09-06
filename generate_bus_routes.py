"""
Generate bus_routes.json - the full list of TransLink BUS routes
(route_id -> label), excluding SkyTrain, SeaBus, and West Coast Express.

Run this ONCE to produce bus_routes.json, which poll_once.py then
loads to know which routes to track.

Requires:
    pip install requests pandas
"""

import io
import json
import zipfile

import pandas as pd
import requests

GTFS_ZIP_URL = "https://gtfs-static.translink.ca/gtfs/google_transit.zip"

resp = requests.get(GTFS_ZIP_URL, timeout=30)
resp.raise_for_status()
zf = zipfile.ZipFile(io.BytesIO(resp.content))

with zf.open("routes.txt") as f:
    routes_df = pd.read_csv(f, dtype=str)

print(f"Total routes in static GTFS: {len(routes_df)}")
print("route_type breakdown:")
print(routes_df["route_type"].value_counts())

# GTFS route_type: 3 = Bus, 0 = Tram/Streetcar, 1 = Subway (SkyTrain), 4 = Ferry (SeaBus)
bus_routes = routes_df[routes_df["route_type"] == "3"]
print(f"\nBus routes only: {len(bus_routes)}")

route_map = {
    row["route_id"]: f'{row["route_short_name"]} {row["route_long_name"]}'.strip()
    for _, row in bus_routes.iterrows()
}

with open("bus_routes.json", "w", encoding="utf-8") as f:
    json.dump(route_map, f, indent=2)

print(f"\nSaved {len(route_map)} bus routes to bus_routes.json")