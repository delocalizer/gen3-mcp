"""Tests for QueryService"""

import pytest

from gen3_mcp.data import Gen3Service
from gen3_mcp.query import QueryService


@pytest.mark.asyncio
async def test_execute_graphql(mock_client, config):
    """Test GraphQL query execution"""
    gen3_service = Gen3Service(mock_client, config)
    query_service = QueryService(mock_client, config, gen3_service)

    query = "{ subject { id submitter_id } }"
    result = await query_service.execute_graphql(query)

    assert result is not None
    assert mock_client.post_json.called
    assert "data" in result


@pytest.mark.asyncio
async def test_field_sample(mock_client, config):
    """Test field value sampling"""
    gen3_service = Gen3Service(mock_client, config)
    query_service = QueryService(mock_client, config, gen3_service)

    result = await query_service.field_sample("subject", "gender", limit=10)

    assert "entity" in result
    assert "field" in result
    assert "values" in result
    assert result["entity"] == "subject"
    assert result["field"] == "gender"


@pytest.mark.asyncio
async def test_validate_valid_query(mock_client, config):
    """Test validation of a valid GraphQL query"""
    gen3_service = Gen3Service(mock_client, config)
    query_service = QueryService(mock_client, config, gen3_service)

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

    result = await query_service.validate_query(valid_query)

    assert result["valid"]
    assert "subject" in result["extracted_fields"]
    assert "id" in result["extracted_fields"]["subject"]
    assert result["summary"]["total_errors"] == 0


@pytest.mark.asyncio
async def test_validate_invalid_query(mock_client, config):
    """Test validation of an invalid GraphQL query"""
    gen3_service = Gen3Service(mock_client, config)
    query_service = QueryService(mock_client, config, gen3_service)

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

    result = await query_service.validate_query(invalid_query)

    assert not result["valid"]
    assert result["summary"]["total_errors"] > 0
    assert "invalid_field" in str(result["summary"]["errors"])


@pytest.mark.asyncio
async def test_suggest_similar_fields(mock_client, config):
    """Test field suggestion functionality"""
    gen3_service = Gen3Service(mock_client, config)
    query_service = QueryService(mock_client, config, gen3_service)

    # Test suggestion for a field similar to "gender"
    suggestions = await query_service.suggest_similar_fields("gander", "subject")

    assert suggestions["entity_exists"]
    assert len(suggestions["suggestions"]) > 0

    # Should suggest "gender" as similar to "gander"
    suggestion_names = [s["name"] for s in suggestions["suggestions"]]
    assert "gender" in suggestion_names


@pytest.mark.asyncio
async def test_generate_query_template(mock_client, config):
    """Test query template generation"""
    gen3_service = Gen3Service(mock_client, config)
    query_service = QueryService(mock_client, config, gen3_service)

    template = await query_service.generate_query_template("subject")

    assert template["exists"]
    assert template["template"] is not None
    assert "id" in template["basic_fields"]
    assert "submitter_id" in template["basic_fields"]
    assert len(template["relationship_fields"]) > 0


@pytest.mark.asyncio
async def test_nonexistent_entity_suggestions(mock_client, config):
    """Test suggestions for non-existent entities"""
    gen3_service = Gen3Service(mock_client, config)
    query_service = QueryService(mock_client, config, gen3_service)

    suggestions = await query_service.suggest_similar_fields(
        "test_field", "nonexistent_entity"
    )

    assert not suggestions["entity_exists"]
    assert "entity_suggestions" in suggestions


@pytest.mark.asyncio
async def test_validate_relationship_query(mock_client, config):
    """Test validation of queries with relationship traversals"""
    gen3_service = Gen3Service(mock_client, config)
    query_service = QueryService(mock_client, config, gen3_service)

    # Query with relationship traversal that should now be valid
    relationship_query = """
    {
        subject {
            id
            submitter_id
            studies {
                submitter_id
                description
            }
        }
    }
    """

    result = await query_service.validate_query(relationship_query)

    # Should be valid now with relationship support
    assert result["valid"]
    assert "subject" in result["extracted_fields"]
    assert "studies" in result["extracted_fields"]
    
    # Subject should be valid as a direct entity
    assert result["validation_results"]["subject"]["entity_exists"]
    
    # Studies should be valid as a relationship from subject
    studies_result = result["validation_results"]["studies"]
    assert len(studies_result["errors"]) == 0  # Should have no errors for valid relationship


@pytest.mark.asyncio
async def test_validate_plural_relationship_names(mock_client, config):
    """Test validation of queries using plural relationship names"""
    gen3_service = Gen3Service(mock_client, config)
    query_service = QueryService(mock_client, config, gen3_service)

    # Query using plural form of target entity (common pattern)
    plural_query = """
    {
        sample {
            id
            submitter_id
            subjects {
                submitter_id
                gender
            }
        }
    }
    """

    result = await query_service.validate_query(plural_query)

    # Should recognize 'subjects' as plural of 'subject' relationship
    assert result["valid"]
    assert "sample" in result["extracted_fields"]
    assert "subjects" in result["extracted_fields"]
    
    # Both entities should validate successfully
    assert result["validation_results"]["sample"]["entity_exists"]
    subjects_result = result["validation_results"]["subjects"]
    assert len(subjects_result["errors"]) == 0


@pytest.mark.asyncio
async def test_validate_invalid_relationship_fields(mock_client, config):
    """Test validation catches invalid fields in relationship contexts"""
    gen3_service = Gen3Service(mock_client, config)
    query_service = QueryService(mock_client, config, gen3_service)

    # Query with invalid field in relationship context
    invalid_field_query = """
    {
        subject {
            id
            submitter_id
            studies {
                submitter_id
                invalid_study_field
            }
        }
    }
    """

    result = await query_service.validate_query(invalid_field_query)

    # Should catch the invalid field in the relationship context
    assert not result["valid"]
    assert result["summary"]["total_errors"] > 0
    
    # Should specifically identify the invalid field in the target entity
    studies_result = result["validation_results"]["studies"]
    assert len(studies_result["errors"]) > 0
    error_message = studies_result["errors"][0]
    assert "invalid_study_field" in error_message
    assert "does not exist in target entity" in error_message
