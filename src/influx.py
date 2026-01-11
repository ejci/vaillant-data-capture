from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from src.config import Config
from src.logger import logger

class InfluxWrapper:
    def __init__(self):
        self.dry_run = Config.VAILLANT_DRYRUN
        self.client = None
        self.write_api = None

    def connect(self):
        if self.dry_run:
            logger.info("DRY RUN: Skipping InfluxDB connection.")
            return

        try:
            self.client = InfluxDBClient(
                url=Config.INFLUX_URL,
                token=Config.INFLUX_TOKEN,
                org=Config.INFLUX_ORG
            )
            self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
            logger.info(f"Connected to InfluxDB at {Config.INFLUX_URL}")
        except Exception as e:
            logger.error(f"Failed to connect to InfluxDB: {e}")
            raise

    def write_point(self, measurement: str, fields: dict, tags: dict = None):
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

            self.write_api.write(bucket=Config.INFLUX_BUCKET, org=Config.INFLUX_ORG, record=point)
            logger.debug(f"Written point to {measurement}")
        except Exception as e:
             logger.error(f"Error writing to InfluxDB: {e}")

    def close(self):
        if self.client:
            self.client.close()
