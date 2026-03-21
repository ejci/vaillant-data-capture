import asyncio
import signal
from datetime import datetime, timedelta
import typing

# If myPyllant types are available we could use them, but let's stick to Any/System where possible
from myPyllant.models import System

from src.config import Config
from src.logger import logger
from src.influx import InfluxWrapper
from src.vaillant import VaillantClient

class VaillantDataCaptureApp:
    """
    Main Application class for Vaillant Data Capture.
    Encapsulates state, polling logic, and InfluxDB writes.
    """
    def __init__(self):
        self.shutdown_event = asyncio.Event()
        self.api_calls_24h = 0
        self.last_reset = datetime.now()
        self.influx = InfluxWrapper()
        self.vaillant = VaillantClient()

    def handle_shutdown(self) -> None:
        """Signal handler to trigger graceful shutdown."""
        logger.info("Received shutdown signal. Stopping...")
        self.shutdown_event.set()

    def _track_api_call(self) -> None:
        """Tracks the number of API calls made in a 24-hour period for logging purposes."""
        now = datetime.now()
        if now - self.last_reset > timedelta(hours=24):
            logger.info(f"Resetting 24h API call count. Total was: {self.api_calls_24h}")
            self.api_calls_24h = 0
            self.last_reset = now
        
        self.api_calls_24h += 1

    async def _process_system(self, system: System) -> None:
        """
        Extracts various metrics (system, zones, circuits, dhw) from a system object
        and writes them to InfluxDB.
        """
        self._track_api_call()

        tags = {
            "system_id": str(system.id),
            "system_name": system.system_name or "Unknown"
        }

        # 1. Extract System Data
        await self._extract_and_write_system_data(system, tags)

        # 2. Extract Zones Data
        await self._extract_and_write_zones_data(system, tags)

        # 3. Extract Circuits Data
        await self._extract_and_write_circuits_data(system, tags)

        # 4. Extract DHW Data
        await self._extract_and_write_dhw_data(system, tags)


    async def _extract_and_write_system_data(self, system: System, base_tags: dict) -> None:
        """Extracts and writes overall system metrics like outdoor temp and water pressure."""
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
        if getattr(system, "configuration", None) and isinstance(system.configuration, dict):
            sys_config = system.configuration.get("system", {})
            if "adaptive_heating_curve" in sys_config:
                 system_fields["adaptive_heating_curve"] = bool(sys_config["adaptive_heating_curve"])
            # Fallback/Safety check: sometimes heating_curve is in system config
            if "heating_curve" in sys_config:
                 system_fields["heating_curve"] = float(sys_config["heating_curve"])

        if system_fields:
            await self.influx.write_point("vaillant_system", system_fields, base_tags)

    async def _extract_and_write_zones_data(self, system: System, base_tags: dict) -> None:
        """Extracts and writes metrics specific to heating zones."""
        if getattr(system, "state", None) and isinstance(system.state, dict):
            zones = system.state.get("zones", [])
            for zone in zones:
                zone_tags = base_tags.copy()
                if "index" in zone:
                    zone_tags["zone_index"] = str(zone["index"])
                
                fields = {}
                if "desired_room_temperature_setpoint_heating" in zone:
                     fields["desired_room_temperature_setpoint_heating"] = float(zone["desired_room_temperature_setpoint_heating"])
                
                if "desired_room_temperature_setpoint" in zone:
                     fields["desired_room_temperature_setpoint"] = float(zone["desired_room_temperature_setpoint"])

                if fields:
                    await self.influx.write_point("vaillant_zones", fields, zone_tags)

    async def _extract_and_write_circuits_data(self, system: System, base_tags: dict) -> None:
        """Extracts and writes metrics specific to heating circuits."""
        if not getattr(system, "state", None) or not isinstance(system.state, dict):
            return

        circuits_state = system.state.get("circuits", [])
        circuits_config = {}
        
        # Heating curve often lives in configuration['circuits'], while flow temp is in state['circuits']
        if getattr(system, "configuration", None) and isinstance(system.configuration, dict):
            for c in system.configuration.get("circuits", []):
                if "index" in c:
                    circuits_config[c["index"]] = c

        for circuit in circuits_state:
            circuit_tags = base_tags.copy()
            c_idx = circuit.get("index")
            if c_idx is not None:
                circuit_tags["circuit_index"] = str(c_idx)
            
            fields = {}
            if "current_circuit_flow_temperature" in circuit:
                fields["current_circuit_flow_temperature"] = float(circuit["current_circuit_flow_temperature"])
            
            if "heating_circuit_flow_setpoint" in circuit:
                 fields["heating_circuit_flow_setpoint"] = float(circuit["heating_circuit_flow_setpoint"])
            
            # Combine configuration data using the circuit index
            if c_idx is not None and c_idx in circuits_config:
                c_conf = circuits_config[c_idx]
                if "heating_curve" in c_conf:
                    fields["heating_curve"] = float(c_conf["heating_curve"])
            
            # Fallback if present directly in state
            if "heating_curve" in circuit:
                 fields["heating_curve"] = float(circuit["heating_curve"])

            if fields:
                await self.influx.write_point("vaillant_circuits", fields, circuit_tags)

    async def _extract_and_write_dhw_data(self, system: System, base_tags: dict) -> None:
        """Extracts and writes metrics for Domestic Hot Water (DHW)."""
        if not getattr(system, "state", None) or not isinstance(system.state, dict):
            return

        dhw_list = system.state.get("dhw", [])
        for dhw in dhw_list:
            dhw_tags = base_tags.copy()
            if "index" in dhw:
                dhw_tags["dhw_index"] = str(dhw["index"])
            
            fields = {}
            if "current_dhw_temperature" in dhw:
                fields["current_dhw_temperature"] = float(dhw["current_dhw_temperature"])
            
            if fields:
                await self.influx.write_point("vaillant_dhw", fields, dhw_tags)


    async def run(self) -> None:
        """
        Main execution entry point. Connects to dependencies, handles the polling loop,
        and manages graceful shutdowns.
        """
        Config.validate()
        
        await self.influx.connect()
        
        logger.info(f"Starting Vaillant Data Capture (Dry Run: {Config.VAILLANT_DRYRUN})")
        
        # Main Poll loop
        while not self.shutdown_event.is_set():
            start_time = datetime.now()
            logger.info(f"Starting poll at {start_time}")
            
            try:
                async for system in self.vaillant.get_systems():
                    logger.info(f"Processing system: {system.system_name} ({system.id})")
                    
                    if Config.VAILLANT_DRYRUN:
                        if hasattr(system, "model_dump_json"):
                             logger.info(f"[DRY RUN - FULL RESPONSE]\n{system.model_dump_json(indent=4)}")
                        elif hasattr(system, "json"):
                             logger.info(f"[DRY RUN - FULL RESPONSE]\n{system.json(indent=4)}")
                        else:
                             logger.info(f"[DRY RUN - FULL RESPONSE] {system}")

                    await self._process_system(system)
                    
            except Exception as e:
                logger.error(f"Error during polling: {e}")
                if not Config.VAILLANT_DRYRUN:
                    await self.influx.write_point("vaillant_errors", {"message": str(e), "type": "poll_failure"}, {})
            
            logger.info(f"API Calls in last 24h: {self.api_calls_24h}")

            # Calculate sleep time
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            sleep_ms = max(0, Config.VAILLANT_POLL_INTERVAL - elapsed)
            
            logger.info(f"Poll finished. Sleeping for {sleep_ms/1000} seconds...")
            
            # Wait for either the sleep duration or the shutdown event
            try:
                await asyncio.wait_for(self.shutdown_event.wait(), timeout=sleep_ms/1000.0)
            except asyncio.TimeoutError:
                # Timeout is expected; means we completed our sleep without a shutdown signal
                pass

        # Cleanup
        await self.vaillant.close()
        await self.influx.close()
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    app = VaillantDataCaptureApp()
    
    # Register signal handlers for graceful shutdown (SIGINT = Ctrl+C, SIGTERM = Docker stop)
    loop = asyncio.get_event_loop()
    try:
        loop.add_signal_handler(signal.SIGINT, app.handle_shutdown)
        loop.add_signal_handler(signal.SIGTERM, app.handle_shutdown)
    except NotImplementedError:
        # Windows doesn't support add_signal_handler natively in some loops
        signal.signal(signal.SIGINT, lambda sig, frame: app.handle_shutdown())
        signal.signal(signal.SIGTERM, lambda sig, frame: app.handle_shutdown())

    try:
        loop.run_until_complete(app.run())
    except KeyboardInterrupt:
        pass
