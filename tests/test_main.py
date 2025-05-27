"""Tests for main module functions"""

from unittest.mock import AsyncMock, patch

import pytest

from gen3_mcp.main import (
    cleanup,
    create_mcp_server,
    get_gen3_service,
    get_query_service,
)


def test_mcp_server_creation():
    """Test that MCP server can be created"""
    mcp = create_mcp_server()
    assert mcp is not None
    assert mcp.name == "gen3"


@pytest.mark.asyncio
async def test_get_gen3_service():
    """Test SchemaService creation and reuse"""
    from gen3_mcp import main

    # Reset global state
    main._config = None
    main._client = None
    main._gen3_service = None
    main._query_service = None

    with (
        patch("gen3_mcp.main.Gen3Client") as mock_client_class,
        patch("gen3_mcp.main.SchemaService") as mock_service_class,
    ):

        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service

        # First call should create service
        service1 = await get_gen3_service()
        assert service1 is mock_service
        mock_client.__aenter__.assert_called_once()
        mock_service_class.assert_called_once()

        # Second call should reuse service
        service2 = await get_gen3_service()
        assert service2 is service1
        assert mock_client.__aenter__.call_count == 1  # Should not be called again
        assert mock_service_class.call_count == 1  # Should not be called again

    # Clean up
    main._client = None
    main._config = None
    main._gen3_service = None
    main._query_service = None


@pytest.mark.asyncio
async def test_get_query_service():
    """Test QueryService creation and reuse"""
    from gen3_mcp import main

    # Reset global state
    main._config = None
    main._client = None
    main._gen3_service = None
    main._query_service = None

    with (
        patch("gen3_mcp.main.Gen3Client") as mock_client_class,
        patch("gen3_mcp.main.SchemaService") as mock_gen3_service_class,
        patch("gen3_mcp.main.QueryService") as mock_query_service_class,
    ):

        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_gen3_service = AsyncMock()
        mock_gen3_service_class.return_value = mock_gen3_service
        mock_query_service = AsyncMock()
        mock_query_service_class.return_value = mock_query_service

        # First call should create service and its dependency
        service1 = await get_query_service()
        assert service1 is mock_query_service
        mock_client.__aenter__.assert_called_once()
        mock_gen3_service_class.assert_called_once()
        mock_query_service_class.assert_called_once_with(
            mock_client, main._config, mock_gen3_service
        )

        # Second call should reuse service
        service2 = await get_query_service()
        assert service2 is service1
        assert mock_client.__aenter__.call_count == 1  # Should not be called again
        assert mock_query_service_class.call_count == 1  # Should not be called again

    # Clean up
    main._client = None
    main._config = None
    main._gen3_service = None
    main._query_service = None


@pytest.mark.asyncio
async def test_service_dependency_order():
    """Test that QueryService properly depends on SchemaService"""
    from gen3_mcp import main

    # Reset global state
    main._config = None
    main._client = None
    main._gen3_service = None
    main._query_service = None

    with (
        patch("gen3_mcp.main.Gen3Client") as mock_client_class,
        patch("gen3_mcp.main.SchemaService") as mock_gen3_service_class,
        patch("gen3_mcp.main.QueryService") as mock_query_service_class,
    ):

        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_gen3_service = AsyncMock()
        mock_gen3_service_class.return_value = mock_gen3_service
        mock_query_service = AsyncMock()
        mock_query_service_class.return_value = mock_query_service

        # Get QueryService should automatically create SchemaService first
        await get_query_service()

        # Verify both services are created and QueryService gets SchemaService as dependency
        mock_gen3_service_class.assert_called_once()
        mock_query_service_class.assert_called_once_with(
            mock_client, main._config, mock_gen3_service
        )

        # Verify global state
        assert main._gen3_service is mock_gen3_service
        assert main._query_service is mock_query_service

    # Clean up
    main._client = None
    main._config = None
    main._gen3_service = None
    main._query_service = None


@pytest.mark.asyncio
async def test_cleanup():
    """Test cleanup function"""
    from gen3_mcp import main

    mock_client = AsyncMock()
    mock_gen3_service = AsyncMock()
    mock_query_service = AsyncMock()

    main._client = mock_client
    main._gen3_service = mock_gen3_service
    main._query_service = mock_query_service

    await cleanup()

    mock_client.__aexit__.assert_called_once()
    assert main._client is None
    assert main._gen3_service is None
    assert main._query_service is None


@pytest.mark.asyncio
async def test_cleanup_with_no_client():
    """Test cleanup when no client exists"""
    from gen3_mcp import main

    main._client = None
    main._gen3_service = None
    main._query_service = None

    # Should not raise any errors
    await cleanup()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
