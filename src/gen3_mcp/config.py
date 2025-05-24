"""Configuration management and logging setup"""

import logging

from pydantic import ConfigDict, Field, computed_field
from pydantic_settings import BaseSettings


class Gen3Config(BaseSettings):
    """Type-safe configuration with pre-computed endpoints"""

    model_config = ConfigDict(env_prefix="GEN3_", case_sensitive=False, extra="ignore")

    base_url: str = Field(
        default="https://gen3.datacommons.io",
        description="Base URL for the Gen3 data commons",
    )
    credentials_file: str = Field(
        default="~/credentials.json", description="Path to the credentials JSON file"
    )
    log_level: str = Field(
        default="INFO",
        pattern=r"^(DEBUG|INFO|WARNING|ERROR)$",
        description="Logging level",
    )

    # HTTP settings
    timeout_seconds: int = Field(
        default=30, gt=0, le=300, description="HTTP request timeout in seconds"
    )

    # Cache settings
    schema_cache_ttl: int = Field(
        default=300, ge=60, le=3600, description="Schema cache TTL in seconds"
    )

    # Pre-computed API endpoint properties
    @computed_field
    @property
    def auth_url(self) -> str:
        """URL for fetching access tokens"""
        return f"{self.base_url}/user/credentials/cdis/access_token"

    @computed_field
    @property
    def graphql_url(self) -> str:
        """URL for GraphQL queries"""
        return f"{self.base_url}/api/v0/submission/graphql"

    @computed_field
    @property
    def schema_base_url(self) -> str:
        """URL for schema dictionary"""
        return f"{self.base_url}/api/v0/submission/_dictionary"

    @computed_field
    @property
    def schema_url(self) -> str:
        """URL for complete schema dictionary"""
        return f"{self.schema_base_url}/_all"

    def entity_schema_url(self, entity_name: str) -> str:
        """URL for specific entity schema"""
        return f"{self.schema_base_url}/{entity_name}"

    def __repr__(self) -> str:
        """String representation of the configuration"""
        return f"Gen3Config(base_url='{self.base_url}', log_level='{self.log_level}')"


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Configure logging for the entire application"""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Only configure if not already configured to avoid conflicts
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=numeric_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
    else:
        # Just set the level if logging is already configured
        logging.getLogger().setLevel(numeric_level)

    return logging.getLogger("gen3-mcp")


def gen3_info(config: Gen3Config) -> str:
    """Basic information about the Gen3 data commons instance"""
    return f"""Gen3 Data Commons MCP Server

Endpoint: {config.base_url}
Log Level: {config.log_level}

Available APIs:
- Schema: {config.schema_url}
- GraphQL: {config.graphql_url}
- Auth: {config.auth_url}

Use the tools below to fetch live data from these endpoints."""


def gen3_endpoints(config: Gen3Config) -> dict[str, str]:
    """Available API endpoints for the Gen3 data commons"""
    return {
        "base_url": config.base_url,
        "schema": config.schema_url,
        "graphql": config.graphql_url,
        "auth": config.auth_url,
    }


def gen3_validation_guide() -> str:
    """Guide for using the GraphQL query validation tools"""
    return """Gen3 GraphQL Query Validation Tools

These tools help prevent field name hallucinations when working with Gen3 GraphQL queries:

1. validation_operations(operation="validate_query", query="...")
   - Validates all field names in a GraphQL query against the actual schema
   - Returns detailed errors and suggestions for invalid fields
   - Use before executing queries to catch mistakes early

2. validation_operations(operation="suggest_fields", field_name="...", entity_name="...")
   - Finds similar field names when you use an invalid field
   - Uses string similarity and pattern matching
   - Suggests alternative entity names if entity doesn't exist

3. validation_operations(operation="query_template", entity_name="...")
   - Generates safe query templates with guaranteed valid fields
   - Includes basic fields, important properties, and relationship examples
   - Use as starting point for building queries

Recommended Workflow:
1. Start with validation_operations(operation="query_template", entity_name="subject")
2. Modify the template as needed
3. Use validation_operations(operation="validate_query", query="...") to check your changes
4. If validation fails, use validation_operations(operation="suggest_fields", ...) to fix errors
5. Execute the validated query with execute_graphql(query="...")

Example:
```
# Get a template
template = validation_operations(operation="query_template", entity_name="subject")

# Modify it
query = "{ subject { id gender invalid_field } }"

# Validate
validation = validation_operations(operation="validate_query", query=query)

# Fix errors using suggestions
if not validation["valid"]:
    suggestions = validation_operations(operation="suggest_fields",
                                      field_name="invalid_field",
                                      entity_name="subject")
```

This approach significantly reduces GraphQL query errors and field name hallucinations."""
