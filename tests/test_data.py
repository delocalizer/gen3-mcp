"""Tests for the Gen3Service"""

import pytest

from gen3_mcp import Gen3SchemaError
from gen3_mcp.data import Gen3Service


@pytest.mark.asyncio
async def test_get_schema_full_caching(mock_client, config):
    """Test that full schema is cached properly"""
    service = Gen3Service(mock_client, config)

    # First call should hit the client
    schema1 = await service.get_schema_full()
    assert mock_client.get_json.call_count == 1

    # Second call should use cache
    schema2 = await service.get_schema_full()
    assert mock_client.get_json.call_count == 1  # No additional calls
    assert schema1 == schema2


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


#@pytest.mark.asyncio
#async def test_get_schema_summary(mock_client, config):
#    """Test schema summary generation"""
#    service = Gen3Service(mock_client, config)
#
#    summary = await service.get_schema_summary()
#
#    assert "total_entities" in summary
#    assert "entity_names" in summary
#    assert "entities_by_category" in summary
#    assert summary["total_entities"] == 3
#    assert "subject" in summary["entity_names"]
#    assert "sample" in summary["entity_names"]
#    assert "study" in summary["entity_names"]


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


@pytest.mark.asyncio
async def test_get_entity_context_valid_entity(mock_client, config):
    """Test entity context for valid entity"""
    service = Gen3Service(mock_client, config)

    result = await service.get_entity_context("subject")

    assert result["entity_name"] == "subject"
    assert result["exists"] is True
    assert "schema_summary" in result
    assert "hierarchical_position" in result
    assert "graphql_fields" in result
    assert "query_patterns" in result
    assert "data_flow_position" in result

    # Check schema summary
    schema_summary = result["schema_summary"]
    assert "title" in schema_summary
    assert "description" in schema_summary
    assert "category" in schema_summary
    assert "total_properties" in schema_summary

    # Check hierarchical position
    hierarchical_position = result["hierarchical_position"]
    assert "parents" in hierarchical_position
    assert "children" in hierarchical_position
    assert "parent_count" in hierarchical_position
    assert "child_count" in hierarchical_position
    assert isinstance(hierarchical_position["parents"], list)
    assert isinstance(hierarchical_position["children"], list)

    # Check GraphQL fields
    graphql_fields = result["graphql_fields"]
    assert "backref_fields" in graphql_fields
    assert "available_as_backref" in graphql_fields
    assert "direct_fields" in graphql_fields
    assert "system_fields" in graphql_fields
    assert isinstance(graphql_fields["direct_fields"], list)
    assert "id" in graphql_fields["direct_fields"]

    # Check query patterns
    query_patterns = result["query_patterns"]
    assert "basic_query" in query_patterns
    assert "with_relationships" in query_patterns
    assert "usage_examples" in query_patterns
    assert "subject" in query_patterns["basic_query"]

    # Check data flow position
    data_flow_position = result["data_flow_position"]
    assert "position" in data_flow_position
    assert "description" in data_flow_position
    assert data_flow_position["position"] in ["root", "leaf", "intermediate"]


@pytest.mark.asyncio
async def test_get_entity_context_relationships(mock_client, config):
    """Test entity context relationship analysis"""
    service = Gen3Service(mock_client, config)

    result = await service.get_entity_context("subject")

    # Subject should have children (samples) based on our mock schema
    hierarchical_position = result["hierarchical_position"]
    assert hierarchical_position["child_count"] > 0

    # Check that children are properly structured
    children = hierarchical_position["children"]
    assert len(children) > 0
    
    for child in children:
        assert "entity" in child
        assert "relationship" in child
        assert "multiplicity" in child
        assert "required" in child
        assert "backref_field" in child


@pytest.mark.asyncio
async def test_entity_name_suggestions(mock_client, config):
    """Test entity name suggestion functionality"""
    service = Gen3Service(mock_client, config)

    # Test with a similar but incorrect entity name
    full_schema = await service.get_schema_full()
    suggestions = service._get_entity_name_suggestions("subj", full_schema)

    assert isinstance(suggestions, list)
    assert len(suggestions) > 0
    
    # Should suggest "subject" for "subj"
    suggestion_names = [s["name"] for s in suggestions]
    assert "subject" in suggestion_names
    
    # Check suggestion structure
    for suggestion in suggestions:
        assert "name" in suggestion
        assert "similarity" in suggestion
        assert "category" in suggestion
        assert 0 <= suggestion["similarity"] <= 1


@pytest.mark.asyncio
async def test_generate_query_patterns(mock_client, config):
    """Test query pattern generation"""
    service = Gen3Service(mock_client, config)

    # Mock hierarchical data
    parents = [
        {
            "entity": "study",
            "relationship": "member_of",
            "backref_field": "subjects"
        }
    ]
    
    children = [
        {
            "entity": "sample",
            "relationship": "related_to",
            "backref_field": "samples"
        }
    ]

    patterns = service._generate_query_patterns("subject", parents, children)

    assert "basic_query" in patterns
    assert "with_relationships" in patterns
    assert "usage_examples" in patterns
    assert isinstance(patterns["with_relationships"], list)
    assert isinstance(patterns["usage_examples"], list)

    # Check basic query structure
    basic_query = patterns["basic_query"]
    assert "subject" in basic_query
    assert "id" in basic_query
    assert "submitter_id" in basic_query

    # Check relationship patterns if children exist
    if children:
        assert len(patterns["with_relationships"]) > 0
        rel_pattern = patterns["with_relationships"][0]
        assert "description" in rel_pattern
        assert "query" in rel_pattern
        assert "target_entity" in rel_pattern


@pytest.mark.asyncio
async def test_determine_data_flow_position(mock_client, config):
    """Test data flow position determination"""
    service = Gen3Service(mock_client, config)

    # Test root entity (no parents)
    root_position = service._determine_data_flow_position([], [{"entity": "sample"}])
    assert root_position["position"] == "root"
    assert "description" in root_position

    # Test leaf entity (no children)
    leaf_position = service._determine_data_flow_position([{"entity": "subject"}], [])
    assert leaf_position["position"] == "leaf"

    # Test intermediate entity
    intermediate_position = service._determine_data_flow_position(
        [{"entity": "study"}], [{"entity": "sample"}]
    )
    assert intermediate_position["position"] == "intermediate"
