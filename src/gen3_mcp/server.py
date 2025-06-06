"""Gen3 MCP server implementation."""

import logging

from mcp.server.fastmcp import FastMCP

from .config import get_config
from .consts import SERVER_NAME
from .exceptions import Gen3SchemaError
from .models import MCPResponse
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
async def get_schema_summary() -> MCPResponse:
    """Discover the data model structure of a Gen3 data commons.

    This is your starting point! Get an overview of all available data types
    (entities) in the Gen3 data commons, including their relationships and
    key properties. Use this to understand what data is available before
    building queries.

    Returns:
        Complete schema information with entity names, relationships, and
        property details. Use the entity_names list to see what data types
        you can query.

    Workflow: **Start here** → generate_query_template → validate_query → execute_graphql
    """
    try:
        logger.info("Fetching schema extract for get_schema_summary tool")
        manager = get_schema_manager()
        extract = await manager.get_schema_extract()

        # Convert SchemaExtract to dict for MCPResponse data field
        extract_data = extract.to_json()

        entity_count = len(extract_data)
        entity_names = list(extract_data.keys())

        return MCPResponse(
            status="success",
            message=f"Retrieved schema extract with {entity_count} entities",
            data={
                "schema_extract": extract_data,
                "entity_count": entity_count,
                "entity_names": entity_names,
            },
            suggestions=[
                "Use the entity_names to explore specific entities",
                "Check relationships between entities using the links information",
                "Look at required_fields and enum_fields for each entity",
            ],
            next_steps={
                "explore_entity": "Use the entity names to dive deeper into specific data types",
                "query_building": "Use generate_query_template() to create GraphQL queries for these entities",
                "validation": "Use validate_query() to check GraphQL query syntax",
            },
            metadata={
                "schema_source": manager.config.schema_url,
                "cached": True,  # Schema manager uses caching
            },
        )

    except Gen3SchemaError as e:
        logger.error(f"Schema error in get_schema_summary: {e}")
        return MCPResponse(
            status="error",
            message="Failed to fetch schema from Gen3 data commons",
            errors=[
                {
                    "error_type": "schema_fetch_error",
                    "message": str(e),
                    "category": "Gen3SchemaError",
                }
            ],
            suggestions=[
                "Check that the Gen3 data commons URL is accessible",
                "Verify your network connection",
                "Confirm the schema endpoint is available",
            ],
            next_steps={
                "troubleshooting": [
                    "1. Check connectivity to the Gen3 data commons",
                    "2. Verify the configured base_url is correct",
                    "3. Try again in a few moments if this was a temporary network issue",
                ]
            },
            metadata={"attempted_url": manager.config.schema_url},
        )

    except Exception as e:
        logger.error(f"Unexpected error in get_schema_summary: {e}")
        return MCPResponse(
            status="error",
            message="Unexpected error while processing schema",
            errors=[
                {
                    "error_type": "unexpected_error",
                    "message": str(e),
                    "category": type(e).__name__,
                }
            ],
            suggestions=[
                "This appears to be an internal error",
                "Try the request again",
                "Check the server logs for more details",
            ],
            next_steps={
                "recovery": [
                    "1. Retry the get_schema_summary() call",
                    "2. If the issue persists, this may be a server-side problem",
                ]
            },
        )


@mcp.tool()
async def generate_query_template(
    entity_name: str, include_relationships: bool = True, max_fields: int = 20
) -> MCPResponse:
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

    Workflow: get_schema_summary → **You are here** → validate_query → execute_graphql
    """
    logger.info(f"Generating query template for entity: {entity_name}")

    service = get_query_service()
    result = await service.generate_query_template(
        entity_name, include_relationships, max_fields
    )

    # Convert service result to MCPResponse
    if not result["exists"]:
        # Entity not found case
        suggestions = [
            f"Try '{suggestion['name']}' instead"
            for suggestion in result.get("suggestions", [])
        ]

        return MCPResponse(
            status="error",
            message=f"Entity '{entity_name}' not found in schema",
            errors=[
                {
                    "error_type": "entity_not_found",
                    "entity": entity_name,
                    "message": result["error"],
                }
            ],
            suggestions=suggestions,
            next_steps={
                "get_entities": "Use get_schema_summary() to see all available entities",
                "try_suggestion": "Use one of the suggested similar entity names",
            },
            metadata={
                "attempted_entity": entity_name,
                "available_suggestions": result.get("suggestions", []),
            },
        )

    # Success case
    return MCPResponse(
        status="success",
        message=f"Generated query template for {entity_name}",
        data={
            "entity_name": entity_name,
            "template": result["template"],
            "included_relationships": include_relationships,
            "max_fields_used": max_fields,
        },
        suggestions=[
            "Copy the template and modify it for your specific needs",
            "Use validate_query() to check the template before execution",
            "Add or remove fields as needed for your use case",
        ],
        next_steps={
            "validate": "Use validate_query() to check the template syntax",
            "customize": "Modify the template fields and relationships as needed",
            "execute": "Use execute_graphql() to run the customized query",
        },
        metadata={
            "generation_params": {
                "include_relationships": include_relationships,
                "max_fields": max_fields,
            }
        },
    )


@mcp.tool()
async def validate_query(query: str) -> MCPResponse:
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

    Workflow: get_schema_summary → generate_query_template → **You are here** → execute_graphql
    """
    logger.info(
        f"Validating GraphQL query: {query[:100]}{'...' if len(query) > 100 else ''}"
    )

    service = get_query_service()
    result = await service.validate_query(query)

    return result.to_mcp_response()


@mcp.tool()
async def execute_graphql(query: str) -> MCPResponse:
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

    Workflow: get_schema_summary → generate_query_template → validate_query → **You are here**
    """
    logger.info(
        f"Executing GraphQL query: {query[:100]}{'...' if len(query) > 100 else ''}"
    )

    service = get_query_service()
    result = await service.execute_graphql(query)

    # Convert service result to MCPResponse
    if "errors" in result:
        return MCPResponse(
            status="error",
            message="GraphQL query executed with errors",
            errors=result["errors"],
            data=result.get("data"),
            suggestions=result.get("suggestion", {}).get("recommended_workflow", []),
        )

    return MCPResponse(
        status="success", message="GraphQL query executed successfully", data=result
    )


async def main() -> None:
    """Run the MCP server."""
    mcp.run(transport="stdio")
    # For development/testing
    # response = await get_schema_summary()
    # print(response.to_json())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
