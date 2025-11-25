
Final Project – King County Metro Bus Bunching Heatmap
======================================================

## Project Description

This project builds a web‑based heatmap that visualizes **bus bunching** in the King County Metro system. Using GTFS schedule data and real‑time vehicle positions, we identify when buses on the same route are much closer together than planned and convert those events into a spatial dataset. The web map highlights where bunching happens most frequently so planners and riders can quickly see “hot spots” of unreliable service across Seattle and the surrounding area.

Our application focuses on **historic bunching events**, not live prediction. Every time a bunching event is detected in the data pipeline, it is written to a CSV file and later aggregated into a GeoJSON layer that drives the heatmap. The project extends earlier course work on GTFS and interactive mapping and packages it into a reusable tool for exploring transit reliability.

## Project Goal

The main goal is to help **King County Metro planners and analysts** understand where and when bus bunching is most severe. By turning millions of schedule and vehicle records into an intuitive heatmap, the app aims to:

- Reveal persistent corridors and stops with high bunching severity.
- Support future planning decisions such as schedule adjustments, signal priority, or stop consolidation.
- Demonstrate how open GTFS feeds can be transformed into an actionable reliability dashboard.

## Data Sources

- **King County Metro GTFS static data**  
  - `routes.txt`, `trips.txt`, `stop_times.txt` for route structure and scheduled headways.
- **King County Metro GTFS‑realtime vehicle positions**  
  - Enhanced JSON feed with vehicle locations, routes, directions, and timestamps.
- All data are publicly available from King County Metro’s developer resources.

## Data Cleaning and Processing (Backend – Mo)

1. **Route Information Standardization**  
   - Converted route IDs to string type and selected key fields (short name, description) for display.

2. **Schedule‑Based Headway Calculation**  
   - Converted scheduled arrival times to minutes since midnight.  
   - Filtered to daytime service (6 AM–10 PM) to focus on meaningful bunching.  
   - Computed planned headways between consecutive trips on each route.

3. **Route Filtering**  
   - Excluded routes with median headways &lt; 5 minutes or &gt; 120 minutes to avoid noisy and low‑frequency routes.

4. **Real‑time Data Integration and Bunching Detection**  
   - Joined live vehicle positions to schedule data.  
   - Compared actual vehicle spacing to planned headways to flag bunching events and assign a **bunching severity score**.

5. **Heatmap Dataset Creation**  
   - Wrote all detected bunching events to `bunching_events.csv`.  
   - Aggregated records to a GeoJSON layer suitable for heatmap rendering in the web app.

## Main Functions (Frontend)

- Interactive web map showing a **heatmap of bunching intensity** across King County.  
- Checkboxes / filters to turn individual routes or route groups on and off.  
- Mouse hover and pop‑ups that display key attributes for a location (route, stop area, average severity, event counts, etc.).  
- Legend explaining the color ramp and what “high bunching” means.  
- Responsive layout designed to work on common desktop and laptop screens.

## Technology Stack

- **Frontend:** HTML, CSS, JavaScript, Mapbox GL JS heatmap template (adapted from course materials).  
- **Backend / Pre‑processing:** Python (pandas, NumPy, possibly GeoPandas) for GTFS processing and CSV/GeoJSON generation.  
- **Version control & hosting:** GitHub + GitHub Pages.
