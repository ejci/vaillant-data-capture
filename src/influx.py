import typing
from influxdb_client.client.influxdb_client_async import InfluxDBClientAsync
from influxdb_client import Point
from src.config import Config
from src.logger import logger

class InfluxWrapper:
    """
    Wrapper around the asynchronous InfluxDB client.
    Handles connection setup and writing points without blocking the async event loop.
    """
    def __init__(self):
        self.dry_run = Config.VAILLANT_DRYRUN
        self.client: typing.Optional[InfluxDBClientAsync] = None
        self.write_api = None

    async def connect(self) -> None:
        """Opens the asynchronous connection to InfluxDB."""
        if self.dry_run:
            logger.info("DRY RUN: Skipping InfluxDB connection.")
            return

        try:
            self.client = InfluxDBClientAsync(
                url=Config.INFLUX_URL,
                token=Config.INFLUX_TOKEN,
                org=Config.INFLUX_ORG
            )
            # The async client's write_api doesn't take SYNCHRONOUS
            self.write_api = self.client.write_api()
            logger.info(f"Connected to InfluxDB at {Config.INFLUX_URL}")
        except Exception as e:
            logger.error(f"Failed to connect to InfluxDB: {e}")
            raise

    async def write_point(self, measurement: str, fields: dict, tags: typing.Optional[dict] = None) -> None:
        """
        Writes a single measurement point to InfluxDB asynchronously.
        
        :param measurement: The name of the measurement table.
        :param fields: A dictionary of key-value pairs representing the fields.
        :param tags: An optional dictionary of key-value pairs representing tags.
        """
        if self.dry_run:
            logger.info(f"[DRY RUN] Would write to {measurement} | Tags: {tags} | Fields: {fields}")
            return

        if not self.write_api:
             logger.warning("Write API not initialized. Skipping write.")
             return

        try:
            point = Point(measurement)
            if tags:
                for key, value in tags.items():
                    point.tag(key, value)
            
            for key, value in fields.items():
                point.field(key, value)

            await self.write_api.write(bucket=Config.INFLUX_BUCKET, org=Config.INFLUX_ORG, record=point)
            logger.debug(f"Written point to {measurement}")
        except Exception as e:
             logger.error(f"Error writing to InfluxDB: {e}")

    async def close(self) -> None:
        """Closes the InfluxDB client connection."""
        if self.client:
            await self.client.close()
