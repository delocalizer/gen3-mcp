"""Gen3 MCP server implementation."""

import logging

from mcp.server.fastmcp import FastMCP

from .config import get_config
from .consts import SERVER_NAME
from .exceptions import Gen3SchemaError
from .models import MCPResponse
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
    """Get processed schema summary with entity definitions and relationships.

    Returns:
        MCPResponse with SchemaExtract data on success, or error details on failure.
        The data field contains the complete schema extract with entities, relationships,
        and summary information for understanding the Gen3 data model structure.
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


# Future mcp.tool functions will follow the same MCPResponse pattern:

# @mcp.tool()
# async def validate_query(query: str) -> MCPResponse:
#     """Validate a GraphQL query against the Gen3 schema.
#
#     Args:
#         query: GraphQL query string to validate
#
#     Returns:
#         MCPResponse with validation results, errors, and suggestions
#     """
#     try:
#         from .query import get_query_service
#         service = get_query_service()
#         result = await service.validate_query(query)
#         return result.to_mcp_response()  # QueryValidationResult already has this method!
#     except Exception as e:
#         return MCPResponse(
#             status="error",
#             message="Failed to validate GraphQL query",
#             errors=[{"error_type": "validation_error", "message": str(e)}]
#         )


# @mcp.tool()
# async def execute_graphql(query: str) -> MCPResponse:
#     """Execute a GraphQL query against the Gen3 data commons.
#
#     Args:
#         query: Valid GraphQL query string to execute
#
#     Returns:
#         MCPResponse with query results or execution errors
#     """
#     try:
#         from .query import get_query_service
#         service = get_query_service()
#         result = await service.execute_graphql(query)
#
#         # Check if result contains errors
#         if result and "errors" in result:
#             return MCPResponse(
#                 status="error",
#                 message="GraphQL query executed with errors",
#                 errors=result["errors"],
#                 data=result.get("data"),
#                 suggestions=result.get("suggestion", {}).get("recommended_workflow", [])
#             )
#
#         return MCPResponse(
#             status="success",
#             message="GraphQL query executed successfully",
#             data=result,
#             next_steps={"data_analysis": "Analyze the returned data for insights"}
#         )
#
#     except Exception as e:
#         return MCPResponse(
#             status="error",
#             message="Failed to execute GraphQL query",
#             errors=[{"error_type": "execution_error", "message": str(e)}]
#         )


# @mcp.tool()
# async def generate_query_template(entity_name: str, include_relationships: bool = True) -> MCPResponse:
#     """Generate a GraphQL query template for a specific entity.
#
#     Args:
#         entity_name: Name of the entity to generate template for
#         include_relationships: Whether to include relationship examples
#
#     Returns:
#         MCPResponse with query template or entity not found error
#     """
#     try:
#         from .query import get_query_service
#         service = get_query_service()
#         result = await service.generate_query_template(entity_name, include_relationships)
#
#         if not result["exists"]:
#             return MCPResponse(
#                 status="error",
#                 message=f"Entity '{entity_name}' not found in schema",
#                 errors=[{
#                     "error_type": "entity_not_found",
#                     "entity": entity_name,
#                     "message": result["error"]
#                 }],
#                 suggestions=[f"Try '{suggestion['name']}' instead" for suggestion in result.get("suggestions", [])],
#                 next_steps={"get_entities": "Use get_schema_summary() to see all available entities"}
#             )
#
#         return MCPResponse(
#             status="success",
#             message=f"Generated query template for {entity_name}",
#             data={
#                 "entity_name": entity_name,
#                 "template": result["template"]
#             },
#             next_steps={
#                 "validate": "Use validate_query() to check the template",
#                 "customize": "Modify the template for your specific needs",
#                 "execute": "Use execute_graphql() to run the query"
#             }
#         )
#
#     except Exception as e:
#         return MCPResponse(
#             status="error",
#             message="Failed to generate query template",
#             errors=[{"error_type": "template_generation_error", "message": str(e)}]
#         )


async def main() -> None:
    """Run the MCP server."""
    # For development/testing
    response = await get_schema_summary()
    print(response.to_json())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
