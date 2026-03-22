import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.vaillant import VaillantClient

@pytest.mark.asyncio
async def test_vaillant_initialize_login(mock_env_vars):
    """Test vaillant API login flow."""
    with patch("src.vaillant.MyPyllantAPI") as mock_api_cls:
        mock_api_instance = AsyncMock()
        mock_api_cls.return_value = mock_api_instance
        
        client = VaillantClient()
        await client.initialize()
        
        mock_api_cls.assert_called_once_with(
            username="test@example.com",
            password="password123",
            brand="vaillant",
            country="netherlands" # Assuming Vaillant brand in your config sets this by default or it's provided
        )
        mock_api_instance.login.assert_called_once()
        assert client.api == mock_api_instance

@pytest.mark.asyncio
async def test_vaillant_get_systems_success(mock_env_vars):
    """Test successfully yielding systems."""
    with patch("src.vaillant.MyPyllantAPI") as mock_api_cls:
        # Prevent get_systems from being an AsyncMock (which causes issues with async generators)
        mock_api_instance = MagicMock()
        mock_api_instance.login = AsyncMock()
        mock_api_instance.aiohttp_session = AsyncMock()
        mock_api_cls.return_value = mock_api_instance

        # Create an async generator for get_systems
        async def mock_sys_gen():
            yield "system_1"
            yield "system_2"

        mock_api_instance.get_systems.return_value = mock_sys_gen()
        
        client = VaillantClient()
        systems = [s async for s in client.get_systems()]
        
        assert len(systems) == 2
        assert systems == ["system_1", "system_2"]
        mock_api_instance.login.assert_called_once()

@pytest.mark.asyncio
async def test_vaillant_token_refresh_on_401(mock_env_vars):
    """Test the retry mechanism triggering a token refresh when encountering a 401 error."""
    with patch("src.vaillant.MyPyllantAPI") as mock_api_cls:
        mock_api_instance = MagicMock()
        # Mock the async method explicitely
        mock_api_instance.aiohttp_session = AsyncMock()
        mock_api_instance.refresh_token = AsyncMock()
        mock_api_instance.login = AsyncMock()
        mock_api_cls.return_value = mock_api_instance
        
        # Generator for side effect
        call_count = 0
        def get_systems_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            async def gen():
                if call_count == 1:
                    raise Exception("401 Unauthorized")
                yield "system_recovered"
            return gen()

        mock_api_instance.get_systems.side_effect = get_systems_effect
        
        client = VaillantClient()
        systems = [s async for s in client.get_systems()]
        
        assert len(systems) == 1
        assert systems[0] == "system_recovered"
        
        # Verify login was only called once (in initialize)
        mock_api_instance.login.assert_called_once()
        
        # Verify refresh_token was called as part of the retry logic
        mock_api_instance.refresh_token.assert_called_once()

@pytest.mark.asyncio
async def test_vaillant_token_refresh_fallback(mock_env_vars):
    """Test the retry mechanism falling back to full login if refresh fails."""
    with patch("src.vaillant.MyPyllantAPI") as mock_api_cls:
        # We have multiple MyPyllantAPI creations during fallback
        # First one fails get_systems with 401, and also fails refresh_token
        mock_api_instance_1 = MagicMock()
        mock_api_instance_1.aiohttp_session = AsyncMock()
        mock_api_instance_1.refresh_token = AsyncMock(side_effect=Exception("Refresh failed"))
        mock_api_instance_1.login = AsyncMock()
        
        mock_api_instance_2 = MagicMock()
        mock_api_instance_2.aiohttp_session = AsyncMock()
        mock_api_instance_2.login = AsyncMock()
        
        mock_api_cls.side_effect = [mock_api_instance_1, mock_api_instance_2]
        
        call_count = 0
        def get_systems_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            async def gen():
                if call_count == 1:
                    raise Exception("401 Unauthorized")
                yield "system_recovered_fallback"
            return gen()

        # Instance 1 will throw the Exception via get_systems
        mock_api_instance_1.get_systems.side_effect = get_systems_effect
        
        # Instance 2 is the fallback, will yield successfully
        mock_api_instance_2.get_systems.side_effect = get_systems_effect

        client = VaillantClient()
        systems = [s async for s in client.get_systems()]
        
        assert len(systems) == 1
        assert systems[0] == "system_recovered_fallback"

        # Verify MyPyllantAPI was instantiated twice
        assert mock_api_cls.call_count == 2
        
        # Verify the first instance tried to refresh the token and failed
        mock_api_instance_1.refresh_token.assert_called_once()
        
        # Verify the second instance performed a fresh login
        mock_api_instance_2.login.assert_called_once()

@pytest.mark.asyncio
async def test_vaillant_close(mock_env_vars):
    """Test that closing client correctly closes aiohttp_session on api."""
    with patch("src.vaillant.MyPyllantAPI") as mock_api_cls:
        mock_api_instance = MagicMock()
        mock_api_instance.aiohttp_session = AsyncMock()
        mock_api_instance.login = AsyncMock()
        mock_api_cls.return_value = mock_api_instance
        
        client = VaillantClient()
        await client.initialize()
        
        await client.close()
        mock_api_instance.aiohttp_session.close.assert_called_once()
