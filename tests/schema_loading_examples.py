"""
Test Resource Loading Approaches - Usage Examples and Comparison

This file demonstrates different ways to load the ex_schema.json as a test resource.
"""


import pytest

# ============================================================================
# APPROACH 1: Simple Global Variable (Recommended for small schemas)
# ============================================================================


def test_with_global_variable():
    """Example using global TEST_SCHEMA variable"""
    from tests.conftest_improved import TEST_SCHEMA

    # Direct access - fastest
    subject_schema = TEST_SCHEMA["subject"]
    assert subject_schema["category"] == "administrative"
    assert "gender" in subject_schema["properties"]


# ============================================================================
# APPROACH 2: Function-based with Caching (Good balance)
# ============================================================================


def test_with_function_caching():
    """Example using get_test_schema() function"""
    from tests.conftest_improved import get_test_schema

    schema = get_test_schema()
    sample_schema = schema["sample"]

    # Check realistic properties from ex_schema.json
    assert sample_schema["category"] == "biospecimen"
    assert "anatomic_site" in sample_schema["properties"]
    assert "preservation_method" in sample_schema["properties"]


# ============================================================================
# APPROACH 3: Class-based Manager (Most Flexible - RECOMMENDED)
# ============================================================================


def test_with_schema_manager():
    """Example using TestSchemaManager class"""
    from tests.conftest_improved import schema_manager

    # Get full schema
    schema = schema_manager.schema
    assert len(schema) == 3  # subject, sample, study

    # Get specific entity
    subject_schema = schema_manager.get_entity_schema("subject")
    assert subject_schema["id"] == "subject"

    # Get entity properties
    subject_props = schema_manager.get_entity_properties("subject")
    expected_props = [
        "age_at_enrollment",
        "gender",
        "race",
        "ethnicity",
        "handedness",
        "experimental_group",
    ]
    for prop in expected_props:
        assert prop in subject_props

    # Get entity links
    subject_links = schema_manager.get_entity_links("subject")
    assert len(subject_links) == 1
    assert subject_links[0]["target_type"] == "study"

    # List available entities
    entities = schema_manager.get_available_entities()
    assert set(entities) == {"subject", "sample", "study"}


# ============================================================================
# APPROACH 4: Pytest Fixtures (Best for test isolation)
# ============================================================================


def test_with_session_fixture(test_schema_fixture):
    """Example using session-scoped fixture"""
    study_schema = test_schema_fixture["study"]

    # Check realistic study properties
    assert study_schema["category"] == "administrative"
    assert "study_design" in study_schema["properties"]
    assert "longitudinal" in study_schema["properties"]

    # Check enum values are realistic
    study_design_enum = study_schema["properties"]["study_design"]["enum"]
    assert "Case-Control Cohort Study" in study_design_enum
    assert "Observational Longitudinal Study" in study_design_enum


def test_with_individual_fixtures(subject_schema, sample_schema, study_schema):
    """Example using individual entity fixtures"""

    # Test subject schema
    assert subject_schema["title"] == "Subject"
    assert subject_schema["category"] == "administrative"

    # Test sample schema
    assert sample_schema["title"] == "Sample"
    assert sample_schema["category"] == "biospecimen"

    # Test study schema
    assert study_schema["title"] == "Study"
    assert study_schema["category"] == "administrative"


def test_with_schema_manager_fixture(schema_manager_fixture):
    """Example using schema manager fixture"""
    manager = schema_manager_fixture

    # Test that we can get complex nested data
    sample_props = manager.get_entity_properties("sample")

    # Check for realistic biospecimen properties
    assert "fasting_status" in sample_props
    assert "preservation_method" in sample_props
    assert "storage_temperature" in sample_props

    # Verify enum values are loaded correctly
    preservation_enum = sample_props["preservation_method"]["enum"]
    expected_preservation = ["Cryopreserved", "FFPE", "Fresh", "Frozen", "OCT"]
    for method in expected_preservation:
        assert method in preservation_enum


# ============================================================================
# APPROACH 5: Enhanced Mock Testing with Realistic Data
# ============================================================================


def test_with_realistic_mock_client(mock_client_realistic):
    """Example using mock client with realistic schema"""

    # The mock client now uses data from ex_schema.json
    # This makes tests more realistic and catches more edge cases

    # Mock responses will use actual property names and enum values
    # from the real schema, making tests more robust

    assert mock_client_realistic is not None
    # Additional testing would go here...


@pytest.mark.asyncio
async def test_with_realistic_mcp_setup(mcp_test_setup_realistic):
    """Example using full MCP setup with realistic schema"""

    setup = mcp_test_setup_realistic

    # Access components
    mcp_server = setup["mcp_server"]
    setup["mock_gen3_service"]
    schema = setup["schema"]
    schema_manager = setup["schema_manager"]

    # The mocks now return realistic data based on ex_schema.json
    assert mcp_server is not None
    assert len(schema) == 3

    # Schema manager provides easy access
    subject_gender_enum = schema_manager.get_entity_properties("subject")["gender"][
        "enum"
    ]
    expected_genders = ["Female", "Male", "Not Reported", "Unknown", "Unspecified"]
    assert set(subject_gender_enum) == set(expected_genders)


# ============================================================================
# PERFORMANCE AND MEMORY COMPARISON
# ============================================================================


def test_compare_loading_approaches():
    """Compare different loading approaches"""

    # Global variable - fastest access, loaded once
    from tests.conftest_improved import TEST_SCHEMA

    pytest.approx(0)  # Instantaneous access
    schema1 = TEST_SCHEMA

    # Function with caching - slight overhead on first call, then fast
    from tests.conftest_improved import get_test_schema

    schema2 = get_test_schema()

    # Class-based manager - slightly more overhead but most flexible
    from tests.conftest_improved import schema_manager

    schema3 = schema_manager.schema

    # All should return the same data
    assert schema1 == schema2 == schema3

    # Verify we have the expected structure from ex_schema.json
    for schema in [schema1, schema2, schema3]:
        assert "subject" in schema
        assert "sample" in schema
        assert "study" in schema

        # Verify realistic properties exist
        assert "age_at_enrollment" in schema["subject"]["properties"]
        assert "anatomic_site" in schema["sample"]["properties"]
        assert "study_design" in schema["study"]["properties"]


# ============================================================================
# RECOMMENDATION SUMMARY
# ============================================================================

"""
RECOMMENDED APPROACH: Use the TestSchemaManager class (Approach 3)

Why TestSchemaManager is recommended:

1. **Flexibility**: Easy access to full schema, individual entities, properties, links
2. **Performance**: Lazy loading with caching
3. **Maintainability**: Centralized schema management
4. **Testing**: Can reload schema during tests if needed
5. **Extensibility**: Easy to add helper methods
6. **Memory Efficient**: Only loads when needed
7. **Type Safety**: Can add type hints easily

Usage in tests:
```python
from tests.conftest_improved import schema_manager

def test_my_feature():
    # Get what you need
    subject_props = schema_manager.get_entity_properties("subject")
    sample_links = schema_manager.get_entity_links("sample")

    # Use in your test
    assert "gender" in subject_props
```

For pytest fixtures, use the session-scoped fixtures for isolation:
```python
def test_with_fixture(schema_manager_fixture):
    manager = schema_manager_fixture
    # Use manager...
```
"""
