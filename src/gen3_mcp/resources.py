"""MCP server resources for working with a Gen3 data commons"""
from .config import Gen3Config


@mcp.resource("gen3://info")
@mcp.resource("gen3://endpoints")
@mcp.resource("gen3://tools-by-category")
@mcp.resource("gen3://workflow")
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


def endpoints_resource() -> dict[str, str]:
    """Available API endpoints for the Gen3 data commons"""
    config = _config if _config else Gen3Config()
    return {
        "base_url": config.base_url,
        "schema": config.schema_url,
        "graphql": config.graphql_url,
        "auth": config.auth_url,
    }


def workflow_resource() -> str:
    """Recommended workflow for exploring Gen3 data commons"""
    return """Gen3 Data Commons Exploration Workflow

== DISCOVERY PHASE ==
1. schema_summary() - Get overview of all entities and categories
2. schema_entity_context(entity_name="subject") - Get hierarchical context and GraphQL field names

== DATA DISCOVERY - QUERY BUILDING PHASE ==
3. query_template(entity_name="subject") - Generate safe starting template
4. Modify the template as needed for your use case
5. validate_query(query="...") - Check syntax and field names
6. If validation fails: suggest_fields(field_name="...", entity_name="...")
7. execute_graphql(query="...") - Run your validated query

== KEY PRINCIPLES ==
- Use schema_summary to understand backref field names for relationships
- Always start with templates rather than writing queries from scratch
- Validate before executing to catch field name errors
- Use suggestions to fix invalid field names

== COMMON PATTERNS ==
- Subject data: subject { id age_at_enrollment sex race ethnicity }
- File listings: file { id file_name file_size data_format submitter_id }
- With relationships: subject { samples { sample_type anatomic_site } }

This workflow prevents field name hallucinations and reduces query failures."""


def tools_by_category_resource() -> dict:
    """Tools organized by usage category for better discoverability"""
    return {
        "schema_discovery": {
            "description": "Understand the data model and available entities",
            "tools": [
                {
                    "name": "schema_summary",
                    "purpose": "Get overview of all entities and categories",
                    "when_to_use": "Starting exploration, understanding data structure",
                },
                {
                    "name": "schema_entity_context",
                    "purpose": "Entity context with hierarchical position and GraphQL field names",
                    "when_to_use": "Understanding entity relationships and how to query linked data",
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
                "1. schema_summary() - overview",
                "2. schema_entity_context(entity_name) - hierarchical context",
            ],
            "query_workflow": [
                "1. query_template(entity_name) - safe starting point",
                "2. validate_query(query) - check modifications",
                "3. suggest_fields() if errors - fix field names",
                "4. execute_graphql(query) - run validated query",
            ],
        },
    }
