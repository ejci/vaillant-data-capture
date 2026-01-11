import asyncio
import logging
import signal
import sys
from datetime import datetime, timedelta

from src.config import Config
from src.logger import logger
from src.influx import InfluxWrapper
from src.vaillant import VaillantClient

# Global state for graceful shutdown
SHUTDOWN = False
API_CALLS_24H = 0
LAST_RESET = datetime.now()

def signal_handler(sig, frame):
    global SHUTDOWN
    logger.info("Received shutdown signal. Stopping...")
    SHUTDOWN = True

def track_api_call():
    global API_CALLS_24H, LAST_RESET
    now = datetime.now()
    if now - LAST_RESET > timedelta(hours=24):
        logger.info(f"Resetting 24h API call count. Total was: {API_CALLS_24H}")
        API_CALLS_24H = 0
        LAST_RESET = now
    
    API_CALLS_24H += 1

async def process_system(system, influx: InfluxWrapper):
    """
    Extracts data from a system object and writes to InfluxDB.
    """
    track_api_call()

    tags = {
        "system_id": system.id,
        "system_name": system.system_name or "Unknown"
    }

    # System Data (from extra_fields)
    # system.extra_fields['outdoor_temperature']
    # system.extra_fields['outdoor_temperature_average24h']
    # system.extra_fields['system_flow_temperature']
    # system.extra_fields['system_water_pressure']
    
    system_fields = {}
    extra_fields = getattr(system, "extra_fields", {}) or {}
    
    if "outdoor_temperature" in extra_fields:
        system_fields["outdoor_temperature"] = float(extra_fields["outdoor_temperature"])
        
    if "outdoor_temperature_average24h" in extra_fields:
        system_fields["outdoor_temperature_average24h"] = float(extra_fields["outdoor_temperature_average24h"])
        
    if "system_flow_temperature" in extra_fields:
        system_fields["system_flow_temperature"] = float(extra_fields["system_flow_temperature"])
        
    if "system_water_pressure" in extra_fields:
        system_fields["system_water_pressure"] = float(extra_fields["system_water_pressure"])

    # Configuration Data
    # system.configuration['system']['adaptive_heating_curve']
    if getattr(system, "configuration", None) and isinstance(system.configuration, dict):
        sys_config = system.configuration.get("system", {})
        if "adaptive_heating_curve" in sys_config:
             system_fields["adaptive_heating_curve"] = bool(sys_config["adaptive_heating_curve"])
        # User asked for 'heating_curve' in system config, likely meaning adaptive_heating_curve or the one in circuits.
        # Just in case it appears there:
        if "heating_curve" in sys_config:
             system_fields["heating_curve"] = float(sys_config["heating_curve"])

    if system_fields:
        influx.write_point("vaillant_system", system_fields, tags)

    # Zones (from system.state['zones'])
    # desired_room_temperature_setpoint_heating
    # desired_room_temperature_setpoint
    if getattr(system, "state", None) and isinstance(system.state, dict):
        zones = system.state.get("zones", [])
        for zone in zones:
            zone_tags = tags.copy()
            # Tag with index of the zone
            if "index" in zone:
                zone_tags["zone_index"] = str(zone["index"])
            
            fields = {}
            if "desired_room_temperature_setpoint_heating" in zone:
                 fields["desired_room_temperature_setpoint_heating"] = float(zone["desired_room_temperature_setpoint_heating"])
            
            if "desired_room_temperature_setpoint" in zone:
                 fields["desired_room_temperature_setpoint"] = float(zone["desired_room_temperature_setpoint"])

            if fields:
                influx.write_point("vaillant_zones", fields, zone_tags)

        # Circuits (from system.state['circuits'] AND system.configuration['circuits'])
        # current_circuit_flow_temperature (state)
        # heating_circuit_flow_setpoint (state)
        # heating_curve (configuration)
        circuits_state = system.state.get("circuits", [])
        circuits_config = {}
        if getattr(system, "configuration", None) and isinstance(system.configuration, dict):
            for c in system.configuration.get("circuits", []):
                if "index" in c:
                    circuits_config[c["index"]] = c

        for circuit in circuits_state:
            circuit_tags = tags.copy()
            c_idx = circuit.get("index")
            # Tag with index of the circuit
            if c_idx is not None:
                circuit_tags["circuit_index"] = str(c_idx)
            
            fields = {}
            if "current_circuit_flow_temperature" in circuit:
                fields["current_circuit_flow_temperature"] = float(circuit["current_circuit_flow_temperature"])
            
            if "heating_circuit_flow_setpoint" in circuit:
                 fields["heating_circuit_flow_setpoint"] = float(circuit["heating_circuit_flow_setpoint"])
            
            # Try to get heating_curve from configuration matching index
            if c_idx is not None and c_idx in circuits_config:
                c_conf = circuits_config[c_idx]
                if "heating_curve" in c_conf:
                    fields["heating_curve"] = float(c_conf["heating_curve"])
            
            # Fallback if user added it to state manually (though likely not there)
            if "heating_curve" in circuit:
                 fields["heating_curve"] = float(circuit["heating_curve"])

            if fields:
                influx.write_point("vaillant_circuits", fields, circuit_tags)

        # DHW (from system.state['dhw'])
        # current_dhw_temperature
        dhw_list = system.state.get("dhw", [])
        for dhw in dhw_list:
            dhw_tags = tags.copy()
            # Tag with index (dhw usually uses index too)
            if "index" in dhw:
                dhw_tags["dhw_index"] = str(dhw["index"])
            
            fields = {}
            if "current_dhw_temperature" in dhw:
                fields["current_dhw_temperature"] = float(dhw["current_dhw_temperature"])
            
            if fields:
                influx.write_point("vaillant_dhw", fields, dhw_tags)


