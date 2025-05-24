"""Tests for the Gen3Service"""

import pytest
import time
from unittest.mock import AsyncMock
from gen3_mcp.service import Gen3Service
from gen3_mcp.exceptions import Gen3SchemaError


@pytest.mark.asyncio
async def test_get_full_schema_caching(mock_client, config):
    """Test that full schema is cached properly"""
    service = Gen3Service(mock_client, config)

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
    service = Gen3Service(mock_client, config)

    # Mock full schema in cache
    service._cache["full_schema"] = {"subject": {}, "sample": {}}
    service._cache_timestamps["full_schema"] = time.time()

    assert await service.entity_exists("subject") == True
    assert await service.entity_exists("nonexistent") == False


@pytest.mark.asyncio
async def test_get_entity_schema_not_found(mock_client, config):
    """Test Gen3SchemaError is raised for missing entities"""
    mock_client.get_json.return_value = None
    service = Gen3Service(mock_client, config)

    with pytest.raises(Gen3SchemaError):
        await service.get_entity_schema("nonexistent")


@pytest.mark.asyncio
async def test_get_schema_summary(mock_client, config):
    """Test schema summary generation"""
    service = Gen3Service(mock_client, config)

    summary = await service.get_schema_summary()

    assert "total_entities" in summary
    assert "entity_names" in summary
    assert "entities_by_category" in summary
    assert summary["total_entities"] == 2  # subject and sample from mock
    assert "subject" in summary["entity_names"]
    assert "sample" in summary["entity_names"]


@pytest.mark.asyncio
async def test_get_sample_records(mock_client, config):
    """Test sample record retrieval"""
    service = Gen3Service(mock_client, config)

    result = await service.get_sample_records("subject", limit=3)

    assert "entity" in result
    assert "sample_records" in result
    assert result["entity"] == "subject"
    assert mock_client.post_json.called


@pytest.mark.asyncio
async def test_explore_entity_data(mock_client, config):
    """Test comprehensive entity exploration"""
    service = Gen3Service(mock_client, config)

    result = await service.explore_entity_data("subject")

    assert "entity" in result
    assert "schema_info" in result
    assert "enum_fields" in result
    assert result["entity"] == "subject"
    assert len(result["enum_fields"]) > 0  # Should find gender enum


@pytest.mark.asyncio
async def test_cache_functionality(mock_client, config):
    """Test basic cache functionality"""
    service = Gen3Service(mock_client, config)

    # Test cache validity
    assert not service._is_cache_valid("nonexistent")
    
    # Test cache update
    service._update_cache("test_key", "test_value")
    assert service._cache["test_key"] == "test_value"
    assert service._is_cache_valid("test_key")

    # Test cache clear
    service.clear_cache()
    assert len(service._cache) == 0
    assert len(service._cache_timestamps) == 0


@pytest.mark.asyncio
async def test_optimal_field_selection(mock_client, config):
    """Test intelligent field selection"""
    service = Gen3Service(mock_client, config)
    
    # Get the subject schema from our mock data
    from tests.conftest import SUBJECT_SCHEMA
    
    fields = service._select_optimal_fields(SUBJECT_SCHEMA, 10)
    
    assert "id" in fields
    assert "submitter_id" in fields
    assert "type" in fields
    assert "gender" in fields  # Should include enum field
    assert len(fields) <= 10
