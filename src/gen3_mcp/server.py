"""Gen3 MCP server implementation."""

import logging

from mcp.server.fastmcp import FastMCP

from .config import get_config
from .consts import SERVER_NAME
from .models import Response
from .query import get_query_service
from .schema import get_schema_manager

logger = logging.getLogger("gen3-mcp.server")

mcp = FastMCP(
    name=SERVER_NAME,
    instructions="""
    Gen3 MCP server.

    This MCP server allows you to:
    1. Explore and understand the schema of a Gen3 data commons.
    2. Discover and explore data in a Gen3 data commons.
    """,
    log_level=get_config().log_level,
)


# https://www.reddit.com/r/ClaudeAI/comments/1hdxq5o/mcp_claude_desktop_and_resources/
# Currently Claude desktop treats resources like files that you
# must actively attach to a chat with the '+' icon. Because we want
# auto-discovery we implement everything here as `mcp.tool`


@mcp.tool()
async def get_schema_summary() -> Response:
    """Discover the data model structure of a Gen3 data commons.

    This is your starting point! Get an overview of all available nodes
    (entities) in the Gen3 data commons, including their relationships and
    metadata. Field details are omitted for conciseness - use get_schema_entity
    to explore specific entities in detail.

    Returns:
        Schema overview with entity names, relationships, and metadata.

    Workflow: **Start here** → get_schema_entity → generate_query_template → validate_query → execute_graphql
    """
    logger.info("Fetching schema extract for get_schema_summary tool")

    try:
        manager = get_schema_manager()
        schema_extract = await manager.get_schema_extract()

        return Response(
            status="success",
            message="Schema summary generated - use get_schema_entity() for detailed field information",
            data=schema_extract.to_summary_json(),
            suggestions=[
                "Use get_schema_entity() to get detailed field information for specific entities",
                "Look for entities with high child_count as good starting points for queries",
                "Check entity relationships to understand data model structure",
            ],
            metadata={"entity_count": len(schema_extract)},
        )
    except Exception as e:
        return Response.from_error(e)


@mcp.tool()
async def get_schema_entity(entity_name: str) -> Response:
    """Get detailed information for a specific entity including all fields.

    Retrieves complete entity definition with all scalar fields, relationships,
    and metadata. Use this after get_schema_summary() to explore specific
    entities in detail before building queries.

    Args:
        entity_name: Name of the entity to retrieve (from get_schema_summary)

    Returns:
        Complete entity data including all fields, relationships, and metadata.

    Workflow: get_schema_summary → **You are here** → generate_query_template → validate_query → execute_graphql
    """
    logger.info(f"Fetching entity details for: {entity_name}")

    try:
        manager = get_schema_manager()
        entity = await manager.get_entity(entity_name)

        return Response(
            status="success",
            message=f"Entity '{entity_name}' details retrieved - ready for query building",
            data=entity.model_dump(),
            suggestions=[
                "Use field information to build targeted GraphQL queries",
                "Check required_fields and enum_fields for query construction",
                "Use generate_query_template() to create a starting query for this entity",
            ],
            metadata={
                "entity_name": entity_name,
                "field_count": len(entity.fields),
                "relationship_count": len(entity.relationships),
            },
        )
    except Exception as e:
        return Response.from_error(e)


@mcp.tool()
async def generate_query_template(
    entity_name: str, include_relationships: bool = True, max_fields: int = 20
) -> Response:
    """Generate a ready-to-use GraphQL query template for any data type.

    Takes an entity name (from get_schema_summary) and creates a complete,
    valid GraphQL query with the most useful fields and relationships.
    This gives you a working starting point that you can customize.

    Args:
        entity_name: Name of the data type to query (e.g., 'subject', 'sample')
        include_relationships: Whether to include related data types in template
        max_fields: Maximum number of fields to include (controls template size)

    Returns:
        A complete GraphQL query template ready to use or customize.
        Copy the template from data.template and modify as needed.

    Workflow: get_schema_summary → get_schema_entity → **You are here** → validate_query → execute_graphql
    """
    logger.info(f"Generating query template for entity: {entity_name}")

    try:
        service = get_query_service()
        template_data = await service.generate_query_template(
            entity_name, include_relationships, max_fields
        )

        return Response(
            status="success",
            message=f"Query template generated for entity '{entity_name}' - ready to validate and execute",
            data=template_data,
            suggestions=[
                "Copy the template and modify as needed for your use case",
                "Adjust field selection based on your data requirements",
                "Always run validate_query before executing",
            ],
        )
    except Exception as e:
        return Response.from_error(e)


@mcp.tool()
async def validate_query(query: str) -> Response:
    """Check if your GraphQL query is valid before executing it.

    Validates your GraphQL query syntax and verifies that all entities and
    fields exist in the schema. Catches errors early and provides specific
    suggestions for fixing issues. Always validate before executing to
    avoid runtime errors.

    Args:
        query: The GraphQL query string to validate

    Returns:
        Validation results with detailed error messages and fix suggestions
        if issues are found. A valid query means it's safe to execute.

    Workflow: get_schema_summary → get_schema_entity → generate_query_template → **You are here** → execute_graphql

    ## IMPORTANT
    **Always** run this before calling execute_graphql
    """
    logger.info(
        f"Validating GraphQL query: {query[:100]}{'...' if len(query) > 100 else ''}"
    )

    try:
        service = get_query_service()
        # validate_query returns None on success (void pattern)
        await service.validate_query(query)

        return Response(
            status="success",
            message="Query validation passed - query is ready for execution",
            data=None,  # Void return pattern - no data needed on successful validation
            suggestions=["Query is valid and ready to execute with execute_graphql"],
            metadata={"query": query, "valid": True},
        )
    except Exception as e:
        return Response.from_error(e)


@mcp.tool()
async def execute_graphql(query: str) -> Response:
    """Execute your GraphQL query and retrieve data from the Gen3 data commons.

    Runs your validated GraphQL query against the Gen3 data commons and
    returns the actual data. This is where you get real research data back.
    Make sure your query is validated first to avoid errors.

    Args:
        query: A valid GraphQL query string (validated with validate_query)

    Returns:
        The data results from your query. On success, data contains the
        requested information. On error, includes specific error details
        and suggestions for fixing the query.

    Workflow: get_schema_summary → get_schema_entity → generate_query_template → validate_query → **You are here**

    ## IMPORTANT
    **Always** run validate_query on the query before calling this.
    """
    logger.info(
        f"Executing GraphQL query: {query[:100]}{'...' if len(query) > 100 else ''}"
    )

    try:
        service = get_query_service()
        query_results = await service.execute_graphql(query)

        return Response(
            status="success",
            message="GraphQL query executed successfully - data retrieved from Gen3 data commons",
            data=query_results,
            suggestions=[
                "Explore the returned data structure for insights",
                "Modify query to adjust fields or add filters as needed",
                "Use relationship fields to explore connected data",
            ],
        )
    except Exception as e:
        return Response.from_error(e)


def main() -> None:
    """Run the MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
