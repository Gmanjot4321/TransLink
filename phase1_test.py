"""
TransLink Reliability Tracker - Phase 1: Connection Test

Goal: prove we can hit TransLink's GTFS-RT V3 feed and parse real trip
update data (predicted vs scheduled arrivals). Nothing else yet.

Requires:
    pip install requests gtfs-realtime-bindings

Get your API key from: https://developer.translink.ca/
(Note: this is the SAME key type as before - RTTI and GTFS-RT V3 share
the TransLink developer account/key system, just different endpoints.)
"""

import requests
from google.transit import gtfs_realtime_pb2

API_KEY = "Ko5e94VoHU5G9tXOUcun"

# GTFS-RT V3 endpoints - these replace the retired RTTI REST API
TRIP_UPDATES_URL = f"https://gtfsapi.translink.ca/v3/gtfsrealtime?apikey={API_KEY}"
VEHICLE_POSITIONS_URL = f"https://gtfsapi.translink.ca/v3/gtfsposition?apikey={API_KEY}"
SERVICE_ALERTS_URL = f"https://gtfsapi.translink.ca/v3/gtfsalerts?apikey={API_KEY}"


def fetch_feed(url: str) -> gtfs_realtime_pb2.FeedMessage:
    """Fetch and parse a GTFS-RT protobuf feed."""
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(response.content)
    return feed


def test_trip_updates(route_filter: str | None = None, limit: int = 10):
    """
    Print live trip updates. This is the feed your whole reliability
    tracker is built on top of - it contains the predicted vs scheduled
    delay for each stop on each trip.
    """
    print("Requesting trip updates feed...\n")
    feed = fetch_feed(TRIP_UPDATES_URL)

    print(f"Feed timestamp: {feed.header.timestamp}")
    print(f"Total entities in feed: {len(feed.entity)}\n")

    shown = 0
    for entity in feed.entity:
        if not entity.HasField("trip_update"):
            continue

        tu = entity.trip_update
        route_id = tu.trip.route_id

        if route_filter and route_id != route_filter:
            continue

        print(f"Route {route_id} | Trip {tu.trip.trip_id}")

        for stu in tu.stop_time_update:
            delay_sec = None
            if stu.HasField("arrival") and stu.arrival.HasField("delay"):
                delay_sec = stu.arrival.delay
            elif stu.HasField("departure") and stu.departure.HasField("delay"):
                delay_sec = stu.departure.delay

            print(f"  stop_id={stu.stop_id}  delay={delay_sec}s")

        shown += 1
        if shown >= limit:
            break

    if shown == 0:
        print("No matching trip updates found. "
              "If you used route_filter, check the route_id format "
              "against TransLink's static GTFS routes.txt.")


def search_by_stop(stop_id: str, limit: int = 20):
    """
    Find all trip updates that include a specific stop_id, regardless of
    route. Useful when you know your stop number but not what the
    route_id looks like in this feed.
    """
    print(f"Searching feed for stop_id={stop_id}...\n")
    feed = fetch_feed(TRIP_UPDATES_URL)

    shown = 0
    for entity in feed.entity:
        if not entity.HasField("trip_update"):
            continue

        tu = entity.trip_update

        for stu in tu.stop_time_update:
            if stu.stop_id != stop_id:
                continue

            delay_sec = None
            if stu.HasField("arrival") and stu.arrival.HasField("delay"):
                delay_sec = stu.arrival.delay
            elif stu.HasField("departure") and stu.departure.HasField("delay"):
                delay_sec = stu.departure.delay

            print(f"route_id={tu.trip.route_id!r}  trip_id={tu.trip.trip_id}  "
                  f"stop_id={stu.stop_id}  delay={delay_sec}s")
            shown += 1
            break  # one match per trip is enough

        if shown >= limit:
            break

    if shown == 0:
        print(f"No trip updates found for stop_id={stop_id}. "
              "This stop may have no active real-time buses right now, "
              "or the stop_id format differs from what you expect "
              "(try without leading zeros, or as a string vs int).")


def list_route_ids(limit: int = 30):
    """
    Diagnostic: print the distinct route_id values that actually appear
    in the feed. Use this to find out what to pass into route_filter,
    since the real-time route_id often does NOT match the bus number
    printed on the bus.
    """
    print("Fetching feed to list distinct route_ids...\n")
    feed = fetch_feed(TRIP_UPDATES_URL)

    seen = set()
    for entity in feed.entity:
        if entity.HasField("trip_update"):
            seen.add(entity.trip_update.trip.route_id)

    print(f"Found {len(seen)} distinct route_ids in this feed:")
    for r in sorted(seen)[:limit]:
        print(" ", repr(r))  # repr() reveals hidden whitespace/type issues

    if len(seen) > limit:
        print(f"  ...and {len(seen) - limit} more (increase limit to see all)")


if __name__ == "__main__":
    if API_KEY == "paste_your_real_api_key_here":
        raise SystemExit("Set your real API key in API_KEY before running.")

    # Confirmed from static GTFS lookup:
    #   route 321/351 -> route_id "6705"
    #   stop 59087 (stop_code) -> stop_id "10445"
    test_trip_updates(route_filter="6705", limit=20)
    search_by_stop("10445", limit=20)