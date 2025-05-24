"""Tests for Tools"""

import pytest

from gen3_mcp.tools import Tools


@pytest.mark.asyncio
async def test_schema_operations(mock_client, config):
    """Test schema operations through Tools"""
    tools = Tools(mock_client, config)

    # Test schema summary
    summary = await tools.schema_summary()
    assert "total_entities" in summary
    assert summary["total_entities"] == 2

    # Test schema entities
    entities = await tools.schema_entities()
    assert "entities" in entities
    assert "subject" in entities["entities"]
    assert "sample" in entities["entities"]

    # Test entity schema
    entity_schema = await tools.schema_entity("subject")
    assert "properties" in entity_schema
    assert "gender" in entity_schema["properties"]


@pytest.mark.asyncio
async def test_data_operations(mock_client, config):
    """Test data operations through Tools"""
    tools = Tools(mock_client, config)

    # Test sample records
    sample_result = await tools.data_sample_records("subject", limit=3)
    assert "entity" in sample_result
    assert sample_result["entity"] == "subject"

    # Test field values
    field_result = await tools.data_field_values("subject", "gender", limit=10)
    assert "entity" in field_result
    assert "field" in field_result
    assert field_result["field"] == "gender"

    # Test entity exploration
    exploration = await tools.data_explore_entity_data("subject")
    assert "entity" in exploration
    assert "enum_fields" in exploration


@pytest.mark.asyncio
async def test_query_operations(mock_client, config):
    """Test query operations through Tools"""
    tools = Tools(mock_client, config)

    # Test GraphQL execution
    query = "{ subject { id submitter_id } }"
    result = await tools.query_graphql(query)
    assert "data" in result


@pytest.mark.asyncio
async def test_validation_operations(mock_client, config):
    """Test validation operations through Tools"""
    tools = Tools(mock_client, config)

    # Test query validation
    valid_query = "{ subject { id submitter_id gender } }"
    validation = await tools.validation_validate_query_fields(valid_query)
    assert validation["valid"]

    # Test field suggestions
    suggestions = await tools.validation_suggest_similar_fields("gander", "subject")
    assert suggestions["entity_exists"]

    # Test template generation
    template = await tools.validation_get_query_template("subject")
    assert template["exists"]
    assert template["template"] is not None


@pytest.mark.asyncio
async def test_explore_with_kwargs(mock_client, config):
    """Test data exploration with various kwargs"""
    tools = Tools(mock_client, config)

    # Test with field_count and limit
    result = await tools.data_explore("subject", field_count=10, limit=3)
    assert "entity" in result
    assert result["entity"] == "subject"


@pytest.mark.asyncio
async def test_detailed_entities(mock_client, config):
    """Test detailed entity listing"""
    tools = Tools(mock_client, config)

    detailed = await tools.schema_list_available_entities()

    assert "total_entities" in detailed
    assert "entities" in detailed
    assert "entities_by_category" in detailed
    assert "relationship_summary" in detailed

    # Check that subject entity is properly detailed
    assert "subject" in detailed["entities"]
    subject_details = detailed["entities"]["subject"]
    assert "title" in subject_details
    assert "description" in subject_details
    assert "category" in subject_details
    assert "properties_count" in subject_details
    assert "links" in subject_details


@pytest.mark.asyncio
async def test_tools_initialization(mock_client, config):
    """Test that tools are properly initialized"""
    tools = Tools(mock_client, config)

    assert tools.config == config
    assert tools.gen3_service is not None
    assert tools.query_service is not None

    # Test that services are connected
    assert tools.query_service.gen3_service == tools.gen3_service
    assert tools.query_service.client == mock_client
    assert tools.query_service.config == config


@pytest.mark.asyncio
async def test_error_handling(mock_client, config):
    """Test error handling in tools"""
    tools = Tools(mock_client, config)

    # Test with invalid entity
    mock_client.get_json.return_value = None

    try:
        await tools.schema_entity("nonexistent")
        raise AssertionError("Should have raised an exception")
    except Exception as e:
        assert "not found" in str(e).lower() or "failed" in str(e).lower()
