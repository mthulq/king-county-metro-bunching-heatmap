import requests
import pandas as pd
import json
import time
from datetime import datetime
import haversine as hs
from haversine import Unit

# Load pre-calculated data
with open('assets/route_median_headways.json', 'r') as f:
    route_median_headways = json.load(f)

routes = pd.read_csv("assets/routes.txt")
routes["route_id"] = routes["route_id"].astype(str)

url = "https://s3.amazonaws.com/kcm-alerts-realtime-prod/vehiclepositions_enhanced.json"


def fetch_bus_positions():
    """Fetches current bus positions and merges with route information."""
    response = requests.get(url)
    data = response.json()
    return pd.json_normalize(data["entity"]).merge(
        routes[["route_id", "route_short_name", "route_desc"]],
        left_on="vehicle.trip.route_id",
        right_on="route_id",
        how="left",
    )


def calculate_distance(bus):
    """Calculates distance in meters between a bus and the next bus."""
    loc1 = (bus["vehicle.position.latitude"], bus["vehicle.position.longitude"])
    loc2 = (bus["next_bus_latitude"], bus["next_bus_longitude"])
    return hs.haversine(loc1, loc2, unit=Unit.METERS)


def shift_group(group):
    """Shifts bus data to identify the next bus ahead."""
    group = group.sort_values("vehicle.current_stop_sequence")
    group["next_bus_stop_sequence"] = group["vehicle.current_stop_sequence"].shift()
    group["next_bus_vehicle_id"] = group["vehicle.vehicle.id"].shift()
    group["next_bus_latitude"] = group["vehicle.position.latitude"].shift()
    group["next_bus_longitude"] = group["vehicle.position.longitude"].shift()
    return group


def calculate_distance_to_next_bus(bus_positions_df):
    """Calculates distance to the next bus ahead for each bus."""
    grouped_buses = bus_positions_df.groupby(
        ["vehicle.trip.route_id", "vehicle.trip.direction_id"]
    )
    shifted_buses = (
        grouped_buses[
            [
                "vehicle.trip.route_id",
                "vehicle.current_stop_sequence",
                "vehicle.vehicle.id",
                "vehicle.position.latitude",
                "vehicle.position.longitude",
                "route_short_name",
                "route_desc",
            ]
        ]
        .apply(shift_group)
        .reset_index(drop=True)
    )
    shifted_buses["distance_to_next_bus_m"] = shifted_buses.apply(
        calculate_distance, axis=1
    )
    return shifted_buses


def estimate_headway(distance_m, avg_speed_m_s=6.169152):
    """Estimates time headway in minutes from distance."""
    return distance_m / avg_speed_m_s / 60


def detect_bunching(bus_positions_df, headways):
    """
    Detects bunching by comparing actual spacing to expected headways.
    Returns DataFrame with bunching_severity: 0=normal, 1=at risk, 2=bunched.
    """
    buses_with_distance = calculate_distance_to_next_bus(bus_positions_df)

    def classify_bunching(bus):
        route_id = bus["vehicle.trip.route_id"]
        if route_id not in headways or pd.isna(bus["distance_to_next_bus_m"]):
            return pd.Series({"bunching_severity": 0, "estimated_headway": None})
        
        estimated_headway = estimate_headway(bus["distance_to_next_bus_m"])
        expected_headway = headways[route_id]
        ratio = estimated_headway / expected_headway
        
        if ratio <= 0.5:
            bunching_severity = 2
        elif ratio <= 0.75:
            bunching_severity = 1
        else:
            bunching_severity = 0

        return pd.Series({
            "bunching_severity": bunching_severity,
            "estimated_headway": estimated_headway,
        })

    buses_with_distance[["bunching_severity", "estimated_headway"]] = \
        buses_with_distance.apply(classify_bunching, axis=1)
    return buses_with_distance


def log_bunching_events(output_file='bunching_events.csv'):
    """
    Continuously logs bunching events every 30 seconds to a CSV file.
    """
    print(f"Starting bunching logger. Data will be saved to {output_file}")
    print("Press Ctrl+C to stop.\n")
    
    while True:
        try:
            # Fetch and classify buses
            bus_positions = fetch_bus_positions()
            bunching_data = detect_bunching(bus_positions, route_median_headways)
            
            # Extract relevant columns and filter for bunched/at-risk buses only
            events = bunching_data[bunching_data['bunching_severity'] >= 1][[
                'vehicle.trip.route_id',
                'route_short_name',
                'route_desc',
                'vehicle.position.latitude',
                'vehicle.position.longitude',
                'bunching_severity',
                'estimated_headway'
            ]].copy()
            
            events['timestamp'] = datetime.now()
            
            # Rename columns for cleaner output
            events.columns = [
                'route_id',
                'route_short_name', 
                'route_desc',
                'latitude',
                'longitude',
                'bunching_severity',
                'estimated_headway',
                'timestamp'
            ]
            
            # Append to CSV (creates file if it doesn't exist)
            events.to_csv(
                output_file,
                mode='a',
                header=not pd.io.common.file_exists(output_file),
                index=False
            )
            
            # Print summary
            total_buses = len(bunching_data)
            logged = len(events)
            bunched = (events['bunching_severity'] == 2).sum()
            at_risk = (events['bunching_severity'] == 1).sum()
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                  f"{total_buses} buses active, logged {logged} events: {bunched} bunched, {at_risk} at risk")
            
            # Wait 30 seconds
            time.sleep(30)
            
        except KeyboardInterrupt:
            print("\n\nStopping bunching logger.")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(30)


if __name__ == "__main__":
    log_bunching_events()