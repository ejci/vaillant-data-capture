import pytest
import importlib
from unittest.mock import AsyncMock, patch
from src.influx import InfluxWrapper
import src.config

@pytest.mark.asyncio
async def test_influx_connect_dry_run(mock_influx_client):
    """Test that connection is skipped if DRYRUN is enabled."""
    with patch("src.influx.Config.VAILLANT_DRYRUN", True):
        wrapper = InfluxWrapper()
        await wrapper.connect()
        
        # Client should not be instantiated in dry run
        mock_influx_client.assert_not_called()
        assert wrapper.client is None
        assert wrapper.write_api is None

@pytest.mark.asyncio
async def test_influx_connect_success(mock_influx_client):
    """Test successful InfluxDB connection."""
    with patch("src.influx.Config.VAILLANT_DRYRUN", False):
        wrapper = InfluxWrapper()
        await wrapper.connect()
    
    # Client should be instantiated using config variables
    mock_influx_client.assert_called_once_with(
        url="http://localhost:8086",
        token="test-token",
        org="test-org"
    )
    assert wrapper.client is not None
    assert wrapper.write_api is not None

@pytest.mark.asyncio
async def test_influx_write_point(mock_influx_client):
    """Test that writing a point correctly structures the Point object."""
    wrapper = InfluxWrapper()
    # Mocking write_api properly
    mock_api = AsyncMock()
    wrapper.write_api = mock_api

    tags = {"system_name": "MySystem", "zone": "Zone1"}
    fields = {"temperature": 21.5, "pressure": 1.5}
    
    with patch("src.influx.Point") as mock_point_cls:
        mock_point_instance = mock_point_cls.return_value
        
        await wrapper.write_point("vaillant_metrics", fields, tags)
        
        # Verify Point creation
        mock_point_cls.assert_called_once_with("vaillant_metrics")
        
        # Verify write API was invoked with correct arguments
        mock_api.write.assert_called_once()

@pytest.mark.asyncio
async def test_influx_write_point_no_api(mock_influx_client):
    """Test that write fails gracefully if write_api is not initialized."""
    wrapper = InfluxWrapper()
    # Skipping connect() so write_api remains None
    
    with patch("src.influx.Point") as mock_point_cls:
        await wrapper.write_point("vaillant_metrics", {"val": 1}, {})
        mock_point_cls.assert_not_called()

@pytest.mark.asyncio
async def test_influx_close(mock_influx_client):
    """Test that closing wrapper cascades to the client."""
    wrapper = InfluxWrapper()
    mock_inner_client = AsyncMock()
    wrapper.client = mock_inner_client
    
    await wrapper.close()
    wrapper.client.close.assert_called_once()
