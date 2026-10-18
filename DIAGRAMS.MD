# Vaillant Data Capture Diagrams

This document contains Mermaid diagrams explaining the core logic and flows of the Vaillant Data Capture application.

## Authorization and Polling Flow

The following sequence diagram illustrates how the application initializes, handles authentication (including token refreshes), and performs the periodic polling of Vaillant system data to be stored in InfluxDB.

```mermaid
sequenceDiagram
    participant App as VaillantDataCaptureApp
    participant Client as VaillantClient
    participant API as MyPyllantAPI (myPyllant library)
    participant Influx as InfluxWrapper

    Note over App, Influx: 1. Initialization and Startup
    App->>Influx: connect()
    App->>App: Enter Polling Loop (while not shutdown)

    Note over App, API: 2. Authorization & Data Fetching
    App->>Client: get_systems()
    
    alt Client Not Initialized
        Client->>Client: initialize()
        Client->>API: login(credentials)
        API-->>Client: Success (Authentication Token)
    end

    Client->>API: get_systems(include_diagnostic_trouble_codes=True)
    
    alt Token Expired (401 Unauthorized)
        API-->>Client: 401 Unauthorized
        Note right of Client: Automatic Retry Logic
        Client->>API: refresh_token()
        
        alt Refresh Fails
            API-->>Client: Refresh Error
            Client->>Client: initialize() (Full Re-authentication)
            Client->>API: login(credentials)
        end
        
        Client->>API: get_systems(...) (Retry)
    end
    
    API-->>Client: List of Systems
    Client-->>App: AsyncGenerator[System]

    Note over App, Influx: 3. Metrics Extraction & Storage
    loop For each System in Generator
        App->>App: _process_system(system)
        
        rect rgb(240, 240, 240)
            Note right of App: Extract metrics from System object
            App->>Influx: write_point("vaillant_system", system_fields)
            App->>Influx: write_point("vaillant_zones", zone_fields)
            App->>Influx: write_point("vaillant_circuits", circuit_fields)
            App->>Influx: write_point("vaillant_dhw", dhw_fields)
        end
    end

    Note over App: 4. Poll Interval Management
    App->>App: Calculate Sleep Time (VAILLANT_POLL_INTERVAL - elapsed)
    App->>App: Wait for next poll or shutdown signal
```

### Key Components

- **VaillantDataCaptureApp**: The orchestrator. Manages the main loop, state, and coordination between the API client and InfluxDB.
- **VaillantClient**: A wrapper around the `myPyllant` library. It handles the nuances of authentication, token refreshes, and API retries.
- **MyPyllantAPI**: The underlying library used to communicate with the Vaillant (myPyllant) cloud services.
- **InfluxWrapper**: Manages the connection and data writing to the InfluxDB instance.

### Error Handling

The application includes robust error handling for the polling process:
- **401 Unauthorized**: Handled by `VaillantClient`, which attempts a `refresh_token()` first before falling back to a full login.
- **Network/API Errors**: Caught in the main loop, logged, and (if not in dry-run mode) reported as an error metric to InfluxDB.
