"""Integration tests for the Gen3 MCP server"""

from unittest.mock import AsyncMock, patch

import pytest

from gen3_mcp import Gen3Config, Tools
from gen3_mcp.main import create_mcp_server
from gen3_mcp.query import QueryService
from gen3_mcp.service import Gen3Service


@pytest.mark.asyncio
async def test_mcp_server_creation():
    """Test that MCP server can be created"""
    with patch("gen3_mcp.main._config", None):  # Reset global config
        mcp = create_mcp_server()
        assert mcp is not None
        assert mcp.name == "gen3"


@pytest.mark.asyncio
async def test_tools_integration(mock_client, config):
    """Test that all tools work together"""
    tools = Tools(mock_client, config)

    # Test the full workflow
    # 1. Get schema summary
    summary = await tools.schema_summary()
    assert "total_entities" in summary

    # 2. Get entity list
    entities = await tools.schema_entities()
    entity_name = entities["entities"][0] if entities["entities"] else "subject"

    # 3. Get entity schema
    schema = await tools.schema_entity(entity_name)
    assert "properties" in schema

    # 4. Generate query template
    template = await tools.validation_get_query_template(entity_name)
    assert template["exists"]

    # 5. Validate the template
    if template["template"]:
        validation = await tools.validation_validate_query_fields(template["template"])
        assert validation["valid"]

    # 6. Execute a simple query
    simple_query = f"{{ {entity_name} {{ id submitter_id }} }}"
    result = await tools.query_graphql(simple_query)
    assert "data" in result


@pytest.mark.asyncio
async def test_client_service_integration(mock_client, config):
    """Test that client and services work together"""
    # Create services
    gen3_service = Gen3Service(mock_client, config)
    query_service = QueryService(mock_client, config, gen3_service)

    # Test schema operations
    schema = await gen3_service.get_full_schema()
    assert len(schema) > 0

    # Test query operations
    query = "{ subject { id } }"
    result = await query_service.execute_graphql(query)
    assert result is not None


@pytest.mark.asyncio
async def test_error_handling_integration(config):
    """Test error handling across the integrated system"""
    from gen3_mcp.client import Gen3Client
    from gen3_mcp.exceptions import Gen3SchemaError

    # Create a client that will fail
    mock_failing_client = AsyncMock(spec=Gen3Client)
    mock_failing_client.get_json.return_value = None

    service = Gen3Service(mock_failing_client, config)

    # Should raise appropriate exception
    with pytest.raises(Gen3SchemaError):
        await service.get_full_schema()


def test_config_integration():
    """Test that config works with all components"""
    from gen3_mcp.config import gen3_endpoints, gen3_info, gen3_validation_guide

    config = Gen3Config(base_url="https://test.example.com")

    # Test resource functions
    info = gen3_info(config)
    assert "https://test.example.com" in info

    endpoints = gen3_endpoints(config)
    assert "base_url" in endpoints
    assert endpoints["base_url"] == "https://test.example.com"

    guide = gen3_validation_guide()
    assert "GraphQL" in guide


@pytest.mark.asyncio
async def test_caching_integration(mock_client, config):
    """Test that caching works across services"""
    service = Gen3Service(mock_client, config)

    # First call
    schema1 = await service.get_full_schema()
    call_count_1 = mock_client.get_json.call_count

    # Second call should use cache
    schema2 = await service.get_full_schema()
    call_count_2 = mock_client.get_json.call_count

    assert call_count_1 == call_count_2  # No additional calls
    assert schema1 == schema2

    # Clear cache and call again
    service.clear_cache()
    await service.get_full_schema()
    call_count_3 = mock_client.get_json.call_count

    assert call_count_3 > call_count_2  # Should have made another call


if __name__ == "__main__":
    print("✅ All integration tests passed!")
