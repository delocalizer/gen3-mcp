"""Tests for main module functions"""

from unittest.mock import AsyncMock, patch

import pytest

from gen3_mcp.main import cleanup, create_mcp_server, get_client


def test_mcp_server_creation():
    """Test that MCP server can be created"""
    mcp = create_mcp_server()
    assert mcp is not None
    assert mcp.name == "gen3"


@pytest.mark.asyncio
async def test_get_client():
    """Test client creation and reuse"""
    from gen3_mcp import main

    # Reset global state
    main._config = None
    main._client = None

    with patch("gen3_mcp.main.Gen3Client") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client

        # First call should create client
        client1 = await get_client()
        assert client1 is mock_client
        mock_client.__aenter__.assert_called_once()

        # Second call should reuse client
        client2 = await get_client()
        assert client2 is client1
        assert mock_client.__aenter__.call_count == 1  # Should not be called again

    # Clean up
    main._client = None
    main._config = None


@pytest.mark.asyncio
async def test_get_client_initialization():
    """Test that get_client properly initializes config and client"""
    from gen3_mcp import main

    # Reset global state
    main._config = None
    main._client = None

    with patch("gen3_mcp.main.Gen3Client") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client

        client = await get_client()
        assert client is mock_client

        # Verify client was properly initialized
        mock_client_class.assert_called_once()
        mock_client.__aenter__.assert_called_once()

        # Verify global state is set
        assert main._client is mock_client
        assert main._config is not None

    # Clean up
    main._client = None
    main._config = None


@pytest.mark.asyncio
async def test_cleanup():
    """Test cleanup function"""
    from gen3_mcp import main

    mock_client = AsyncMock()
    main._client = mock_client

    await cleanup()

    mock_client.__aexit__.assert_called_once()
    assert main._client is None


@pytest.mark.asyncio
async def test_cleanup_with_no_client():
    """Test cleanup when no client exists"""
    from gen3_mcp import main

    main._client = None

    # Should not raise any errors
    await cleanup()


@pytest.mark.asyncio
async def test_cleanup_with_error():
    """Test cleanup handles errors gracefully"""
    from gen3_mcp import main

    mock_client = AsyncMock()
    mock_client.__aexit__.side_effect = Exception("Cleanup error")
    main._client = mock_client

    # Should not raise exception
    await cleanup()

    # Client should still be set to None
    assert main._client is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
