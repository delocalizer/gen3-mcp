"""Tests for QueryService"""

import pytest
from gen3_mcp.service import Gen3Service
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
async def test_execute_field_sampling(mock_client, config):
    """Test field value sampling"""
    gen3_service = Gen3Service(mock_client, config)
    query_service = QueryService(mock_client, config, gen3_service)

    result = await query_service.execute_field_sampling("subject", "gender", limit=10)

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

    result = await query_service.validate_query_fields(valid_query)

    assert result["valid"] == True
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

    result = await query_service.validate_query_fields(invalid_query)

    assert result["valid"] == False
    assert result["summary"]["total_errors"] > 0
    assert "invalid_field" in str(result["summary"]["errors"])


@pytest.mark.asyncio
async def test_suggest_similar_fields(mock_client, config):
    """Test field suggestion functionality"""
    gen3_service = Gen3Service(mock_client, config)
    query_service = QueryService(mock_client, config, gen3_service)

    # Test suggestion for a field similar to "gender"
    suggestions = await query_service.suggest_similar_fields("gander", "subject")

    assert suggestions["entity_exists"] == True
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

    assert template["exists"] == True
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

    assert suggestions["entity_exists"] == False
    assert "entity_suggestions" in suggestions


@pytest.mark.asyncio
async def test_extract_graphql_fields(mock_client, config):
    """Test GraphQL field extraction"""
    gen3_service = Gen3Service(mock_client, config)
    query_service = QueryService(mock_client, config, gen3_service)

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

    extracted = query_service._extract_graphql_fields(query)

    assert "subject" in extracted
    assert "id" in extracted["subject"]
    assert "gender" in extracted["subject"]
    assert "studies" in extracted["subject"]


@pytest.mark.asyncio
async def test_similarity(mock_client, config):
    """Test similarity calculation"""
    gen3_service = Gen3Service(mock_client, config)
    query_service = QueryService(mock_client, config, gen3_service)

    # Test exact match
    assert query_service._similarity("gender", "gender") == 1.0
    
    # Test substring match
    assert query_service._similarity("gender", "gen") == pytest.approx(0.667, rel=1e-3)
    
    # Test no match
    assert query_service._similarity("abc", "xyz") < 0.5
