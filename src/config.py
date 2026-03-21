import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """
    Application configuration class.
    Loads and validates environment variables.
    """
    # Vaillant API Configuration
    VAILLANT_BRAND = os.getenv("VAILLANT_BRAND", "vaillant")
    VAILLANT_COUNTRY = os.getenv("VAILLANT_COUNTRY", "netherlands")
    VAILLANT_EMAIL = os.getenv("VAILLANT_EMAIL")
    VAILLANT_PASSWORD = os.getenv("VAILLANT_PASSWORD")
    
    try:
        VAILLANT_POLL_INTERVAL = int(os.getenv("VAILLANT_POLL_INTERVAL", "600000")) # 10 mins
    except ValueError:
        VAILLANT_POLL_INTERVAL = 600000
        
    VAILLANT_DRYRUN = os.getenv("VAILLANT_DRYRUN", "false").lower() == "true"
    VAILLANT_LOG_LEVEL = os.getenv("VAILLANT_LOG_LEVEL", "info")

    # InfluxDB Configuration
    INFLUX_URL = os.getenv("INFLUX_URL", "http://localhost:8086")
    INFLUX_TOKEN = os.getenv("INFLUX_TOKEN")
    INFLUX_ORG = os.getenv("INFLUX_ORG")
    INFLUX_BUCKET = os.getenv("INFLUX_BUCKET")

    @classmethod
    def validate(cls) -> None:
        """
        Validates that all required environment variables are set.
        Raises ValueError if any are missing.
        """
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