async def main():
    Config.validate()
    
    influx = InfluxWrapper()
    influx.connect()

    vaillant = VaillantClient()
    
    logger.info(f"Starting Vaillant Data Capture (Dry Run: {Config.VAILLANT_DRYRUN})")
    
    # Poll loop
    while not SHUTDOWN:
        start_time = datetime.now()
        logger.info(f"Starting poll at {start_time}")
        
        try:
            async for system in vaillant.get_systems():
                logger.info(f"Processing system: {system.system_name} ({system.id})")
                
                if Config.VAILLANT_DRYRUN:
                    if hasattr(system, "model_dump_json"):
                         logger.info(f"[DRY RUN - FULL RESPONSE]\n{system.model_dump_json(indent=4)}")
                    elif hasattr(system, "json"):
                         logger.info(f"[DRY RUN - FULL RESPONSE]\n{system.json(indent=4)}")
                    else:
                         logger.info(f"[DRY RUN - FULL RESPONSE] {system}")

                await process_system(system, influx)
                
        except Exception as e:
            logger.error(f"Error during polling: {e}")
            if not Config.VAILLANT_DRYRUN:
                influx.write_point("vaillant_errors", {"message": str(e), "type": "poll_failure"}, {})
        
        logger.info(f"API Calls in last 24h: {API_CALLS_24H}")

        # Calculate sleep time
        elapsed = (datetime.now() - start_time).total_seconds() * 1000
        sleep_ms = max(0, Config.VAILLANT_POLL_INTERVAL - elapsed)
        
        logger.info(f"Poll finished. Sleeping for {sleep_ms/1000} seconds...")
        
        # Sleep in chunks to allow graceful shutdown
        sleep_seconds = sleep_ms / 1000
        while sleep_seconds > 0 and not SHUTDOWN:
            await asyncio.sleep(min(1, sleep_seconds))
            sleep_seconds -= 1

    await vaillant.close()
    influx.close()
    logger.info("Shutdown complete.")

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
