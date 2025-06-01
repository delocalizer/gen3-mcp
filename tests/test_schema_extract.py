"""Tests for SchemaExtract functionality"""

import json
from pathlib import Path

import pytest

from gen3_mcp.schema_extract import (
    SchemaExtract,
    _create_query_patterns,
    _create_schema_summary,
    _get_position_description,
    _extract_enum_fields,
)


@pytest.fixture(autouse=True)
def clear_schema_cache():
    """Hack: clear SchemaExtract cache before each test to prevent interference"""
    SchemaExtract.clear_cache()
    yield
    SchemaExtract.clear_cache()


@pytest.fixture(scope="session")
def test_schema():
    """Load the test schema from ex_schema.json"""
    schema_path = Path(__file__).parent / "ex_schema.json"
    with open(schema_path) as f:
        return json.load(f)


@pytest.fixture(scope="session")
def reference_extract():
    """Load the reference SchemaExtract format from ex_schema_extract.json"""
    extract_path = Path(__file__).parent / "ex_schema_extract.json"
    with open(extract_path) as f:
        return json.load(f)


def test_schema_extract_from_full_schema(test_schema):
    """Test SchemaExtract creation from full schema"""
    schema_extract = SchemaExtract.from_full_schema(test_schema)

    # Basic structure checks
    assert isinstance(schema_extract.entities, dict)
    assert len(schema_extract.entities) > 0

    # Check that expected entities exist
    expected_entities = {"subject", "sample", "study", "aliquot", "aligned_reads_file"}
    actual_entities = set(schema_extract.entities.keys())
    assert expected_entities.issubset(actual_entities)

    # Check that each entity has the expected structure
    for entity_name, entity in schema_extract.entities.items():
        assert hasattr(entity, "name")
        assert hasattr(entity, "fields")
        assert hasattr(entity, "relationships")
        assert hasattr(entity, "schema_summary")
        assert hasattr(entity, "query_patterns")

        # Basic data type checks
        assert entity.name == entity_name
        assert isinstance(entity.fields, set)
        assert isinstance(entity.relationships, dict)


def test_schema_extract_entity_access(test_schema):
    """Test accessing individual entities from SchemaExtract"""
    schema_extract = SchemaExtract.from_full_schema(test_schema)

    # Test subject entity specifically
    subject = schema_extract.entities["subject"]
    assert subject.name == "subject"

    # Check fields are populated
    assert len(subject.fields) > 0
    assert "id" in subject.fields
    assert "submitter_id" in subject.fields

    # Check relationships are populated
    assert len(subject.relationships) > 0

    # Check schema summary is populated
    assert subject.schema_summary is not None
    assert subject.schema_summary.title == "Subject"
    assert subject.schema_summary.category == "administrative"

    # Check query patterns are populated
    assert subject.query_patterns is not None
    assert subject.query_patterns.basic_query
    assert "subject" in subject.query_patterns.basic_query


def test_schema_extract_caching():
    """Test that SchemaExtract uses caching properly"""
    # Clear any existing cache
    SchemaExtract.clear_cache()

    test_schema = {"test_entity": {"properties": {"id": {"type": "string"}}}}

    # First call should create new extract
    extract1 = SchemaExtract.from_full_schema(test_schema)

    # Second call should return cached version
    extract2 = SchemaExtract.from_full_schema(test_schema)

    # Should be the same instance due to caching
    assert extract1 is extract2

    # Clear cache and verify new instance is created
    SchemaExtract.clear_cache()
    extract3 = SchemaExtract.from_full_schema(test_schema)
    assert extract3 is not extract1


def test_create_schema_summary(test_schema):
    """Test schema summary creation for individual entities"""
    schema_extract = SchemaExtract.from_full_schema(test_schema)
    subject_entity = schema_extract.entities["subject"]
    subject_def = test_schema["subject"]

    # Test the function directly
    schema_summary = _create_schema_summary(subject_entity, subject_def)

    # Check all expected fields are present
    assert schema_summary.title == "Subject"
    assert (
        schema_summary.description
        == "The collection of all data related to a specific subject in the context of a specific experiment."
    )
    assert schema_summary.category == "administrative"
    assert isinstance(schema_summary.required_fields, list)
    assert "submitter_id" in schema_summary.required_fields
    assert "type" in schema_summary.required_fields

    # Check counts
    assert schema_summary.field_count == len(subject_entity.fields)
    assert schema_summary.parent_count > 0  # Subject has studies as parent
    assert (
        schema_summary.child_count > 0
    )  # Subject has samples, aligned_reads_files as children

    # Check position description
    assert isinstance(schema_summary.position_description, dict)
    assert "position" in schema_summary.position_description
    assert "description" in schema_summary.position_description
    assert schema_summary.position_description["position"] == "intermediate"


