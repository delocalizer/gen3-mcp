"""MCP server resources for working with a Gen3 data commons."""

import logging
from typing import Any

from .config import Config

logger = logging.getLogger("gen3-mcp.resources")


def get_endpoints_resource(config: Config | None = None) -> dict[str, str]:
    """Available API endpoints for the Gen3 data commons.

    Args:
        config: Config instance. If None, creates new instance.

    Returns:
        Dict with endpoint URLs.
    """
    if config is None:
        config = Config()

    return {
        "base_url": config.base_url,
        "schema": config.schema_url,
        "graphql": config.graphql_url,
        "auth": config.auth_url,
    }


def get_info_resource(config: Config | None = None) -> str:
    """Basic information about the Gen3 data commons instance.

    Args:
        config: Config instance. If None, creates new instance.

    Returns:
        Info string about the Gen3 instance.
    """
    if config is None:
        config = Config()

    return f"""Gen3 Data Commons MCP Server

Endpoint: {config.base_url}
Log Level: {config.log_level}

Available APIs:
- Schema: {config.schema_url}
- GraphQL: {config.graphql_url}
- Auth: {config.auth_url}

Use the tools below to fetch live data from these endpoints."""


def get_tools_by_category_resource() -> dict[str, Any]:
    """Tools organized by usage category for better discoverability.

    Returns:
        Dict with tools categorized by usage.
    """
    return {
        "schema_discovery": {
            "description": "Understand the detailed data model, and example query patterns",
            "tools": [
                {
                    "name": "annotated_schema_structure",
                    "purpose": "Get complete schema with all entities, relationships, and query patterns",
                    "when_to_use": "Starting exploration, understanding data structure, and getting entity-specific context for constructing new queries",
                },
            ],
        },
        "query_building": {
            "description": "Build and validate GraphQL queries safely",
            "tools": [
                {
                    "name": "query_template",
                    "purpose": "Generate safe query starting templates",
                    "when_to_use": "Start here for new queries",
                },
                {
                    "name": "validate_query",
                    "purpose": "Check query syntax and field names",
                    "when_to_use": "ALWAYS use before executing any modified query",
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
                "1. annotated_schema_structure() - complete schema with all entity details and relationships",
            ],
            "query_workflow": [
                "1. query_template(entity_name) - safe starting point",
                "2. validate_query(query) - check modifications",
                "3. execute_graphql(query) - run validated query",
            ],
        },
    }


def get_workflow_resource() -> str:
    """Recommended workflow for exploring Gen3 data commons.

    Returns:
        Workflow description string.
    """
    return """Gen3 Data Commons Exploration Workflow

== DISCOVERY PHASE ==
1. annotated_schema_structure() - Get complete schema with all entities, relationships,
   and query patterns. This includes hierarchical context and GraphQL fields for all entities.
   TIP: use the patterns in <entity>.query_patterns.complex_queries as example GraphQL queries
   to start data exploration

== DATA DISCOVERY - QUERY BUILDING PHASE ==
2. query_template(entity_name=<entity>) - Generate safe starting template
3. Modify the template as needed for your use case
4. validate_query(query="...") - ALWAYS Check syntax and field names before execution
   (on failure, take note of suggestions in the response)
5. execute_graphql(query="...") - Run your validated query

== KEY PRINCIPLES ==
- Use annotated_schema_structure to understand relationships, discover entity names,
  and learn example query patterns for each entity
- The count of relationships in each annotated_schema_structure entity is a direct
  measure of how connected that entity is
- Use query_template as the basis for constructing queries rather than
  writing queries from scratch
- ALWAYS validate queries before executing to catch field name errors
- Use suggestions to fix invalid entity and field names

== COMMONS-AGNOSTIC APPROACH ==
- Entity and field names vary by commons - always discover them first
- Start with annotated_schema_structure() to see what entities exist in your specific
  commons, and what available fields and relations they have

This workflow prevents field name hallucinations and reduces query failures."""


def register_resources(mcp, config: Config | None = None) -> None:
    """Register all resources with the MCP server.

    Args:
        mcp: FastMCP instance to register resources with.
        config: Config instance. If None, creates new instance.
    """
    logger.debug("Registering MCP resources")

    @mcp.resource("gen3://endpoints")
    def endpoints_resource() -> dict[str, str]:
        """Available API endpoints for the Gen3 data commons."""
        return get_endpoints_resource(config)

    @mcp.resource("gen3://info")
    def info_resource() -> str:
        """Basic information about the Gen3 data commons instance."""
        return get_info_resource(config)

    @mcp.resource("gen3://tools-by-category")
    def tools_by_category_resource() -> dict[str, Any]:
        """Tools organized by usage category for better discoverability."""
        return get_tools_by_category_resource()

    @mcp.resource("gen3://workflow")
    def workflow_resource() -> str:
        """Recommended workflow for exploring Gen3 data commons."""
        return get_workflow_resource()

    logger.info("Registered 4 MCP resources")
