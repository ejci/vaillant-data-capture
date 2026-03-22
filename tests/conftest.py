import os
import pytest
from unittest.mock import AsyncMock, patch
import importlib

# Ensure we can reload the config module easily in tests
import src.config

@pytest.fixture(autouse=True)
def mock_env_vars():
    """Provides a valid set of environment variables for testing, restoring original afterwards."""
    import src.config
    
    original = {
        "VAILLANT_EMAIL": src.config.Config.VAILLANT_EMAIL,
        "VAILLANT_PASSWORD": src.config.Config.VAILLANT_PASSWORD,
        "INFLUX_URL": src.config.Config.INFLUX_URL,
        "INFLUX_TOKEN": src.config.Config.INFLUX_TOKEN,
        "INFLUX_ORG": src.config.Config.INFLUX_ORG,
        "INFLUX_BUCKET": src.config.Config.INFLUX_BUCKET,
        "VAILLANT_DRYRUN": src.config.Config.VAILLANT_DRYRUN,
        "VAILLANT_POLL_INTERVAL": src.config.Config.VAILLANT_POLL_INTERVAL,
    }
    
    src.config.Config.VAILLANT_EMAIL = "test@example.com"
    src.config.Config.VAILLANT_PASSWORD = "password123"
    src.config.Config.INFLUX_URL = "http://localhost:8086"
    src.config.Config.INFLUX_TOKEN = "test-token"
    src.config.Config.INFLUX_ORG = "test-org"
    src.config.Config.INFLUX_BUCKET = "test-bucket"
    src.config.Config.VAILLANT_DRYRUN = False
    src.config.Config.VAILLANT_POLL_INTERVAL = 600000
    
    yield
    
    for k, v in original.items():
        setattr(src.config.Config, k, v)

@pytest.fixture
def mock_influx_client():
    """Mocks the InfluxDBClientAsync to prevent real database connections."""
    with patch("src.influx.InfluxDBClientAsync") as mock_client:
        mock_instance = AsyncMock()
        mock_client.return_value = mock_instance
        
        # Mock the write_api to avoid real network calls
        mock_write_api = AsyncMock()
        mock_instance.write_api.return_value = mock_write_api
        
        yield mock_client