def test_create_query_patterns(test_schema):
    """Test query pattern generation for entities"""
    schema_extract = SchemaExtract.from_full_schema(test_schema)
    subject_entity = schema_extract.entities["subject"]

    # Test the function directly
    query_patterns = _create_query_patterns(subject_entity)

    # Check structure
    assert hasattr(query_patterns, "basic_query")
    assert hasattr(query_patterns, "complex_queries")

    # Check basic query
    basic_query = query_patterns.basic_query
    assert "subject" in basic_query
    assert "id" in basic_query
    assert "submitter_id" in basic_query
    assert "type" in basic_query

    # Check relationship queries
    assert isinstance(query_patterns.complex_queries, list)
    assert len(query_patterns.complex_queries) > 0

    # Check that relationship queries have proper structure
    for rel_query in query_patterns.complex_queries:
        assert hasattr(rel_query, "description")
        assert hasattr(rel_query, "query")
        assert isinstance(rel_query.description, str)
        assert isinstance(rel_query.query, str)
        assert "subject" in rel_query.query


def test_get_position_description():
    """Test hierarchical position determination"""
    # Test root entity (no parents)
    root_pos = _get_position_description(0, 1)
    assert root_pos["position"] == "root"
    assert "no parents" in root_pos["description"].lower()

    # Test leaf entity (no children)
    leaf_pos = _get_position_description(1, 0)
    assert leaf_pos["position"] == "leaf"
    assert "no children" in leaf_pos["description"].lower()

    # Test intermediate entity
    intermediate_pos = _get_position_description(1, 1)
    assert intermediate_pos["position"] == "intermediate"
    assert "intermediate" in intermediate_pos["description"].lower()

    # Test multiple parents/children
    multi_pos = _get_position_description(2, 3)
    assert multi_pos["position"] == "intermediate"


def test_query_patterns_basic_query_validation(test_schema):
    """Test that basic query patterns are valid GraphQL"""
    schema_extract = SchemaExtract.from_full_schema(test_schema)

    from gen3_mcp.graphql_validator import validate_graphql

    # Test basic queries for all entities
    for entity_name, entity in schema_extract.entities.items():
        if entity.query_patterns:
            basic_query = entity.query_patterns.basic_query
            validation_result = validate_graphql(basic_query, schema_extract)

            assert (
                validation_result.is_valid
            ), f"Basic query for {entity_name} failed validation: {validation_result.errors}"


def test_query_patterns_relationship_query_validation(test_schema):
    """Test that relationship query patterns are valid GraphQL"""
    schema_extract = SchemaExtract.from_full_schema(test_schema)

    from gen3_mcp.graphql_validator import validate_graphql

    # Test relationship queries
    for entity_name, entity in schema_extract.entities.items():
        if entity.query_patterns and entity.query_patterns.complex_queries:
            for rel_query in entity.query_patterns.complex_queries:
                validation_result = validate_graphql(rel_query.query, schema_extract)
                assert validation_result.is_valid


def test_schema_extract_matches_reference_format(test_schema, reference_extract):
    """Test that SchemaExtract output matches the reference format"""
    schema_extract = SchemaExtract.from_full_schema(test_schema)
    result = json.loads(repr(schema_extract))

    # Check that we have the same entities
    assert set(result.keys()) == set(reference_extract.keys())

    # Check structure for a known entity (subject)
    if "subject" in result and "subject" in reference_extract:
        subject_result = result["subject"]
        subject_reference = reference_extract["subject"]

        # Check that all major sections exist
        expected_sections = [
            "fields",
            "relationships",
            "schema_summary",
            "query_patterns",
        ]
        for section in expected_sections:
            assert section in subject_result, f"Missing section: {section}"
            assert section in subject_reference, f"Reference missing section: {section}"

        # Check schema_summary structure
        schema_summary = subject_result["schema_summary"]
        ref_summary = subject_reference["schema_summary"]

        expected_summary_fields = [
            "title",
            "description",
            "category",
            "required_fields",
            "enum_fields",
            "field_count",
            "parent_count",
            "child_count",
            "position_description",
        ]
        for field in expected_summary_fields:
            assert field in schema_summary, f"Missing schema_summary field: {field}"
            assert (
                field in ref_summary
            ), f"Reference missing schema_summary field: {field}"

        # Check query_patterns structure
        query_patterns = subject_result["query_patterns"]
        ref_patterns = subject_reference["query_patterns"]

        expected_pattern_fields = [
            "basic_query",
            "complex_queries",
        ]
        for field in expected_pattern_fields:
            assert field in query_patterns, f"Missing query_patterns field: {field}"
            assert (
                field in ref_patterns
            ), f"Reference missing query_patterns field: {field}"


