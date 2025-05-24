# Gen3 MCP Server

A Model Context Protocol (MCP) server for interacting with Gen3 data commons, with GraphQL query validation to reduce hallucinations.

## Install and Configure 

These instructions are for using the server in a chat client. For development, see [Development](DEVELOPMENT.md).

```bash
# Clone the repository
git clone <repository-url>

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Create Gen3 credentials file

Create a file `credentials.json` containing your Gen3 API key:

```json
{
  "api_key": "xxxx",
  "key_id": "xxxx"
}
```

### Configure chat client

Example for Claude Desktop `~/.config/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "gen3-mcp-server": {
      "command": "uvx",
      "args": [
        "--from", "/path/to/gen3-mcp",
        "gen3-mcp"
      ],
      "env": {
        "GEN3_CREDENTIALS_FILE": "/path/to/credentials.json",
        "GEN3_BASE_URL": "https://gen3.datacommons.io/",
        "GEN3_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

## Example Usage in chat client

**prompt**

> Explore the data commons at https://gen3.datacommons.io.
>
> Summarize the data model.
>
> Construct and run a query that returns data about 5 participants.

**response**

![Response](response.png "Response")


## Available Tools

The MCP server provides the following tools:

### Schema Tools (`schema_*`)
- `schema_summary()` - Get schema summary with entity counts
- `schema_full()` - Get complete schema definition
- `schema_entity(entity_name)` - Get schema for specific entity
- `schema_entities()` - Get list of all entities
- `schema_describe_entities()` - Get detailed entity list with relationships

### Data Tools (`data_*`)
- `data_explore(entity_name, limit=5, field_count=10)` - Explore entity with intelligent field selection
- `data_sample_records(entity_name, limit=5)` - Get sample records
- `data_field_values(entity_name, field_name, limit=20)` - Analyze field value distribution
- `data_explore_entity_data(entity_name)` - Comprehensive entity exploration

### Validation Tools 
- `validate_query(query)` - Validate GraphQL query against schema
- `suggest_fields(field_name, entity_name)` - Get suggestions for field names
- `query_template(entity_name, include_relationships=True, max_fields=20)` - Generate safe query templates

### GraphQL Tool
- `execute_graphql(query)` - Execute GraphQL query against Gen3 data commons

### Resources
- `gen3://info` - Information about the Gen3 instance
- `gen3://endpoints` - Available API endpoints
- `gen3://validation` - GraphQL validation guidance


## Acknowledgments

Built with [MCP (Model Context Protocol)](https://github.com/modelcontextprotocol) and designed for [Gen3 Data Commons](https://gen3.org/).
