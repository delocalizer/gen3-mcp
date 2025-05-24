"""Tests for ValidationService"""

import pytest
from gen3_mcp.schema.service import SchemaService
from gen3_mcp.schema.validation import ValidationService


@pytest.mark.asyncio
async def test_validate_valid_query(mock_client, config):
    """Test validation of a valid GraphQL query"""
    schema_service = SchemaService(mock_client, config)
    validation_service = ValidationService(schema_service)

    # Valid query using fields that exist in mock schema
    valid_query = """
    {
        subject {
            id
            submitter_id
            gender
            age_at_enrollment
        }
    }
    """

    result = await validation_service.validate_query_fields(valid_query)

    assert result["valid"] == True
    assert "subject" in result["extracted_fields"]
    assert "id" in result["extracted_fields"]["subject"]
    assert result["summary"]["total_errors"] == 0


@pytest.mark.asyncio
async def test_validate_invalid_query(mock_client, config):
    """Test validation of an invalid GraphQL query"""
    schema_service = SchemaService(mock_client, config)
    validation_service = ValidationService(schema_service)

    # Invalid query with non-existent fields
    invalid_query = """
    {
        subject {
            id
            invalid_field
            another_bad_field
        }
    }
    """

    result = await validation_service.validate_query_fields(invalid_query)

    assert result["valid"] == False
    assert result["summary"]["total_errors"] > 0
    assert "invalid_field" in str(result["summary"]["errors"])


@pytest.mark.asyncio
async def test_suggest_similar_fields(mock_client, config):
    """Test field suggestion functionality"""
    schema_service = SchemaService(mock_client, config)
    validation_service = ValidationService(schema_service)

    # Test suggestion for a field similar to "gender"
    suggestions = await validation_service.suggest_similar_fields("gander", "subject")

    assert suggestions["entity_exists"] == True
    assert len(suggestions["suggestions"]) > 0

    # Should suggest "gender" as similar to "gander"
    suggestion_names = [s["name"] for s in suggestions["suggestions"]]
    assert "gender" in suggestion_names


@pytest.mark.asyncio
async def test_generate_query_template(mock_client, config):
    """Test query template generation"""
    schema_service = SchemaService(mock_client, config)
    validation_service = ValidationService(schema_service)

    template = await validation_service.generate_query_template("subject")

    assert template["exists"] == True
    assert template["template"] is not None
    assert "id" in template["basic_fields"]
    assert "submitter_id" in template["basic_fields"]
    assert len(template["relationship_fields"]) > 0


@pytest.mark.asyncio
async def test_nonexistent_entity_suggestions(mock_client, config):
    """Test suggestions for non-existent entities"""
    schema_service = SchemaService(mock_client, config)
    validation_service = ValidationService(schema_service)

    suggestions = await validation_service.suggest_similar_fields(
        "test_field", "nonexistent_entity"
    )

    assert suggestions["entity_exists"] == False
    assert "entity_suggestions" in suggestions


@pytest.mark.asyncio
async def test_extract_graphql_fields(mock_client, config):
    """Test GraphQL field extraction"""
    schema_service = SchemaService(mock_client, config)
    validation_service = ValidationService(schema_service)

    query = """
    {
        subject(first: 10) {
            id
            submitter_id
            gender
            studies {
                id
                study_name
            }
        }
    }
    """

    extracted = validation_service._extract_graphql_fields(query)

    assert "subject" in extracted
    assert "id" in extracted["subject"]
    assert "gender" in extracted["subject"]
    assert "studies" in extracted["subject"]
