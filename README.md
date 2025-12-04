Final Project – King County Metro Bus Bunching Heatmap
======================================================

## Project Description

This project builds a web‑based interactive heatmap that visualizes **bus bunching** across the King County Metro system. Bus bunching occurs when buses on the same route arrive much closer together than planned, causing uneven service, long wait times, and operational inefficiencies. Using GTFS schedule data and real‑time vehicle positions, our system detects these bunching events, assigns severity scores, and stores them in a reproducible dataset. The frontend application (built using Mapbox GL JS) displays these events as a heatmap and allows users to explore locations with persistent reliability issues.

Unlike dashboards that focus only on real‑time operations, this project emphasizes **long‑term bunching patterns**. The backend pipeline continuously processes vehicle feeds, detects bunching, and records events in a CSV file that is later transformed into a GeoJSON dataset. This GeoJSON powers the heatmap, revealing broader spatial patterns across Seattle, Bellevue, Redmond, Renton, and surrounding King County areas. This approach enables transportation planners to identify consistent problem zones rather than isolated anomalies.

## Project Goal

The goal of this tool is to support **Metro planners, analysts, and the public** by providing a clear spatial visualization of where bus bunching occurs most frequently. Through large‑scale data processing and intuitive design, the heatmap aims to:

- Highlight persistent corridors with high bunching severity.
- Identify stop clusters and intersections where service reliability breaks down.
- Support planning decisions such as headway adjustments, transit priority strategies, and route redesigns.
- Demonstrate how open GTFS feeds can be transformed into an actionable, map‑based reliability dashboard.

This tool is intended as a foundation for further development, such as adding temporal filters, live metrics, or predictive analytics.

## Data Sources

All data used in this project is publicly available from King County Metro:

- **GTFS static data**  
  Provides planned routes, trips, stop sequences, and scheduled arrival times.

- **GTFS‑realtime vehicle positions (enhanced JSON)**  
  Supplies latitude/longitude, timestamp, route, and vehicle identifiers for detecting actual spacing.

These datasets together enable accurate computation of planned vs. actual headways.

---

## Data Cleaning and Processing (Backend – Mo)

### 1. Route Information Standardization
The backend converts all route IDs to string types for consistency and selects only essential fields (route short name, description) to keep the dataset lightweight.

### 2. Scheduled Headway Calculation
- Arrival times are converted to minutes after midnight.
- Analysis is restricted to **6 AM–10 PM**, when bunching affects service the most.
- Planned headways are derived by comparing consecutive scheduled trips on each route and direction.

### 3. Route Filtering
Routes with median headways below 5 minutes or above 120 minutes are excluded to remove high‑frequency noise and low‑frequency outliers.

### 4. Real‑time Integration and Bunching Detection
- Real‑time vehicle positions are joined to scheduled trips.
- Actual distance‑based spacing is compared to planned headways.
- If actual spacing falls below a computed threshold, a bunching event is flagged.
- Each event includes coordinates, route, direction, timestamp, and a severity score.

### 5. GeoJSON Heatmap Dataset Creation
All events are stored in `bunching_events.csv`.  
A processing script aggregates these records and outputs a final GeoJSON file used by the frontend heatmap renderer.

---

## Main Functions (Frontend – Mo & Ruiming & Vincent)

The frontend is a critical component of the project, responsible for rendering data, enabling user interaction, and providing meaningful insights through filtering and pop‑ups.

### 1. Heatmap Rendering

The processed GeoJSON is loaded into Mapbox GL JS as a custom source. A heatmap layer is styled using:

- **Intensity scaling** based on event frequency  
- **A multi‑stop color ramp** transitioning from yellow → orange → deep red  
- **Zoom‑adaptive radius and opacity**

This allows the visualization to show broad spatial trends at low zoom levels and detailed local hotspots when zoomed in.

### 2. Route Filter Panel

A dynamic filter panel on the right side of the interface enables users to toggle individual routes:

- All unique route names are detected from the GeoJSON dataset.
- A checkbox is created for each route.
- Checking or unchecking a route updates a Mapbox **filter expression** that hides or displays heatmap points belonging to that route.

This filtering system allows planners to isolate reliability issues for specific lines or families of routes.

### 3. Hover Pop‑Ups

A event detecter detects the nearest point under the cursor and displays a customizable popup. Popups include:

- Route number  
- Stop or intersection area  
- Bunching severity  
- Estimated headway  
- Timestamp of the event  

This transforms the visualization from a static heatmap into an interactive analytical tool.

### 4. Responsive Layout and UI Behavior

The webpage layout is optimized for laptop displays and ensures:

- Smooth pan/zoom behavior on the map  
- Automatic resizing of the filter sidebar  
- Clear popups and legible labels  
- Consistency across Chrome, Safari, and Firefox  

We adjusted the heatmap layer styling so that event density remains visible as the user zooms in or out.

### 5. Experimental Features (Future Work)

The frontend includes exploratory work toward:

- **Cluster detection** with Mapbox clustering  
- **Top‑5 densest hotspot detection**  
- **Circle overlays** marking high‑density areas  
- **Zoom‑dependent dynamic density polling**

These features laid groundwork for more advanced spatial analysis but require additional spatial indexing beyond what Mapbox’s default clustering offers.

---

## Technology Stack

- **Frontend:** HTML, CSS, JavaScript, Mapbox GL JS  
- **Backend:** Python (pandas, NumPy, GeoPandas), GTFS processing scripts  
- **Hosting:** GitHub Pages  
- **Version Control:** Git + GitHub
