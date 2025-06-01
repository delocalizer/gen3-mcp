"""Tests for QueryService"""

import pytest

from gen3_mcp.query import QueryService
from gen3_mcp.schema import SchemaService


@pytest.mark.asyncio
async def test_execute_graphql(mock_client, config):
    """Test GraphQL query execution"""
    gen3_service = SchemaService(mock_client, config)
    query_service = QueryService(mock_client, config, gen3_service)

    query = "{ subject { id submitter_id } }"
    result = await query_service.execute_graphql(query)

    assert result is not None
    assert mock_client.post_json.called
    assert "data" in result


@pytest.mark.asyncio
async def test_generate_query_template(mock_client, config):
    """Test query template generation"""
    gen3_service = SchemaService(mock_client, config)
    query_service = QueryService(mock_client, config, gen3_service)

    template = await query_service.generate_query_template("subject")

    assert template["exists"]
    assert template["template"] is not None
    assert (
        template["template"]
        == """{
    subject(first: 10) {
        id
        submitter_id
        type
        age_at_enrollment_gt89
        ethnicity
        gender
        handedness
        index_date
        index_event_status
        lost_to_followup
        race
        aligned_reads_files {
            id
            submitter_id
        }
        samples {
            id
            submitter_id
        }
        studies {
            id
            submitter_id
        }
    }
}"""
    )
