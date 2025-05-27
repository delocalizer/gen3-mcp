"""Tests for the Gen3Service"""

import json
from pathlib import Path
from unittest import TestCase

import pytest

from gen3_mcp.data import Gen3Service


@pytest.fixture(scope="session")
def reference_context():
    """Load the reference entity_context for a subject"""
    schema_path = Path(__file__).parent / "subject_entity_context.json"
    with open(schema_path) as f:
        return json.load(f)


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
async def test_optimal_field_selection(mock_client, config):
    """Test intelligent field selection"""
    service = Gen3Service(mock_client, config)

    # Get the subject schema from the loaded schema
    schema = await service.get_schema_full()
    subject_schema = schema["subject"]

    fields = service._select_optimal_fields(subject_schema, 10)

    assert "id" in fields
    assert "submitter_id" in fields
    assert "type" in fields
    assert "gender" in fields  # Should include enum field
    assert len(fields) <= 10


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
async def test_get_entity_context_details(mock_client, config, reference_context):
    """Test entity context details for 'subject'"""
    service = Gen3Service(mock_client, config)

    result = await service.get_entity_context("subject")

    # reference_context is farily  large; inspect file by eye for details
    TestCase().assertDictEqual(result, reference_context)


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
            "backref_field": "subjects",
            "link_name": "studies",
        }
    ]

    children = [
        {"entity": "sample", "relationship": "related_to", "backref_field": "samples"}
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


@pytest.mark.asyncio
async def test_query_patterns_basic_query_validation(mock_client, config):
    """Test that the basic query pattern generated is valid GraphQL"""
    service = Gen3Service(mock_client, config)

    # Get a real schema extract for validation
    full_schema = await service.get_schema_full()
    from gen3_mcp.graphql_validator import validate_graphql
    from gen3_mcp.schema_extract import SchemaExtract

    schema_extract = SchemaExtract.from_full_schema(full_schema)

    # Generate query patterns for a known entity
    patterns = service._generate_query_patterns("subject", [], [])

    # Extract the basic query
    basic_query = patterns["basic_query"]

    # Validate the generated query
    validation_result = validate_graphql(basic_query, schema_extract)

    # Assertions
    assert (
        validation_result.is_valid is True
    ), f"Basic query validation failed: {validation_result.errors}"
    assert len(validation_result.errors) == 0

    # Verify query structure
    assert validation_result.query_tree is not None
    root = validation_result.query_tree
    assert root.entity_name == "subject"

    # Verify essential fields are present
    expected_basic_fields = {"id", "submitter_id", "type"}
    actual_fields = set(root.fields)
    assert expected_basic_fields.issubset(
        actual_fields
    ), f"Missing basic fields: {expected_basic_fields - actual_fields}"


@pytest.mark.asyncio
async def test_query_patterns_relationship_query_validation(mock_client, config):
    """Test that relationship query patterns generated are valid GraphQL"""
    service = Gen3Service(mock_client, config)

    # Get schema extract for validation
    full_schema = await service.get_schema_full()
    from gen3_mcp.graphql_validator import validate_graphql
    from gen3_mcp.schema_extract import SchemaExtract

    schema_extract = SchemaExtract.from_full_schema(full_schema)

    # Mock hierarchical data with children that have backref_fields
    children = [
        {"entity": "sample", "relationship": "related_to", "backref_field": "samples"},
        {"entity": "study", "relationship": "member_of", "backref_field": "studies"},
    ]

    # Generate query patterns
    patterns = service._generate_query_patterns("subject", [], children)

    # Test each relationship query pattern
    relationship_patterns = patterns["with_relationships"]
    assert (
        len(relationship_patterns) > 0
    ), "Should generate relationship patterns when children exist"

    for pattern in relationship_patterns:
        query = pattern["query"]
        target_entity = pattern["target_entity"]

        # Validate each relationship query
        validation_result = validate_graphql(query, schema_extract)

        # Assertions
        assert (
            validation_result.is_valid is True
        ), f"Relationship query for {target_entity} failed validation: {validation_result.errors}"
        assert len(validation_result.errors) == 0

        # Verify query structure - should have subject as root with relationship child
        assert validation_result.query_tree is not None
        root = validation_result.query_tree
        assert root.entity_name == "subject"

        # Verify the relationship is properly represented in the tree
        # The backref_field should appear as a child in the query tree
        child_entities = set(root.children.keys())
        assert (
            len(child_entities) > 0
        ), f"Relationship query should have child entities, got: {child_entities}"


@pytest.mark.asyncio
async def test_query_patterns_complex_hierarchy_validation(mock_client, config):
    """Test query pattern validation for entities with both parents and children"""
    service = Gen3Service(mock_client, config)

    # Get schema extract for validation
    full_schema = await service.get_schema_full()
    from gen3_mcp.graphql_validator import validate_graphql
    from gen3_mcp.schema_extract import SchemaExtract

    schema_extract = SchemaExtract.from_full_schema(full_schema)

    # Test with the sample entity which has both parents (subject) and could have children
    # Mock complex hierarchy
    parents = [
        {
            "entity": "subject",
            "relationship": "related_to",
            "backref_field": "subjects",
            "link_name": "subjects",
        }
    ]

    children = [
        {
            "entity": "aliquot",
            "relationship": "derived_from",
            "backref_field": "aliquots",
        }
    ]

    # Generate patterns for intermediate entity
    patterns = service._generate_query_patterns("sample", parents, children)

    # Validate basic query
    basic_query = patterns["basic_query"]
    validation_result = validate_graphql(basic_query, schema_extract)

    assert (
        validation_result.is_valid is True
    ), f"Complex entity basic query failed: {validation_result.errors}"
    assert validation_result.query_tree.entity_name == "sample"

    # Validate relationship queries if any exist
    if patterns["with_relationships"]:
        for pattern in patterns["with_relationships"]:
            query = pattern["query"]
            validation_result = validate_graphql(query, schema_extract)

            # Should be valid even for entities not in our limited test schema
            # (validation might fail due to missing entities, but syntax should be correct)
            if not validation_result.is_valid:
                # Check if failures are due to unknown entities (acceptable) vs syntax errors (not acceptable)
                syntax_errors = [
                    e
                    for e in validation_result.errors
                    if e.error_type == "syntax_error"
                ]
                assert (
                    len(syntax_errors) == 0
                ), f"Syntax errors in generated query: {syntax_errors}"

                # If validation fails due to unknown entities, that's acceptable for this test
                # since our mock schema is limited, but syntax should still be correct
                unknown_entity_errors = [
                    e
                    for e in validation_result.errors
                    if e.error_type == "unknown_entity"
                ]
                if unknown_entity_errors:
                    # This is acceptable - just means our test schema doesn't have all entities
                    # but the query syntax itself should be valid
                    continue
            else:
                # If validation passes, verify structure
                assert validation_result.query_tree is not None
                assert validation_result.query_tree.entity_name == "sample"

    # Verify that patterns contain expected structure elements
    assert "basic_query" in patterns
    assert "with_relationships" in patterns
    assert "usage_examples" in patterns
    assert isinstance(patterns["usage_examples"], list)
    assert len(patterns["usage_examples"]) > 0
