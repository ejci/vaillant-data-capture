# Vaillant Data Capture

A Python-based application that captures telemetry data from Vaillant heating systems (via the myPyllant library) and pushes it to an InfluxDB instance. Designed to be run as a Docker container.

## Features

- **Automated Polling**: Fetches system data at configurable intervals.
- **InfluxDB Integration**: Writes data to InfluxDB with proper tagging (System ID, Zone Index, etc.).
- **Dockerized**: specific `Dockerfile` and `compose.yaml` for easy deployment.
- **Dry Run Mode**: Test data collection without writing to the database.
- **Resilient**: Handles API errors and connection issues gracefully.
- **Loki-ready Logging**: Emits newline-delimited JSON to stdout for easy ingestion by Promtail/Alloy.

## Prerequisites

- **Vaillant Account**: Credentials for your Vaillant app (e.g., sensoAPP/myVaillant).
- **InfluxDB**: A running InfluxDB v2 instance (URL, Org, Bucket, Token).
- **Docker**: To run the application container.

## Setup & Running

1.  **Clone the repository**
    ```bash
    git clone <repository-url>
    cd vaillant-data-capture
    ```

2.  **Configure Environment Variables**
    Copy the example environment file and edit it with your details:
    ```bash
    cp .env.example .env
    ```

    **Required Variables:**
    - `VAILLANT_EMAIL`: Your Vaillant username/email.
    - `VAILLANT_PASSWORD`: Your Vaillant password.
    - `INFLUX_URL`: URL of your InfluxDB instance (e.g., `http://localhost:8086`).
    - `INFLUX_TOKEN`: InfluxDB API token.
    - `INFLUX_ORG`: InfluxDB Organization name.
    - `INFLUX_BUCKET`: InfluxDB Bucket name.

    **Optional Variables:**
    - `VAILLANT_BRAND`: Brand of your system (default: `vaillant`).
    - `VAILLANT_COUNTRY`: Country code (default: `netherlands`).
    - `VAILLANT_POLL_INTERVAL`: Time between polls in milliseconds (default: `600000` = 10 minutes).
    - `VAILLANT_DRYRUN`: Set to `true` to print data to console instead of writing to InfluxDB.
    - `VAILLANT_LOG_LEVEL`: Log verbosity — `debug`, `info`, `warning`, `error` (default: `info`).

3.  **Run with Docker Compose**
    ```bash
    docker-compose up --build -d
    ```

## Data Schema

The application writes the following measurements to InfluxDB:

### `vaillant_system`
*   **Fields**:
    *   `outdoor_temperature`: Current outdoor temperature.
    *   `outdoor_temperature_average24h`: 24h average outdoor temperature.
    *   `system_flow_temperature`: Current system flow temperature.
    *   `system_water_pressure`: System water pressure.
    *   `adaptive_heating_curve`: Boolean indicating if adaptive hearing curve is enabled.

### `vaillant_zones`
*   **Tags**: `zone_index`, `system_id`
*   **Fields**:
    *   `desired_room_temperature_setpoint_heating`: Heating setpoint.
    *   `desired_room_temperature_setpoint`: Current effective setpoint.

### `vaillant_circuits`
*   **Tags**: `circuit_index`, `system_id`
*   **Fields**:
    *   `current_circuit_flow_temperature`: Current flow temp in circuit.
    *   `heating_circuit_flow_setpoint`: Target flow temp.
    *   `heating_curve`: The configured heating curve value (if available).

### `vaillant_dhw`
*   **Tags**: `dhw_index`, `system_id`
*   **Fields**:
    *   `current_dhw_temperature`: Current hot water tank temperature.

## Logging & Loki

All logs are emitted as newline-delimited JSON to stdout:

```
{"level": 30, "time": "2026-02-21T14:51:18.985Z", "service": "vaillant-data-capture", "msg": "Polling data..."}
{"level": 50, "time": "2026-02-21T14:51:18.987Z", "service": "vaillant-data-capture", "msg": "Error during polling"}
```

Each line carries `"service": "vaillant-data-capture"`, making it straightforward to create Loki label filters in Promtail/Alloy.

## Development

To run locally without Docker for development:

1.  Create a virtual environment:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Run the application:
    ```bash
    python main.py
    ```
