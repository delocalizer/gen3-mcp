"""Main MCP server implementation"""

import asyncio
import logging

from mcp.server.fastmcp import FastMCP

from .client import Gen3Client
from .config import Gen3Config, setup_logging
from .data import Gen3Service
from .query import QueryService

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

    # ===== SCHEMA TOOLS =====

    @mcp.tool()
    async def schema_summary() -> dict:
        """Get schema summary"""
        gen3_service = await get_gen3_service()
        return await gen3_service.get_schema_summary()

    @mcp.tool()
    async def schema_full() -> dict:
        """Get complete schema"""
        gen3_service = await get_gen3_service()
        return await gen3_service.get_full_schema()

    @mcp.tool()
    async def schema_entity(entity_name: str) -> dict:
        """Get schema for specific entity

        Args:
            entity_name: Name of the entity to get schema for
        """
        gen3_service = await get_gen3_service()
        return await gen3_service.get_entity_schema(entity_name)

    @mcp.tool()
    async def schema_entities() -> dict:
        """Get list of all entities"""
        gen3_service = await get_gen3_service()
        entities = await gen3_service.get_entity_names()
        return {"entities": entities}

    @mcp.tool()
    async def schema_describe_entities() -> dict:
        """Get detailed entity list with relationships"""
        gen3_service = await get_gen3_service()
        return await gen3_service.get_detailed_entities()

    # ===== BASIC DATA TOOLS =====

    @mcp.tool()
    async def data_explore(
        entity_name: str, limit: int = 5, field_count: int = 10
    ) -> dict:
        """Explore entity data with intelligent field selection

        Args:
            entity_name: Name of the entity to explore
            limit: Maximum number of records to return (default: 5)
            field_count: Maximum number of fields to include (default: 10)
        """
        gen3_service = await get_gen3_service()
        # Get sample records
        result = await gen3_service.get_sample_records(entity_name, limit)
        result["entity"] = entity_name
        return result

    @mcp.tool()
    async def data_sample_records(entity_name: str, limit: int = 5) -> dict:
        """Get sample records for entity

        Args:
            entity_name: Name of the entity to sample
            limit: Maximum number of records to return (default: 5)
        """
        gen3_service = await get_gen3_service()
        return await gen3_service.get_sample_records(entity_name, limit)

    @mcp.tool()
    async def data_field_values(
        entity_name: str, field_name: str, limit: int = 20
    ) -> dict:
        """Get field value distribution

        Args:
            entity_name: Name of the entity
            field_name: Name of the field to analyze
            limit: Maximum number of values to return (default: 20)
        """
        query_service = await get_query_service()
        return await query_service.field_sample(
            entity_name, field_name, limit
        )

    @mcp.tool()
    async def data_explore_entity_data(entity_name: str) -> dict:
        """Comprehensive entity exploration

        Args:
            entity_name: Name of the entity to explore comprehensively
        """
        gen3_service = await get_gen3_service()
        return await gen3_service.explore_entity_data(entity_name)

    # Validation operations
    @mcp.tool()
    async def validate_query(query: str) -> dict:
        """Validate GraphQL query

        Args:
            query: GraphQL query string to validate
        """
        query_service = await get_query_service()
        return await query_service.validate_query(query)

    @mcp.tool()
    async def suggest_fields(field_name: str, entity_name: str) -> dict:
        """Get field suggestions

        Args:
            field_name: Name of the field to find suggestions for
            entity_name: Name of the entity to search within
        """
        query_service = await get_query_service()
        return await query_service.suggest_similar_fields(field_name, entity_name)

    @mcp.tool()
    async def query_template(
        entity_name: str, include_relationships: bool = True, max_fields: int = 20
    ) -> dict:
        """Generate safe query template

        Args:
            entity_name: Name of the entity to generate template for
            include_relationships: Whether to include relationships (default: True)
            max_fields: Maximum number of fields to include (default: 20)
        """
        query_service = await get_query_service()
        return await query_service.generate_query_template(
            entity_name, include_relationships, max_fields
        )

    @mcp.tool()
    async def execute_graphql(query: str) -> dict:
        """Execute GraphQL query against the Gen3 data commons

        Args:
            query: GraphQL query string
        """
        query_service = await get_query_service()
        result = await query_service.execute_graphql(query)
        if result is None:
            return {"error": "Query execution failed"}
        return result

    # ===== RESOURCES =====

    @mcp.resource("gen3://info")
    def info_resource() -> str:
        """Basic information about the Gen3 data commons instance"""
        config = _config if _config else Gen3Config()
        return f"""Gen3 Data Commons MCP Server

Endpoint: {config.base_url}
Log Level: {config.log_level}

Available APIs:
- Schema: {config.schema_url}
- GraphQL: {config.graphql_url}
- Auth: {config.auth_url}

Use the tools below to fetch live data from these endpoints."""

    @mcp.resource("gen3://endpoints")
    def endpoints_resource() -> dict[str, str]:
        """Available API endpoints for the Gen3 data commons"""
        config = _config if _config else Gen3Config()
        return {
            "base_url": config.base_url,
            "schema": config.schema_url,
            "graphql": config.graphql_url,
            "auth": config.auth_url,
        }

    @mcp.resource("gen3://validation")
    def validation_resource() -> str:
        """Guide for using the GraphQL query validation tools"""
        return """Gen3 GraphQL Query Validation Tools

These tools help prevent field name hallucinations when working with Gen3 GraphQL queries:

1. validate_query(query="...")
   - Validates all field names in a GraphQL query against the actual schema
   - Returns detailed errors and suggestions for invalid fields
   - Use before executing queries to catch mistakes early

2. suggest_fields(field_name="...", entity_name="...")
   - Finds similar field names when you use an invalid field
   - Uses string similarity and pattern matching
   - Suggests alternative entity names if entity doesn't exist

3. query_template(entity_name="...")
   - Generates safe query templates with guaranteed valid fields
   - Includes basic fields, important properties, and relationship examples
   - Use as starting point for building queries

Recommended Workflow:
1. Start with query_template(entity_name="subject")
2. Modify the template as needed
3. Use validate_query(query="...") to check your changes
4. If validation fails, use suggest_fields(...) to fix errors
5. Execute the validated query with execute_graphql(query="...")

Example:
```
# Get a template
template = query_template(entity_name="subject")

# Modify it
query = "{ subject { id gender invalid_field } }"

# Validate
validation = validate_query(query=query)

# Fix errors using suggestions
if not validation["valid"]:
    suggestions = suggest_fields(field_name="invalid_field",
                                          entity_name="subject")
```

This approach significantly reduces GraphQL query errors and field name hallucinations."""

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
