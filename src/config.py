import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Vaillant
    VAILLANT_BRAND = os.getenv("VAILLANT_BRAND", "vaillant")
    VAILLANT_COUNTRY = os.getenv("VAILLANT_COUNTRY", "netherlands")
    VAILLANT_EMAIL = os.getenv("VAILLANT_EMAIL")
    VAILLANT_PASSWORD = os.getenv("VAILLANT_PASSWORD")
    VAILLANT_POLL_INTERVAL = int(os.getenv("VAILLANT_POLL_INTERVAL", "600000")) # 10 mins
    VAILLANT_DRYRUN = os.getenv("VAILLANT_DRYRUN", "false").lower() == "true"
    VAILLANT_LOG_LEVEL = os.getenv("VAILLANT_LOG_LEVEL", "info")

    # InfluxDB
    INFLUX_URL = os.getenv("INFLUX_URL", "http://localhost:8086")
    INFLUX_TOKEN = os.getenv("INFLUX_TOKEN")
    INFLUX_ORG = os.getenv("INFLUX_ORG")
    INFLUX_BUCKET = os.getenv("INFLUX_BUCKET")

    @classmethod
    def validate(cls):
        required = [
            'VAILLANT_EMAIL', 'VAILLANT_PASSWORD', 
            'INFLUX_TOKEN', 'INFLUX_ORG', 'INFLUX_BUCKET'
        ]
        
        # If dry run, influx vars might not be strictly needed, but let's assume valid config is good practice
        # unless explicitly relaxed.
        if cls.VAILLANT_DRYRUN:
             required = ['VAILLANT_EMAIL', 'VAILLANT_PASSWORD']

        missing = [key for key in required if not getattr(cls, key)]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
