import logging
from myPyllant.api import MyPyllantAPI
from myPyllant.models import System, Device
from src.config import Config
from src.logger import logger

class VaillantClient:
    def __init__(self):
        self.api = None
        # Suppress myPyllant debug logs if needed as they can be verbose
        logging.getLogger("myPyllant").setLevel(logging.WARNING)

    async def initialize(self):
        logger.info(f"Initializing Vaillant API for user {Config.VAILLANT_EMAIL}")
        try:
            self.api = MyPyllantAPI(
                username=Config.VAILLANT_EMAIL,
                password=Config.VAILLANT_PASSWORD,
                brand=Config.VAILLANT_BRAND,
                country=Config.VAILLANT_COUNTRY
            )
            await self.api.login()
            logger.info("Login successful")
        except Exception as e:
             logger.error(f"Failed to login to Vaillant: {e}")
             raise

    async def get_systems(self):
        if not self.api:
            await self.initialize()
        
        async for system in self.api.get_systems(include_diagnostic_trouble_codes=True):
            yield system

    async def close(self):
         # myPyllant uses aiohttp session managed internally, usually needs closing if exposed, 
         # but check library. It often closes on context exit or explicit close if available.
         # Assuming clean shutdown isn't strictly enforced by specific method in current version,
         # but standard is good practice.
         pass
