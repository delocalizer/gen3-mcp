"""Main MCP server implementation"""

import asyncio
import logging

from mcp.server.fastmcp import FastMCP

from .client import Gen3Client
from .config import (
    Gen3Config,
    gen3_endpoints,
    gen3_info,
    gen3_validation_guide,
    setup_logging,
)
from .tools import Tools
from .utils import parse_kwargs_string, validate_kwargs

logger = logging.getLogger("gen3-mcp.main")

# Global state
_config: Gen3Config | None = None
_client: Gen3Client | None = None


async def get_client() -> Gen3Client:
    """Get or create the global client instance"""
    global _config, _client

    if _client is None:
        if _config is None:
            _config = Gen3Config()
            setup_logging(_config.log_level)

        _client = Gen3Client(_config)
        await _client.__aenter__()
        logger.info(f"Connected to Gen3 instance: {_config.base_url}")

    return _client


def create_mcp_server() -> FastMCP:
    """Create and configure the MCP server"""
    mcp = FastMCP("gen3")

    # Register resources
    @mcp.resource("gen3://info")
    def info_resource() -> str:
        if _config is None:
            config = Gen3Config()
        else:
            config = _config
        return gen3_info(config)

    @mcp.resource("gen3://endpoints")
    def endpoints_resource() -> dict[str, str]:
        if _config is None:
            config = Gen3Config()
        else:
            config = _config
        return gen3_endpoints(config)

    @mcp.resource("gen3://validation")
    def validation_resource() -> str:
        return gen3_validation_guide()

    # Register tools
    @mcp.tool()
    async def schema_operations(operation: str, entity_name: str = None) -> dict:
        """Schema operations tool

        Available operations:
        - summary: Get schema summary
        - full: Get complete schema
        - entity: Get schema for specific entity (requires entity_name)
        - entities: Get list of all entities
        - detailed_entities: Get detailed entity list with relationships
        """
        client = await get_client()
        tools = Tools(client, _config)

        match operation:
            case "summary":
                return await tools.schema_summary()
            case "full":
                return await tools.schema_full()
            case "entity":
                if not entity_name:
                    raise ValueError("entity_name required for 'entity' operation")
                return await tools.schema_entity(entity_name)
            case "entities":
                return await tools.schema_entities()
            case "detailed_entities":
                return await tools.schema_detailed_entities()
            case _:
                raise ValueError(f"Unknown schema operation: {operation}")

    @mcp.tool()
    async def data_operations(operation: str, entity_name: str, kwargs: str) -> dict:
        """Data operations tool

        Available operations:
        - explore: Explore entity data (supports field_count, limit)
        - sample_records: Get sample records (supports limit)
        - field_values: Get field value distribution (requires field_name, supports limit)
        - explore_entity_data: Comprehensive entity exploration

        Args:
            kwargs: String parameter due to MCP limitation - only primitive types allowed.
                   Format: "key1=value1,key2=value2" (e.g., "limit=5,field_count=10")
        """
        client = await get_client()
        tools = Tools(client, _config)
        parsed_kwargs = parse_kwargs_string(kwargs)

        match operation:
            case "explore":
                return await tools.data_explore(entity_name, **parsed_kwargs)
            case "sample_records":
                return await tools.data_sample_records(entity_name, **parsed_kwargs)
            case "field_values":
                validate_kwargs("field_values", parsed_kwargs, ["field_name"])
                field_name = parsed_kwargs.get("field_name")
                return await tools.data_field_values(
                    entity_name, field_name, **parsed_kwargs
                )
            case "explore_entity_data":
                return await tools.data_explore_entity_data(entity_name)
            case _:
                raise ValueError(f"Unknown data operation: {operation}")

    @mcp.tool()
    async def validation_operations(operation: str, kwargs: str) -> dict:
        """Validation operations tool

        Available operations:
        - validate_query: Validate GraphQL query (requires query)
        - suggest_fields: Get field suggestions (requires field_name, entity_name)
        - query_template: Generate safe query template (requires entity_name)

        Args:
            kwargs: String parameter due to MCP limitation - only primitive types allowed.
                   Format: "key1=value1,key2=value2" (e.g., "query=...,entity_name=subject")
        """
        client = await get_client()
        tools = Tools(client, _config)
        parsed_kwargs = parse_kwargs_string(kwargs)

        match operation:
            case "validate_query":
                validate_kwargs("validate_query", parsed_kwargs, ["query"])
                query = parsed_kwargs.get("query")
                return await tools.validate_query(query)
            case "suggest_fields":
                validate_kwargs(
                    "suggest_fields", parsed_kwargs, ["field_name", "entity_name"]
                )
                field_name = parsed_kwargs.get("field_name")
                entity_name = parsed_kwargs.get("entity_name")
                return await tools.suggest_fields(field_name, entity_name)
            case "query_template":
                validate_kwargs("query_template", parsed_kwargs, ["entity_name"])
                entity_name = parsed_kwargs.get("entity_name")
                return await tools.query_template(entity_name, **parsed_kwargs)
            case _:
                raise ValueError(f"Unknown validation operation: {operation}")

    @mcp.tool()
    async def execute_graphql(query: str) -> dict:
        """Execute GraphQL query against the Gen3 data commons

        Args:
            query: GraphQL query string
        """
        client = await get_client()
        tools = Tools(client, _config)
        return await tools.query_graphql(query)

    return mcp


async def cleanup():
    """Clean up global resources"""
    global _client
    if _client:
        try:
            await _client.__aexit__(None, None, None)
            logger.info("Client disconnected")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        finally:
            _client = None


def main():
    """Main entry point"""
    try:
        mcp = create_mcp_server()
        mcp.run(transport="stdio")
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Server failed: {e}")
        raise
    finally:
        try:
            asyncio.run(cleanup())
        except Exception as e:
            logger.error(f"Error during final cleanup: {e}")


if __name__ == "__main__":
    main()
