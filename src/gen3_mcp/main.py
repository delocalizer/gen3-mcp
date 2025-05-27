"""Main MCP server implementation"""

import asyncio
import logging

from mcp.server.fastmcp import FastMCP

from .client import Gen3Client
from .config import Gen3Config, setup_logging
from .schema import Gen3Service
from .query import QueryService
from .resources import register_resources

logger = logging.getLogger("gen3-mcp.main")

# Global state
_config: Gen3Config | None = None
_client: Gen3Client | None = None
_gen3_service: Gen3Service | None = None
_query_service: QueryService | None = None


async def _get_ready():
    """Lazy and idempotent initialization of config and client dependencies.

    Ensures _config and _client globals are initialized.
    """
    global _config, _client

    if _config is None:
        _config = Gen3Config()
        setup_logging(_config.log_level)

    if _client is None:
        _client = Gen3Client(_config)
        await _client.__aenter__()
        logger.info(f"Connected to Gen3 instance: {_config.base_url}")


async def get_gen3_service() -> Gen3Service:
    """Get or create the Gen3Service instance"""
    global _gen3_service
    if _gen3_service is None:
        await _get_ready()
        _gen3_service = Gen3Service(_client, _config)
        logger.info("Initialized Gen3Service")
    return _gen3_service


async def get_query_service() -> QueryService:
    """Get or create the QueryService instance"""
    global _query_service
    if _query_service is None:
        await _get_ready()
        gen3_service = await get_gen3_service()  # Ensure dependency exists
        _query_service = QueryService(_client, _config, gen3_service)
        logger.info("Initialized QueryService")
    return _query_service


def create_mcp_server() -> FastMCP:
    """Create and configure the MCP server"""
    mcp = FastMCP("gen3")

    # Register resources
    register_resources(mcp, _config)

    # ===== SCHEMA DISCOVERY TOOLS =====

    @mcp.tool()
    async def schema_summary() -> dict:
        """Get schema summary - an overview of all entities in the data commons,
        and the relationships and links between them.
        """
        gen3_service = await get_gen3_service()
        return await gen3_service.get_schema_summary()

    @mcp.tool()
    async def schema_entity_context(entity_name: str) -> dict:
        """Get detailed entity context - field names, relationships to ancestor
        entities, backrefs that define inverse relationships, example queries,
        and more.

        Args:
            entity_name: Name of the entity to get context for
        """
        gen3_service = await get_gen3_service()
        return await gen3_service.get_entity_context(entity_name)

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
        query_service = await get_query_service()
        result = await query_service.generate_query_template(
            entity_name, include_relationships, max_fields
        )

        # Add workflow guidance in response
        if result.get("exists"):
            result["next_step"] = (
                "Use validate_query() to check any modifications, then execute_graphql() to run the query"
            )

        return result

    @mcp.tool()
    async def validate_query(query: str) -> dict:
        """Validate GraphQL query - check syntax and field names against schema
        before execution (use before execute_graphql)

        Args:
            query: GraphQL query string to validate
        """
        query_service = await get_query_service()
        result = await query_service.validate_query(query)

        return result

    @mcp.tool()
    async def execute_graphql(query: str) -> dict:
        """Execute GraphQL query against the Gen3 data commons - run validated
        GraphQL query (tip: use validate_query first to check syntax)

        Args:
            query: GraphQL query string
        """
        query_service = await get_query_service()
        result = await query_service.execute_graphql(query)

        if result is None:
            return {
                "error": "Query execution failed",
                "suggestion": "Try validate_query() to check syntax or query_template() to generate a safe template",
            }

        # Check for GraphQL errors and provide guidance
        if result.get("errors"):
            result["suggestion"] = (
                "Query returned GraphQL errors. Use validate_query() to check field names and syntax."
            )

        return result

    return mcp


async def cleanup():
    """Clean up global resources"""
    global _client, _gen3_service, _query_service
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


def main():
    """Main entry point"""
    try:
        mcp = create_mcp_server()
        mcp.run(transport="stdio")
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
