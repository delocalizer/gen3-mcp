"""Main MCP server implementation"""

import asyncio
import logging
import signal
import sys
from typing import Optional
from contextlib import asynccontextmanager
from mcp.server.fastmcp import FastMCP

from .config import Gen3Config, setup_logging
from .client import Gen3Client
from .tools import UnifiedTools
from .resources import Gen3Resources

logger = logging.getLogger("gen3-mcp.main")

# Global references for proper cleanup
_client_instance: Optional[Gen3Client] = None
_config: Optional[Gen3Config] = None


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

    # Initialize resources
    resources = Gen3Resources(_config)

    # Register resources
    @mcp.resource("gen3://info")
    def gen3_info() -> str:
        return resources.gen3_info()

    @mcp.resource("gen3://endpoints")
    def gen3_endpoints() -> dict[str, str]:
        return resources.gen3_endpoints()

    @mcp.resource("gen3://validation")
    def gen3_validation_guide() -> str:
        return resources.gen3_validation_guide()

    # Register consolidated tools
    @mcp.tool()
    async def schema_operations(operation: str, entity_name: str = None) -> dict:
        """Unified schema operations tool

        Available operations:
        - summary: Get schema summary
        - full: Get complete schema
        - entity: Get schema for specific entity (requires entity_name)
        - entities: Get list of all entities
        - list_available_entities: Get detailed entity list with relationships
        """
        async with client_context() as client:
            tools = UnifiedTools(client, _config)

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
    async def data_operations(operation: str, entity_name: str, **kwargs) -> dict:
        """Unified data operations tool

        Available operations:
        - explore: Explore entity data (supports field_count, limit)
        - sample_records: Get sample records (supports limit)
        - field_values: Get field value distribution (requires field_name, supports limit)
        - explore_entity_data: Comprehensive entity exploration
        """
        async with client_context() as client:
            tools = UnifiedTools(client, _config)

            match operation:
                case "explore":
                    return await tools.data_explore(entity_name, **kwargs)
                case "sample_records":
                    return await tools.data_sample_records(entity_name, **kwargs)
                case "field_values":
                    field_name = kwargs.get("field_name")
                    if not field_name:
                        raise ValueError(
                            "field_name required for 'field_values' operation"
                        )
                    return await tools.data_field_values(
                        entity_name, field_name, **kwargs
                    )
                case "explore_entity_data":
                    return await tools.data_explore_entity_data(entity_name)
                case _:
                    raise ValueError(f"Unknown data operation: {operation}")

    @mcp.tool()
    async def validation_operations(operation: str, **kwargs) -> dict:
        """Unified validation operations tool

        Available operations:
        - validate_query: Validate GraphQL query (requires query)
        - suggest_fields: Get field suggestions (requires field_name, entity_name)
        - query_template: Generate safe query template (requires entity_name)
        """
        async with client_context() as client:
            tools = UnifiedTools(client, _config)

            match operation:
                case "validate_query":
                    query = kwargs.get("query")
                    if not query:
                        raise ValueError(
                            "query required for 'validate_query' operation"
                        )
                    return await tools.validation_validate_query_fields(query)
                case "suggest_fields":
                    field_name = kwargs.get("field_name")
                    entity_name = kwargs.get("entity_name")
                    if not field_name or not entity_name:
                        raise ValueError(
                            "field_name and entity_name required for 'suggest_fields' operation"
                        )
                    return await tools.validation_suggest_similar_fields(
                        field_name, entity_name
                    )
                case "query_template":
                    entity_name = kwargs.get("entity_name")
                    if not entity_name:
                        raise ValueError(
                            "entity_name required for 'query_template' operation"
                        )
                    return await tools.validation_get_query_template(
                        entity_name, **kwargs
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
            tools = UnifiedTools(client, _config)
            return await tools.query_graphql(query)

    # Legacy tool compatibility (keeping original names for backward compatibility)
    @mcp.tool()
    async def get_schema_summary() -> dict:
        """Get schema summary (legacy compatibility)"""
        return await schema_operations("summary")

    @mcp.tool()
    async def get_full_schema() -> dict:
        """Get full schema (legacy compatibility)"""
        return await schema_operations("full")

    @mcp.tool()
    async def get_entity_schema(entity_name: str) -> dict:
        """Get entity schema (legacy compatibility)"""
        return await schema_operations("entity", entity_name)

    @mcp.tool()
    async def list_available_entities() -> dict:
        """List available entities (legacy compatibility)"""
        return await schema_operations("list_available_entities")

    @mcp.tool()
    async def query_graphql(query: str) -> dict:
        """Execute GraphQL query (legacy compatibility)"""
        return await execute_graphql(query)

    @mcp.tool()
    async def get_field_values(
        entity_name: str, field_name: str, limit: int = 20
    ) -> dict:
        """Get field values (legacy compatibility)"""
        return await data_operations(
            "field_values", entity_name, field_name=field_name, limit=limit
        )

    @mcp.tool()
    async def get_sample_records(entity_name: str, limit: int = 5) -> dict:
        """Get sample records (legacy compatibility)"""
        return await data_operations("sample_records", entity_name, limit=limit)

    @mcp.tool()
    async def explore_entity_data(entity_name: str) -> dict:
        """Explore entity data (legacy compatibility)"""
        return await data_operations("explore_entity_data", entity_name)

    @mcp.tool()
    async def validate_query_fields(query: str) -> dict:
        """Validate query fields (legacy compatibility)"""
        return await validation_operations("validate_query", query=query)

    @mcp.tool()
    async def suggest_similar_fields(field_name: str, entity_name: str) -> dict:
        """Suggest similar fields (legacy compatibility)"""
        return await validation_operations(
            "suggest_fields", field_name=field_name, entity_name=entity_name
        )

    @mcp.tool()
    async def get_query_template(
        entity_name: str, include_relationships: bool = True
    ) -> dict:
        """Get query template (legacy compatibility)"""
        return await validation_operations(
            "query_template",
            entity_name=entity_name,
            include_relationships=include_relationships,
        )

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
