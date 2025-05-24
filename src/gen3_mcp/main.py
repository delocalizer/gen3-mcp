"""Main MCP server implementation"""

import asyncio
import logging
import signal
import sys
from contextlib import asynccontextmanager

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
from .utils import parse_kwargs_string, validate_kwargs_for_operation

logger = logging.getLogger("gen3-mcp.main")

# Global references for proper cleanup
_client_instance: Gen3Client | None = None
_config: Gen3Config | None = None


@asynccontextmanager
async def client_context():
    """Context manager for the global client"""
    global _client_instance, _config

    if _client_instance is None:
        if _config is None:
            _config = Gen3Config()
        _client_instance = Gen3Client(_config)
        await _client_instance.__aenter__()

    try:
        yield _client_instance
    finally:
        # Don't close here since it's a global instance
        pass


def create_mcp_server() -> FastMCP:
    """Create and configure the MCP server with all tools and resources"""
    global _config
    _config = Gen3Config()

    # Set up logging
    setup_logging(_config.log_level)
    logger.info(f"Starting Gen3 MCP Server with endpoint: {_config.base_url}")

    # Create MCP server
    mcp = FastMCP("gen3")

    # Register resources
    @mcp.resource("gen3://info")
    def gen3_info_resource() -> str:
        return gen3_info(_config)

    @mcp.resource("gen3://endpoints")
    def gen3_endpoints_resource() -> dict[str, str]:
        return gen3_endpoints(_config)

    @mcp.resource("gen3://validation")
    def gen3_validation_guide_resource() -> str:
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
        - list_available_entities: Get detailed entity list with relationships
        """
        async with client_context() as client:
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
                case "list_available_entities":
                    return await tools.schema_list_available_entities()
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
        async with client_context() as client:
            tools = Tools(client, _config)

            # Parse kwargs string with robust parsing and type conversion
            parsed_kwargs = parse_kwargs_string(kwargs)

            match operation:
                case "explore":
                    return await tools.data_explore(entity_name, **parsed_kwargs)
                case "sample_records":
                    return await tools.data_sample_records(entity_name, **parsed_kwargs)
                case "field_values":
                    validate_kwargs_for_operation(
                        "field_values", parsed_kwargs, ["field_name"]
                    )
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
        async with client_context() as client:
            tools = Tools(client, _config)

            # Parse kwargs string with robust parsing and type conversion
            parsed_kwargs = parse_kwargs_string(kwargs)

            match operation:
                case "validate_query":
                    validate_kwargs_for_operation(
                        "validate_query", parsed_kwargs, ["query"]
                    )
                    query = parsed_kwargs.get("query")
                    return await tools.validation_validate_query_fields(query)
                case "suggest_fields":
                    validate_kwargs_for_operation(
                        "suggest_fields", parsed_kwargs, ["field_name", "entity_name"]
                    )
                    field_name = parsed_kwargs.get("field_name")
                    entity_name = parsed_kwargs.get("entity_name")
                    return await tools.validation_suggest_similar_fields(
                        field_name, entity_name
                    )
                case "query_template":
                    validate_kwargs_for_operation(
                        "query_template", parsed_kwargs, ["entity_name"]
                    )
                    entity_name = parsed_kwargs.get("entity_name")
                    return await tools.validation_get_query_template(
                        entity_name, **parsed_kwargs
                    )
                case _:
                    raise ValueError(f"Unknown validation operation: {operation}")

    @mcp.tool()
    async def execute_graphql(query: str) -> dict:
        """Execute GraphQL query against the Gen3 data commons

        Args:
            query: GraphQL query string
        """
        async with client_context() as client:
            tools = Tools(client, _config)
            return await tools.query_graphql(query)

    return mcp


async def cleanup():
    """Cleanup global resources"""
    global _client_instance
    if _client_instance:
        await _client_instance.__aexit__(None, None, None)
        _client_instance = None
        logger.info("Cleanup completed")


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info("Shutting down...")
    if _client_instance:
        asyncio.create_task(cleanup())
    sys.exit(0)


def main():
    """Main entry point"""
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        mcp = create_mcp_server()
        mcp.run(transport="stdio")
    except Exception as e:
        logger.error(f"Server failed to start: {e}")
        raise
    finally:
        # Ensure cleanup on exit
        if _client_instance:
            asyncio.run(cleanup())


if __name__ == "__main__":
    main()
