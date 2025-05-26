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

    # ===== SCHEMA DISCOVERY TOOLS =====

#    @mcp.tool()
#    async def schema_summary() -> dict:
#        """Get schema summary - Overview of all entities and categories in the data commons"""
#        gen3_service = await get_gen3_service()
#        return await gen3_service.get_schema_summary()

    @mcp.tool()
    async def schema_full() -> dict:
        """Get complete schema - Full schema definitions for all entities"""
        gen3_service = await get_gen3_service()
        return await gen3_service.get_full_schema()

    @mcp.tool()
    async def schema_entity(entity_name: str) -> dict:
        """Get schema for specific entity - Detailed schema definition for a single entity type

        Args:
            entity_name: Name of the entity to get schema for
        """
        gen3_service = await get_gen3_service()
        return await gen3_service.get_entity_schema(entity_name)

    @mcp.tool()
    async def schema_describe_entities() -> dict:
        """Get detailed entity list with relationships - Entity summaries plus relationship mapping"""
        gen3_service = await get_gen3_service()
        return await gen3_service.get_detailed_entities()

    @mcp.tool()
    async def schema_entity_context(entity_name: str) -> dict:
        """Get entity context and hierarchical position - Understand entity relationships, GraphQL field names, and data flow position

        Args:
            entity_name: Name of the entity to get context for
        """
        gen3_service = await get_gen3_service()
        return await gen3_service.get_entity_context(entity_name)

    # ===== DATA EXPLORATION TOOLS =====

    @mcp.tool()
    async def data_explore(
        entity_name: str, limit: int = 5, field_count: int = 10
    ) -> dict:
        """Explore entity data with intelligent field selection - Quick data preview with automatically selected useful fields

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
        """Get sample records for entity - Raw data samples with basic field selection

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
        """Get field value distribution - Analyze unique values and their frequencies for a specific field

        Args:
            entity_name: Name of the entity
            field_name: Name of the field to analyze
            limit: Maximum number of values to return (default: 20)
        """
        query_service = await get_query_service()
        return await query_service.field_sample(entity_name, field_name, limit)

    @mcp.tool()
    async def data_explore_entity_data(entity_name: str) -> dict:
        """Comprehensive entity exploration - Complete entity analysis including schema, samples, and enum fields

        Args:
            entity_name: Name of the entity to explore comprehensively
        """
        gen3_service = await get_gen3_service()
        return await gen3_service.explore_entity_data(entity_name)

    # ===== GRAPHQL QUERY TOOLS =====

    @mcp.tool()
    async def query_template(
        entity_name: str, include_relationships: bool = True, max_fields: int = 20
    ) -> dict:
        """Generate safe query template - Create GraphQL query template with validated fields (recommended starting point)

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
            result["workflow_tip"] = (
                "Use validate_query() to check any modifications, then execute_graphql() to run the query"
            )

        return result

    @mcp.tool()
    async def validate_query(query: str) -> dict:
        """Validate GraphQL query - Check syntax and field names against schema before execution (use before execute_graphql)

        Args:
            query: GraphQL query string to validate
        """
        query_service = await get_query_service()
        result = await query_service.validate_query(query)

        # Add helpful suggestions to response
        if not result.get("valid"):
            result["suggestion"] = (
                "Use suggest_fields() to fix field name errors, or query_template() to generate a safe starting template"
            )

        return result

    @mcp.tool()
    async def suggest_fields(field_name: str, entity_name: str) -> dict:
        """Get field suggestions - Find similar field names when validation fails

        Args:
            field_name: Name of the field to find suggestions for
            entity_name: Name of the entity to search within
        """
        query_service = await get_query_service()
        return await query_service.suggest_similar_fields(field_name, entity_name)

    @mcp.tool()
    async def execute_graphql(query: str) -> dict:
        """Execute GraphQL query against the Gen3 data commons - Run validated GraphQL query (tip: use validate_query first to check syntax)

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

    @mcp.resource("gen3://workflow")
    def workflow_resource() -> str:
        """Recommended workflow for exploring Gen3 data commons"""
        return """Gen3 Data Commons Exploration Workflow

== DISCOVERY PHASE ==
1. schema_full() - Get overview of all entities and categories
2. schema_describe_entities() - Understand entity relationships
3. schema_entity_context(entity_name="subject") - Get hierarchical context and GraphQL field names
4. data_explore(entity_name="subject") - Preview data for key entities

== QUERY BUILDING PHASE ==
5. query_template(entity_name="subject") - Generate safe starting template
6. Modify the template as needed for your use case
7. validate_query(query="...") - Check syntax and field names
8. If validation fails: suggest_fields(field_name="...", entity_name="...")

== EXECUTION PHASE ==
9. execute_graphql(query="...") - Run your validated query
10. data_field_values(entity_name="...", field_name="...") - Analyze specific fields

== KEY PRINCIPLES ==
- Always start with templates rather than writing queries from scratch
- Use schema_entity_context() to understand backref field names for relationships
- Validate before executing to catch field name errors
- Use suggestions to fix invalid field names
- Explore relationships through schema_describe_entities() first

== COMMON PATTERNS ==
- Subject data: subject { id age_at_enrollment sex race ethnicity }
- File listings: file { id file_name file_size data_format submitter_id }
- With relationships: subject { samples { sample_type anatomic_site } }

This workflow prevents field name hallucinations and reduces query failures."""

    @mcp.resource("gen3://validation")
    def validation_resource() -> str:
        """Guide for using the GraphQL query validation tools"""
        return """Gen3 GraphQL Query Validation Tools

These tools help prevent field name hallucinations when working with Gen3 GraphQL queries:

== VALIDATION TOOLS ==

1. query_template(entity_name="...")
   - Generates safe query templates with guaranteed valid fields
   - Includes basic fields, important properties, and relationship examples
   - Use as starting point for building queries
   - Returns: Complete GraphQL query template

2. validate_query(query="...")
   - Validates all field names in a GraphQL query against the actual schema
   - Returns detailed errors and suggestions for invalid fields
   - Use before executing queries to catch mistakes early
   - Returns: Validation status, field-by-field analysis, suggestions

3. suggest_fields(field_name="...", entity_name="...")
   - Finds similar field names when you use an invalid field
   - Uses string similarity and pattern matching
   - Suggests alternative entity names if entity doesn't exist
   - Returns: Ranked suggestions with similarity scores

4. execute_graphql(query="...")
   - Executes validated GraphQL queries
   - Returns GraphQL response or execution errors
   - Best used after validation to ensure success

== RECOMMENDED WORKFLOW ==

Step 1: Start with a template
```
template_result = query_template(entity_name="subject")
query = template_result["template"]
```

Step 2: Modify the template as needed
```
query = '''
{
    subject(first: 10) {
        id
        age_at_enrollment
        invalid_field  # This will cause validation to fail
    }
}
'''
```

Step 3: Validate your changes
```
validation = validate_query(query=query)
if not validation["valid"]:
    print("Validation errors:", validation["errors"])
```

Step 4: Fix errors using suggestions
```
suggestions = suggest_fields(
    field_name="invalid_field",
    entity_name="subject"
)
print("Suggested fields:", suggestions["suggestions"])
```

Step 5: Execute the corrected query
```
result = execute_graphql(query=corrected_query)
```

== ERROR PREVENTION ==

This approach significantly reduces:
- GraphQL query syntax errors
- Field name hallucinations
- Entity name mistakes
- Relationship traversal errors

Always validate complex queries before execution to save time and ensure accuracy."""

    @mcp.resource("gen3://tools-by-category")
    def tools_by_category_resource() -> dict:
        """Tools organized by usage category for better discoverability"""
        return {
            "schema_discovery": {
                "description": "Understand the data model and available entities",
                "tools": [
                    {
                        "name": "schema_full",
                        "purpose": "Get overview of all entities and categories",
                        "when_to_use": "Starting exploration, understanding data structure",
                    },
                    {
                        "name": "schema_describe_entities",
                        "purpose": "Detailed entities with relationships",
                        "when_to_use": "Understanding how entities connect to each other",
                    },
                    {
                        "name": "schema_entity",
                        "purpose": "Complete schema for specific entity",
                        "when_to_use": "Need detailed field definitions for one entity",
                    },
                    {
                        "name": "schema_entity_context",
                        "purpose": "Entity context with hierarchical position and GraphQL field names",
                        "when_to_use": "Understanding entity relationships and how to query linked data",
                    },
                ],
            },
            "data_exploration": {
                "description": "Preview and analyze actual data content",
                "tools": [
                    {
                        "name": "data_explore",
                        "purpose": "Quick preview with smart field selection",
                        "when_to_use": "First look at entity data content",
                    },
                    {
                        "name": "data_sample_records",
                        "purpose": "Raw data samples with basic fields",
                        "when_to_use": "Need simple data preview",
                    },
                    {
                        "name": "data_field_values",
                        "purpose": "Analyze value distribution for specific field",
                        "when_to_use": "Understanding field contents, finding enum values",
                    },
                    {
                        "name": "data_explore_entity_data",
                        "purpose": "Comprehensive entity analysis",
                        "when_to_use": "Need complete understanding of entity",
                    },
                ],
            },
            "query_building": {
                "description": "Build and validate GraphQL queries safely",
                "tools": [
                    {
                        "name": "query_template",
                        "purpose": "Generate safe query starting templates",
                        "when_to_use": "ALWAYS start here for new queries",
                    },
                    {
                        "name": "validate_query",
                        "purpose": "Check query syntax and field names",
                        "when_to_use": "Before executing any modified query",
                    },
                    {
                        "name": "suggest_fields",
                        "purpose": "Fix invalid field names",
                        "when_to_use": "When validation shows field errors",
                    },
                ],
            },
            "query_execution": {
                "description": "Execute validated queries against the data commons",
                "tools": [
                    {
                        "name": "execute_graphql",
                        "purpose": "Run GraphQL queries",
                        "when_to_use": "After validation, to get actual data",
                    }
                ],
            },
            "workflow_guidance": {
                "discovery_workflow": [
                    "1. schema_full() - overview",
                    "2. schema_describe_entities() - relationships",
                    "3. schema_entity_context(entity_name) - hierarchical context",
                    "4. data_explore(entity_name) - preview data",
                ],
                "query_workflow": [
                    "1. query_template(entity_name) - safe starting point",
                    "2. validate_query(query) - check modifications",
                    "3. suggest_fields() if errors - fix field names",
                    "4. execute_graphql(query) - run validated query",
                ],
            },
        }

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
