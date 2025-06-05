"""Gen3 MCP server implementation."""

import json

from mcp.server.fastmcp import FastMCP

from .client import get_client
from .config import get_config
from .consts import SERVER_NAME
from .schema_extract import get_schema_extract

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
async def get_schema_summary() -> str:
    client = get_client()
    schema = await client.get_json(client.config.schema_url)
    extract = await get_schema_extract(schema)
    extract = await get_schema_extract(schema)
    return json.dumps(extract.model_dump())
    # return SchemaExtractResponse(isError=False, content=repr(extract), schema_extract=extract)


# @mcp.tool()
# async def gen3_base_url() -> str:
# """Return the configured Gen3 data commons base URL"""
#    return get_config().base_url


# @mcp.tool()
# async def gen3_full_schema() -> dict:
#    """Get the full schema of a Gen3 data commons.
#
#    This tool provides access to a JSON document defining the schema of
#    a Gen3 data commons. Entities (nodes) are named in top-level keys, each
#    associated with the JSON Schema object that describes the entity.
#
#    Each entity description includes:
#    - Relationship definitions that specify links in the data model graph
#    - Field definitions that specify property data types and validation rules
#    - Controlled vocabularies and enumerated values
#
#    System-level metadata and reusable schema fragments are distinguished by
#    top-level keys with leading underscores (e.g., _definitions, _settings,
#    _terms).
#
#    Example extract of the schema structure (depth-filtered):
#    ```json
#    {
#      "study": {
#        "title": "Study",
#        "type": "object",
#        "properties": {
#          "submitter_id": {"type": "string"},
#          "code": {"type": "string"},
#          "disease_type": {"type": "string"},
#          "primary_site": {"type": "string"}
#        },
#        "links": [
#          {
#            "name": "projects",
#            "backref": "studies",
#            "label": "member_of",
#            "target_type": "project"
#          }
#        ]
#      },
#      "subject": {
#        "title": "Subject",
#        "type": "object",
#        "properties": {
#          "submitter_id": {"type": "string"},
#          "gender": {"enum": ["female", "male", "unknown"]},
#          "race": {"type": "string"},
#          "ethnicity": {"type": "string"}
#        },
#        "links": [
#          {
#            "name": "studies",
#            "backref": "subjects",
#            "label": "member_of",
#            "target_type": "study"
#          }
#        ]
#      },
#      "sample": {
#        "title": "Sample",
#        "type": "object",
#        "properties": {
#          "submitter_id": {"type": "string"},
#          "sample_type": {"type": "string"},
#          "composition": {"type": "string"}
#        },
#        "links": [
#          {
#            "name": "subjects",
#            "backref": "samples",
#            "label": "derived_from",
#            "target_type": "subject"
#          }
#        ]
#      }
#    }
#    ```
#
#    IMPORTANT: use sparingly as the result is likely to be quite large
#
#    ## Examples of how to use this information:
#    1. Extract the entity names to list all entities available in the commons
#    2. Extract links information for an entity to understand its relationships
#    3. Extract properties information for an entity to understand its available
#       attributes, their data types and validation rules
#    4. Follow links between entities to understand the graph data model
#    """
#    client = get_client()
#    schema = await client.get_json(client.config.schema_url)
#    return schema


async def main() -> None:
    """Run the MCP server."""
    # mcp.run(transport="stdio")
    summary = await get_schema_summary()
    print(summary)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
