"""Main MCP server implementation."""

import asyncio
import json
import logging

from mcp.server.fastmcp import FastMCP

from .client import Gen3Client
from .config import Gen3Config, setup_logging
from .query import QueryService
from .resources import register_resources
from .schema import SchemaService
from .schema_extract import SchemaExtract

logger = logging.getLogger("gen3-mcp.main")

# Global state
_config: Gen3Config | None = None
_client: Gen3Client | None = None
_gen3_service: SchemaService | None = None
_query_service: QueryService | None = None


def create_mcp_server() -> FastMCP:
    """Create and configure the MCP server.

    Returns:
        Configured FastMCP server instance.
    """
    logger.debug("Creating MCP server")
    mcp = FastMCP("gen3")

    # Register resources
    register_resources(mcp, _config)

    # ===== SCHEMA DISCOVERY TOOLS =====

    @mcp.tool()
    async def schema_summary() -> dict:
        """Get complete schema information - all entities with fields, relationships,
        query patterns, and hierarchical context in one comprehensive response.
        """
        logger.debug("schema_summary called")
        gen3_service = await get_gen3_service()
        full_schema = await gen3_service.get_schema_full()
        schema_extract = SchemaExtract.from_full_schema(full_schema)
        result = json.loads(repr(schema_extract))
        logger.info(f"schema_summary completed with {len(result)} entities")
        return result

    # ===== GRAPHQL QUERY TOOLS =====

    @mcp.tool()
    async def query_template(
        entity_name: str, include_relationships: bool = True, max_fields: int = 20
    ) -> dict:
        """Generate safe query template - create GraphQL query template with
        validated fields (recommended starting point)

        Args:
            entity_name: Name of the entity to generate template for
            include_relationships: Whether to include relationships (default: True)
            max_fields: Maximum number of fields to include (default: 20)
        """
        logger.debug(f"query_template called for entity: {entity_name}")
        query_service = await get_query_service()
        result = await query_service.generate_query_template(
            entity_name, include_relationships, max_fields
        )

        # Add workflow guidance in response
        if result.get("exists"):
            result["next_step"] = (
                "Use validate_query() to check any modifications, then execute_graphql() to run the query"
            )

        logger.info(f"query_template completed for entity: {entity_name}")
        return result

    @mcp.tool()
    async def validate_query(query: str) -> dict:
        """Validate GraphQL query - check syntax and field names against schema
        before execution (use before execute_graphql)

        Args:
            query: GraphQL query string to validate
        """
        logger.debug("validate_query called")
        query_service = await get_query_service()
        result = await query_service.validate_query(query)
        logger.info(f"validate_query completed - valid: {result.get('valid', False)}")
        return result

    @mcp.tool()
    async def execute_graphql(query: str) -> dict:
        """Execute GraphQL query against the Gen3 data commons - run validated
        GraphQL query (tip: use validate_query first to check syntax)

        Args:
            query: GraphQL query string
        """
        logger.debug("execute_graphql called")
        query_service = await get_query_service()
        result = await query_service.execute_graphql(query)

        if result is None:
            logger.warning("execute_graphql returned None")
            return {
                "error": "Query execution failed",
                "suggestion": "Try validate_query() to check syntax or query_template() to generate a safe template",
            }

        # Check for GraphQL errors and provide guidance
        if result.get("errors"):
            logger.warning(
                f"execute_graphql returned errors: {len(result['errors'])} errors"
            )
            result["suggestion"] = (
                "Query returned GraphQL errors. Use validate_query() to check field names and syntax."
            )
        else:
            logger.info("execute_graphql completed successfully")

        return result

    logger.info("MCP server created")
    return mcp


async def get_gen3_service() -> SchemaService:
    """Get or create the SchemaService instance.

    Returns:
        SchemaService instance.
    """
    global _gen3_service

    if _gen3_service is None:
        logger.debug("Creating new SchemaService")
        await _get_ready()
        _gen3_service = SchemaService(_client, _config)
        logger.info("Initialized SchemaService")

    return _gen3_service


async def get_query_service() -> QueryService:
    """Get or create the QueryService instance.

    Returns:
        QueryService instance.
    """
    global _query_service

    if _query_service is None:
        logger.debug("Creating new QueryService")
        await _get_ready()
        gen3_service = await get_gen3_service()  # Ensure dependency exists
        _query_service = QueryService(_client, _config, gen3_service)
        logger.info("Initialized QueryService")

    return _query_service


async def cleanup() -> None:
    """Clean up global resources."""
    global _client, _gen3_service, _query_service

    logger.debug("Starting cleanup")

    if _client:
        try:
            await _client.__aexit__(None, None, None)
            logger.info("Client disconnected")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        finally:
            _client = None
            _gen3_service = None
            _query_service = None

    logger.debug("Cleanup completed")


def main() -> None:
    """Main entry point."""
    logger.debug("Starting main")

    try:
        mcp = create_mcp_server()
        logger.info("Starting MCP server")
        mcp.run(transport="stdio")
    except Exception as e:
        logger.error(f"Server failed: {e}")
        raise
    finally:
        try:
            logger.debug("Running final cleanup")
            asyncio.run(cleanup())
        except Exception as e:
            logger.error(f"Error during final cleanup: {e}")


async def _get_ready() -> None:
    """Lazy and idempotent initialization of config and client dependencies.

    Ensures _config and _client globals are initialized.
    """
    global _config, _client

    if _config is None:
        logger.debug("Initializing config")
        _config = Gen3Config()
        setup_logging(_config.log_level)
        logger.info(f"Config initialized for {_config.base_url}")

    if _client is None:
        logger.debug("Initializing client")
        _client = Gen3Client(_config)
        await _client.__aenter__()
        logger.info(f"Connected to Gen3 instance: {_config.base_url}")


if __name__ == "__main__":
    main()
