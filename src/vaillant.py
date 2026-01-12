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
        # Close existing session if it exists to prevent leakage
        if self.api and hasattr(self.api, "aiohttp_session") and self.api.aiohttp_session:
            await self.api.aiohttp_session.close()

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
        
        # Retry logic for expired tokens (401)
        max_retries = 1
        for attempt in range(max_retries + 1):
            try:
                async for system in self.api.get_systems(include_diagnostic_trouble_codes=True):
                    yield system
                break # Success, exit loop
            except Exception as e:
                # Check for 401 Unauthorized in the exception message
                is_unauthorized = "401" in str(e) or "Unauthorized" in str(e)
                
                if is_unauthorized and attempt < max_retries:
                    logger.warning(f"Received 401 Unauthorized (Attempt {attempt + 1}). Re-authenticating...")
                    await self.initialize()
                else:
                    # Not a 401 or max retries exceeded
                    raise e

    async def close(self):
        if self.api and hasattr(self.api, "aiohttp_session") and self.api.aiohttp_session:
            await self.api.aiohttp_session.close()
