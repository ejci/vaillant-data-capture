import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from main import VaillantDataCaptureApp

@pytest.fixture
def mock_app():
    """Returns an instance of VaillantDataCaptureApp with mocked dependencies."""
    with patch("main.InfluxWrapper") as mock_influx_cls, \
         patch("main.VaillantClient") as mock_vaillant_cls:
        
        mock_influx = AsyncMock()
        mock_influx_cls.return_value = mock_influx
        
        mock_vaillant = AsyncMock()
        mock_vaillant_cls.return_value = mock_vaillant
        
        app = VaillantDataCaptureApp()
        
        # Replace instances with the mocks
        app.influx = mock_influx
        app.vaillant = mock_vaillant
        
        return app

@pytest.fixture
def mock_system():
    """Returns a mocked myPyllant System object."""
    system = MagicMock()
    system.id = "sys-123"
    system.system_name = "TestSystem"
    
    # Mock system extra fields
    system.extra_fields = {
        "outdoor_temperature": 15.5,
        "system_water_pressure": 1.5,
    }
    
    # Mock configuration
    system.configuration = {
        "system": {
            "adaptive_heating_curve": True,
            "heating_curve": 1.2
        },
        "circuits": [
            {"index": 0, "heating_curve": 1.2}
        ]
    }
    
    # Mock state
    system.state = {
        "zones": [
            {
                "index": 0,
                "desired_room_temperature_setpoint_heating": 21.0,
                "desired_room_temperature_setpoint": 21.0
            }
        ],
        "circuits": [
            {
                "index": 0,
                "current_circuit_flow_temperature": 35.5,
                "heating_circuit_flow_setpoint": 40.0,
                "heating_curve": 1.2
            }
        ],
        "dhw": [
            {
                "index": 0,
                "current_dhw_temperature": 55.0
            }
        ]
    }
    
    return system

@pytest.mark.asyncio
async def test_process_system_extracts_data(mock_env_vars, mock_app, mock_system):
    """Test that processing a system correctly extracts fields and tags for InfluxDB."""
    
    await mock_app._process_system(mock_system)
    
    # Verify write_point was called 4 times (system, zone, circuit, dhw)
    assert mock_app.influx.write_point.call_count == 4
    
    # Expected base tags
    base_tags = {"system_id": "sys-123", "system_name": "TestSystem"}
    
    # Verify System Data Write
    mock_app.influx.write_point.assert_any_call(
        "vaillant_system",
        {
            "outdoor_temperature": 15.5,
            "system_water_pressure": 1.5,
            "adaptive_heating_curve": True,
            "heating_curve": 1.2
        },
        base_tags
    )
    
    # Verify Zone Data Write
    zone_tags = base_tags.copy()
    zone_tags["zone_index"] = "0"
    mock_app.influx.write_point.assert_any_call(
        "vaillant_zones",
        {
            "desired_room_temperature_setpoint_heating": 21.0,
            "desired_room_temperature_setpoint": 21.0
        },
        zone_tags
    )
    
    # Verify Circuit Data Write
    circuit_tags = base_tags.copy()
    circuit_tags["circuit_index"] = "0"
    mock_app.influx.write_point.assert_any_call(
        "vaillant_circuits",
        {
            "current_circuit_flow_temperature": 35.5,
            "heating_circuit_flow_setpoint": 40.0,
            "heating_curve": 1.2
        },
        circuit_tags
    )
    
    # Verify DHW Data Write
    dhw_tags = base_tags.copy()
    dhw_tags["dhw_index"] = "0"
    mock_app.influx.write_point.assert_any_call(
        "vaillant_dhw",
        {
            "current_dhw_temperature": 55.0
        },
        dhw_tags
    )

@pytest.mark.asyncio
async def test_process_system_partial_data(mock_env_vars, mock_app):
    """Test extraction with missing data sections to ensure it doesn't crash."""
    system = MagicMock()
    system.id = "sys-456"
    system.system_name = "PartialSystem"
    
    # Empty system
    system.extra_fields = None
    system.configuration = None
    system.state = None
    
    await mock_app._process_system(system)
    
    # No writing should occur because there are no fields to extract
    mock_app.influx.write_point.assert_not_called()

def test_api_calls_tracking(mock_app):
    """Test that the 24h API tracking resets appropriately."""
    mock_app._track_api_call()
    assert mock_app.api_calls_24h == 1
    
    # Force a time diff
    import datetime
    from datetime import timedelta
    mock_app.last_reset = datetime.datetime.now() - timedelta(hours=25)
    
    mock_app._track_api_call()
    assert mock_app.api_calls_24h == 1 # Has reset, plus 1 for this call