def test_schema_extract_repr_is_valid_json(test_schema):
    """Test that SchemaExtract.__repr__ returns valid JSON"""
    schema_extract = SchemaExtract.from_full_schema(test_schema)
    repr_str = repr(schema_extract)

    # Should be valid JSON
    try:
        parsed = json.loads(repr_str)
        assert isinstance(parsed, dict)
        assert len(parsed) > 0
    except json.JSONDecodeError as e:
        pytest.fail(f"SchemaExtract.__repr__ does not return valid JSON: {e}")


def test_schema_extract_entity_relationships(test_schema):
    """Test that entity relationships are properly structured"""
    schema_extract = SchemaExtract.from_full_schema(test_schema)

    # Check subject relationships specifically
    subject = schema_extract.entities["subject"]

    # Should have both parent and child relationships
    parent_rels = [
        rel
        for rel in subject.relationships.values()
        if rel.link_type.value == "child_of"
    ]
    child_rels = [
        rel
        for rel in subject.relationships.values()
        if rel.link_type.value == "parent_of"
    ]

    assert len(parent_rels) > 0, "Subject should have parent relationships"
    assert len(child_rels) > 0, "Subject should have child relationships"

    # Check relationship structure
    for rel in subject.relationships.values():
        assert hasattr(rel, "name")
        assert hasattr(rel, "source_type")
        assert hasattr(rel, "target_type")
        assert hasattr(rel, "link_type")
        assert hasattr(rel, "link_multiplicity")

        assert rel.source_type == "subject"
        assert rel.target_type in schema_extract.entities


def test_schema_extract_helper_functions(test_schema):
    """Test individual helper functions in schema_extract module"""
    from gen3_mcp.schema_extract import (
        _create_query_patterns,
        _create_schema_summary,
        _get_position_description,
    )

    schema_extract = SchemaExtract.from_full_schema(test_schema)
    subject_entity = schema_extract.entities["subject"]
    subject_def = test_schema["subject"]

    # Test position_description function
    parent_count = subject_entity.schema_summary.parent_count
    child_count = subject_entity.schema_summary.child_count
    position_desc = _get_position_description(parent_count, child_count)

    assert isinstance(position_desc, dict)
    assert "position" in position_desc
    assert "description" in position_desc
    assert position_desc["position"] in ["root", "leaf", "intermediate"]

    # Test schema_summary creation
    schema_summary = _create_schema_summary(subject_entity, subject_def)

    assert schema_summary.title == "Subject"
    assert schema_summary.category == "administrative"
    assert len(schema_summary.required_fields) > 0
    assert schema_summary.field_count > 0
    assert "position" in schema_summary.position_description

    # Test query_patterns creation
    query_patterns = _create_query_patterns(subject_entity)

    assert query_patterns.basic_query
    assert "subject" in query_patterns.basic_query
    assert isinstance(query_patterns.complex_queries, list)


def test_schema_extract_consolidation_coverage(test_schema):
    """Test that SchemaExtract provides comprehensive functionality for all entities"""
    schema_extract = SchemaExtract.from_full_schema(test_schema)

    # Test that every entity has comprehensive information in one place
    for entity_name, entity in schema_extract.entities.items():
        # Entity context functionality
        assert entity.schema_summary is not None
        assert entity.schema_summary.title
        assert entity.schema_summary.description
        assert entity.schema_summary.category
        assert isinstance(entity.schema_summary.required_fields, list)
        assert entity.schema_summary.field_count >= 0
        assert entity.schema_summary.parent_count >= 0
        assert entity.schema_summary.child_count >= 0

        # Position description functionality
        position_desc = entity.schema_summary.position_description
        assert "position" in position_desc
        assert "description" in position_desc
        assert position_desc["position"] in ["root", "leaf", "intermediate"]

        # Query patterns functionality
        assert entity.query_patterns is not None
        assert entity.query_patterns.basic_query
        assert entity_name in entity.query_patterns.basic_query
        assert isinstance(entity.query_patterns.complex_queries, list)

        # Relationships and fields
        assert isinstance(entity.fields, set)
        assert isinstance(entity.relationships, dict)

        # Verify that basic fields are present
        basic_fields = {"id", "submitter_id", "type"}
        # At least some basic fields should be present (schema-dependent)
        assert len(entity.fields.intersection(basic_fields)) > 0


