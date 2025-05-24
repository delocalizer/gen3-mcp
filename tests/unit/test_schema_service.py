"""Tests for SchemaService"""

import pytest
import time
from unittest.mock import AsyncMock
from gen3_mcp.schema.service import SchemaService
from gen3_mcp.exceptions import EntityNotFoundError, SchemaFetchError


@pytest.mark.asyncio
async def test_get_full_schema_caching(mock_client, config):
    """Test that full schema is cached properly"""
    service = SchemaService(mock_client, config)

    # First call should hit the client
    schema1 = await service.get_full_schema()
    assert mock_client.get_json.call_count == 1

    # Second call should use cache
    schema2 = await service.get_full_schema()
    assert mock_client.get_json.call_count == 1  # No additional calls
    assert schema1 == schema2


@pytest.mark.asyncio
async def test_entity_exists(mock_client, config):
    """Test entity existence checking"""
    service = SchemaService(mock_client, config)

    # Mock full schema in cache
    service._cache["full_schema"] = {"subject": {}, "sample": {}}
    service._cache_timestamps["full_schema"] = time.time()

    assert await service.entity_exists("subject") == True
    assert await service.entity_exists("nonexistent") == False


@pytest.mark.asyncio
async def test_get_entity_schema_not_found(mock_client, config):
    """Test EntityNotFoundError is raised for missing entities"""
    mock_client.get_json.return_value = None
    service = SchemaService(mock_client, config)

    with pytest.raises(EntityNotFoundError):
        await service.get_entity_schema("nonexistent")


@pytest.mark.asyncio
async def test_get_schema_summary(mock_client, config):
    """Test schema summary generation"""
    service = SchemaService(mock_client, config)

    summary = await service.get_schema_summary()

    assert "total_entities" in summary
    assert "entity_names" in summary
    assert "entities_by_category" in summary
    assert summary["total_entities"] == 2  # subject and sample from mock
    assert "subject" in summary["entity_names"]
    assert "sample" in summary["entity_names"]


@pytest.mark.asyncio
async def test_cache_eviction(mock_client, config):
    """Test cache eviction when max size is reached"""
    # Create config with small cache size by modifying the existing config
    # instead of creating a new one to avoid Pydantic initialization issues
    config.max_cache_size = 2

    service = SchemaService(mock_client, config)

    # Fill cache to limit
    service._update_cache("key1", "value1")
    service._update_cache("key2", "value2")
    assert len(service._cache) == 2

    # Adding third item should evict oldest
    service._update_cache("key3", "value3")
    assert len(service._cache) == 2
    assert "key1" not in service._cache  # Should be evicted
    assert "key3" in service._cache
