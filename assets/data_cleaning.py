import requests
import pandas as pd
import json
from json import loads, dumps
import os

url = "https://s3.amazonaws.com/kcm-alerts-realtime-prod/vehiclepositions_enhanced.json"
routes = pd.read_csv("assets/routes.txt")
routes["route_id"] = routes["route_id"].astype(str)


def fetch_bus_positions():
    """
    Fetches current bus positions from the real-time API and merges with route information.
    Returns a DataFrame containing vehicle positions and route details.
    """
    response = requests.get(url)
    data = response.json()
    return pd.json_normalize(data["entity"]).merge(
        routes[["route_id", "route_short_name", "route_desc"]],
        left_on="vehicle.trip.route_id",
        right_on="route_id",
        how="left",
    )


stop_times = pd.read_csv("assets/stop_times.txt")
trips = pd.read_csv("assets/trips.txt")
trip_schedules = stop_times.merge(trips[["trip_id", "route_id"]], on="trip_id")


def arrival_time_to_mins(arrival_time_str):
    """
    Converts GTFS timestamp (HH:MM:SS) to total minutes since midnight.
    """
    time_components = arrival_time_str.split(":")
    return (
        (int(time_components[0]) * 60)
        + int(time_components[1])
        + (int(time_components[2]) / 60)
    )


trip_schedules["arrival_time_mins"] = trip_schedules["arrival_time"].apply(
    arrival_time_to_mins
)


def calculate_route_median_headways():
    """
    Calculates median headways for each route during daytime hours (6 AM - 10 PM).
    Returns a dictionary mapping route_id to median headway in minutes, excluding routes with headways <5 or >120 minutes.
    """
    daytime_first_stops = trip_schedules[
        (trip_schedules["stop_sequence"] == 1)
        & (trip_schedules["arrival_time_mins"] >= 360)
        & (trip_schedules["arrival_time_mins"] <= 1320)
    ]

    daytime_first_stops["headway"] = daytime_first_stops.groupby("route_id")[
        "arrival_time_mins"
    ].diff()

    median_headways = daytime_first_stops.groupby("route_id")["headway"].median()
    valid_headways = median_headways[(median_headways > 5) & (median_headways < 120)]

    return {str(route_id): headway for route_id, headway in valid_headways.items()}


def route_info_to_json(route_info_df):
    result = (
        route_info_df.groupby("route_id")[
            ["route_id", "route_short_name", "route_desc"]
        ]
        .apply(lambda x: x.drop("route_id", axis=1).to_dict(orient="records")[0])
        .to_json()
    )
    return dumps(loads(result))

route_median_headways = calculate_route_median_headways()
route_info_json = route_info_to_json(routes)

os.makedirs('assets', exist_ok=True)

with open('assets/route_median_headways.json', 'w') as f:
    json.dump(route_median_headways, f, indent=2)

with open('assets/route_info.json', 'w') as f:
    f.write(route_info_json)

print("Processed data saved to assets folder!")