def test_extract_enum_fields():
    """Test the _extract_enum_fields function directly"""
    # Test entity with various enum field types
    test_entity_def = {
        "properties": {
            "direct_enum_field": {
                "enum": ["value1", "value2", "value3"]
            },
            "regular_field": {
                "type": "string"
            },
            "complex_oneof_field": {
                "oneOf": [
                    {"type": "null"},
                    {"enum": ["a", "b"]},
                    {"enum": ["c", "d"]}
                ]
            },
            "oneof_without_enum": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "null"}
                ]
            }
        }
    }
    
    enum_fields = _extract_enum_fields(test_entity_def)
    
    # Should only extract fields with direct enum constraints
    expected = ["direct_enum_field"]
    assert enum_fields == expected


def test_schema_summary_includes_enum_fields(test_schema):
    """Test that schema summary includes enum_fields for entities"""
    schema_extract = SchemaExtract.from_full_schema(test_schema)
    
    # Test some specific entities we know have enum fields
    sample_entity = schema_extract.entities["sample"]
    assert hasattr(sample_entity.schema_summary, "enum_fields")
    assert isinstance(sample_entity.schema_summary.enum_fields, list)
    
    # Sample should have enum fields like fasting_status, laterality, etc.
    sample_enums = sample_entity.schema_summary.enum_fields
    assert "fasting_status" in sample_enums
    assert "laterality" in sample_enums
    assert "preservation_method" in sample_enums
    # State should NOT be included as it uses oneOf validation
    assert "state" not in sample_enums
    
    # Subject should have enum fields like ethnicity, gender, etc.
    subject_entity = schema_extract.entities["subject"]
    subject_enums = subject_entity.schema_summary.enum_fields
    assert "ethnicity" in subject_enums
    assert "gender" in subject_enums
    assert "race" in subject_enums
    # State should NOT be included as it uses oneOf validation
    assert "state" not in subject_enums
    
    # All enum fields should be sorted
    assert sample_enums == sorted(sample_enums)
    assert subject_enums == sorted(subject_enums)


def test_enum_fields_in_reference_format(test_schema, reference_extract):
    """Test that enum_fields match the reference format"""
    schema_extract = SchemaExtract.from_full_schema(test_schema)
    result = json.loads(repr(schema_extract))
    
    # Check that enum_fields exist in the output and match reference
    for entity_name in result.keys():
        if entity_name in reference_extract:
            result_entity = result[entity_name]
            ref_entity = reference_extract[entity_name]
            
            # Both should have enum_fields in schema_summary
            assert "enum_fields" in result_entity["schema_summary"]
            assert "enum_fields" in ref_entity["schema_summary"]
            
            # Values should match
            result_enums = result_entity["schema_summary"]["enum_fields"]
            ref_enums = ref_entity["schema_summary"]["enum_fields"]
            assert result_enums == ref_enums, f"Enum fields mismatch for {entity_name}: {result_enums} != {ref_enums}"


def test_enum_fields_comprehensive_coverage(test_schema):
    """Test that enum_fields are correctly extracted for all entities in test schema"""
    schema_extract = SchemaExtract.from_full_schema(test_schema)
    
    # Expected enum fields for each entity (based on our analysis, excluding state)
    expected_enum_fields = {
        "aligned_reads_file": [],
        "aliquot": [], 
        "sample": ["fasting_status", "laterality", "preservation_method", "procured_or_purchased"],
        "study": ["study_design", "study_objective", "study_setup", "type"],
        "subject": ["age_at_enrollment_gt89", "ethnicity", "gender", "handedness", "index_date", "index_event_status", "lost_to_followup", "race"]
    }
    
    for entity_name, expected_enums in expected_enum_fields.items():
        if entity_name in schema_extract.entities:
            entity = schema_extract.entities[entity_name]
            actual_enums = entity.schema_summary.enum_fields
            assert actual_enums == expected_enums, f"Entity {entity_name}: expected {expected_enums}, got {actual_enums}"
