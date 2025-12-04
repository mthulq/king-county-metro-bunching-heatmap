import requests
import pandas as pd
import json
import time
from datetime import datetime
import haversine as hs
from haversine import Unit
import os

with open('assets/route_median_headways.json', 'r') as f:
    route_median_headways = json.load(f)

routes = pd.read_csv("assets/routes.txt")
routes["route_id"] = routes["route_id"].astype(str)

url = "https://s3.amazonaws.com/kcm-alerts-realtime-prod/vehiclepositions_enhanced.json"


def fetch_bus_positions():
    response = requests.get(url)
    data = response.json()
    
    df = pd.json_normalize(data["entity"]) 
    
    # --- FIX 1: PROACTIVELY ENSURE CRITICAL COLUMNS EXIST ---
    required_trip_cols = ['vehicle.trip.route_id', 'vehicle.trip.direction_id', 'vehicle.vehicle.id', 'vehicle.position.latitude', 'vehicle.position.longitude']
    for col in required_trip_cols:
        if col not in df.columns:
            df[col] = None
    
    # --- FIX 2: MERGE AND DROP RECORDS WITH MISSING GROUPING KEYS ---
    # Merge first to get route names
    merged_df = df.merge(
        routes[["route_id", "route_short_name", "route_desc"]],
        left_on="vehicle.trip.route_id",
        right_on="route_id",
        how="left",
    )
    
    # Drop rows where the critical grouping keys are missing (cannot calculate distance without route/direction)
    merged_df.dropna(subset=['vehicle.trip.route_id', 'vehicle.trip.direction_id'], inplace=True)

    return merged_df


def calculate_distance(bus):
    loc1 = (bus["vehicle.position.latitude"], bus["vehicle.position.longitude"])
    loc2 = (bus["next_bus_latitude"], bus["next_bus_longitude"])
    return hs.haversine(loc1, loc2, unit=Unit.METERS)


def shift_group(group):
    # Ensure all necessary shift columns exist before shifting
    group = group.sort_values("vehicle.current_stop_sequence")
    group["next_bus_stop_sequence"] = group["vehicle.current_stop_sequence"].shift()
    group["next_bus_vehicle_id"] = group["vehicle.vehicle.id"].shift()
    group["next_bus_latitude"] = group["vehicle.position.latitude"].shift()
    group["next_bus_longitude"] = group["vehicle.position.longitude"].shift()
    return group


def calculate_distance_to_next_bus(bus_positions_df):
    # The columns for grouping are guaranteed to exist due to the preprocessing in fetch_bus_positions
    grouped_buses = bus_positions_df.groupby(
        ["vehicle.trip.route_id", "vehicle.trip.direction_id"]
    )
    
    # Ensure only necessary columns are selected before applying the shift
    columns_to_process = [
        "vehicle.trip.route_id",
        "vehicle.current_stop_sequence",
        "vehicle.vehicle.id",
        "vehicle.position.latitude",
        "vehicle.position.longitude",
        "route_short_name",
        "route_desc",
        "vehicle.trip.direction_id"  # Explicitly include direction_id here for clarity
    ]

    shifted_buses = (
        grouped_buses[columns_to_process]
        .apply(shift_group)
        .reset_index(drop=True)
    )
    
    # Drop rows that are the first in a group (no "next bus" to compare to)
    shifted_buses.dropna(subset=['next_bus_vehicle_id'], inplace=True)
    
    shifted_buses["distance_to_next_bus_m"] = shifted_buses.apply(
        calculate_distance, axis=1
    )
    return shifted_buses


def estimate_headway(distance_m, avg_speed_m_s=6.169152):
    return distance_m / avg_speed_m_s / 60


def detect_bunching(bus_positions_df, headways):
    buses_with_distance = calculate_distance_to_next_bus(bus_positions_df)

    def classify_bunching(bus):
        route_id = bus["vehicle.trip.route_id"]
        # Also check for presence of direction_id, although it should be handled by fetch/grouping
        if pd.isna(route_id) or pd.isna(bus["distance_to_next_bus_m"]):
            return pd.Series({"bunching_severity": 0, "estimated_headway": None, "event_id": None})
        
        estimated_headway = estimate_headway(bus["distance_to_next_bus_m"])
        expected_headway = headways.get(route_id, 9999)
        ratio = estimated_headway / expected_headway
        
        if ratio <= 0.5:
            bunching_severity = 2
        elif ratio <= 0.75:
            bunching_severity = 1
        else:
            bunching_severity = 0

        event_id = f"{route_id}-{bus['vehicle.trip.direction_id']}-{bus['vehicle.vehicle.id']}-{bus['next_bus_vehicle_id']}"

        return pd.Series({
            "bunching_severity": bunching_severity,
            "estimated_headway": estimated_headway,
            "event_id": event_id if bunching_severity >= 1 else None
        })

    buses_with_distance[[
        "bunching_severity", 
        "estimated_headway", 
        "event_id"
    ]] = buses_with_distance.apply(classify_bunching, axis=1)
    
    return buses_with_distance


def log_bunching_events(output_file='bunching_events_incidence_and_escalation.csv'):
    print(f"Starting bunching logger. Data will be saved to {output_file}")
    print("Press Ctrl+C to stop.\n")

    last_bunched_state = {} 
    
    while True:
        try:
            bus_positions = fetch_bus_positions()
            bunching_data = detect_bunching(bus_positions, route_median_headways)
            
            active_events = bunching_data[bunching_data['bunching_severity'] >= 1].copy()
            
            logs_to_save_list = []
            current_state = {}

            for _, event in active_events.iterrows():
                event_id = event['event_id']
                current_severity = event['bunching_severity']
                last_severity = last_bunched_state.get(event_id, 0)

                current_state[event_id] = current_severity
                
                if current_severity > last_severity:
                    logs_to_save_list.append(event)
            
            new_events = pd.DataFrame(logs_to_save_list)

            last_bunched_state = current_state

            if not new_events.empty:
                logs_to_save = new_events[[
                    'vehicle.trip.route_id',
                    'route_short_name',
                    'route_desc',
                    'vehicle.position.latitude',
                    'vehicle.position.longitude',
                    'bunching_severity',
                    'estimated_headway'
                ]].copy()
                
                logs_to_save['timestamp'] = datetime.now()
                
                logs_to_save.columns = [
                    'route_id',
                    'route_short_name', 
                    'route_desc',
                    'latitude',
                    'longitude',
                    'bunching_severity',
                    'estimated_headway',
                    'timestamp'
                ]
                
                logs_to_save.to_csv(
                    output_file,
                    mode='a',
                    header=not pd.io.common.file_exists(output_file),
                    index=False
                )

            total_buses = len(bunching_data)
            logged = len(new_events)
            bunched = (new_events['bunching_severity'] == 2).sum()
            at_risk = (new_events['bunching_severity'] == 1).sum()
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                  f"{total_buses} buses active. Logged {logged} NEW/ESCALATED events: {bunched} bunched, {at_risk} at risk. "
                  f"({len(last_bunched_state)} events currently active.)")
            
            time.sleep(30)
            
        except KeyboardInterrupt:
            print("\n\nStopping bunching logger.")
            break
        except Exception as e:
            print(f"Error: {type(e).__name__}: {e}")
            time.sleep(30)


if __name__ == "__main__":
    log_bunching_events()