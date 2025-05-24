"""Tests for the Gen3Service"""

import pytest

from gen3_mcp import Gen3SchemaError
from gen3_mcp.data import Gen3Service


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
async def test_get_entity_schema_not_found(mock_client, config):
    """Test Gen3SchemaError is raised for missing entities"""
    mock_client.get_json.return_value = None
    service = Gen3Service(mock_client, config)

    with pytest.raises(Gen3SchemaError):
        await service.get_entity_schema("nonexistent")


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


@pytest.mark.asyncio
async def test_get_schema_summary(mock_client, config):
    """Test schema summary generation"""
    service = Gen3Service(mock_client, config)

    summary = await service.get_schema_summary()

    assert "total_entities" in summary
    assert "entity_names" in summary
    assert "entities_by_category" in summary
    assert summary["total_entities"] == 2
    assert "subject" in summary["entity_names"]
    assert "sample" in summary["entity_names"]


@pytest.mark.asyncio
async def test_get_detailed_entities(mock_client, config):
    """Test detailed entity information"""
    service = Gen3Service(mock_client, config)

    detailed = await service.get_detailed_entities()

    assert "total_entities" in detailed
    assert "entities" in detailed
    assert "entities_by_category" in detailed
    assert "relationship_summary" in detailed
    assert detailed["total_entities"] == 2

    # Check subject entity details
    assert "subject" in detailed["entities"]
    subject = detailed["entities"]["subject"]
    assert "title" in subject
    assert "description" in subject
    assert "properties_count" in subject


@pytest.mark.asyncio
async def test_get_entity_names(mock_client, config):
    """Test entity name retrieval"""
    service = Gen3Service(mock_client, config)

    entity_names = await service.get_entity_names()

    assert isinstance(entity_names, list)
    assert "subject" in entity_names
    assert "sample" in entity_names
    assert len(entity_names) == 2


@pytest.mark.asyncio
async def test_cache_clear(mock_client, config):
    """Test cache clearing functionality"""
    service = Gen3Service(mock_client, config)

    # Add something to cache
    service._update_cache("test", "value")
    assert "test" in service._cache

    # Clear cache
    service.clear_cache()
    assert len(service._cache) == 0
    assert len(service._cache_timestamps) == 0
