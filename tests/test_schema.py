"""Tests for the SchemaService"""

import pytest

from gen3_mcp.schema import SchemaService


@pytest.mark.asyncio
async def test_get_schema_full_caching(mock_client, config):
    """Test that full schema is cached properly"""
    service = SchemaService(mock_client, config)

    # First call should hit the client
    schema1 = await service.get_schema_full()
    assert mock_client.get_json.call_count == 1

    # Second call should use cache
    schema2 = await service.get_schema_full()
    assert mock_client.get_json.call_count == 1  # No additional calls
    assert schema1 == schema2


@pytest.mark.asyncio
async def test_schema_service_cache_ttl(mock_client, config):
    """Test that cache respects TTL settings"""
    import time

    # Set very short TTL for testing
    config.schema_cache_ttl = 0.1  # 100ms
    service = SchemaService(mock_client, config)

    # First call
    schema1 = await service.get_schema_full()
    assert mock_client.get_json.call_count == 1

    # Immediate second call should use cache
    schema2 = await service.get_schema_full()
    assert mock_client.get_json.call_count == 1
    assert schema1 == schema2

    # Wait for cache to expire
    time.sleep(0.15)

    # Third call should fetch again
    await service.get_schema_full()
    assert mock_client.get_json.call_count == 2


@pytest.mark.asyncio
async def test_schema_service_initialization(mock_client, config):
    """Test SchemaService initialization"""
    service = SchemaService(mock_client, config)

    assert service.client is mock_client
    assert service.config is config
    assert service.cache_ttl == config.schema_cache_ttl
    assert isinstance(service._cache, dict)
    assert isinstance(service._cache_timestamps, dict)


@pytest.mark.asyncio
async def test_cache_validity_check(mock_client, config):
    """Test internal cache validity checking"""
    service = SchemaService(mock_client, config)

    # Non-existent key should be invalid
    assert not service._is_cache_valid("nonexistent_key")

    # Add something to cache
    service._update_cache("test_key", {"test": "data"})

    # Should be valid immediately
    assert service._is_cache_valid("test_key")

    # Check that cache contains the data
    assert service._cache["test_key"] == {"test": "data"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
