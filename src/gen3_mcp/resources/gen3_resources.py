"""MCP resources using config properties consistently"""

from ..config.settings import Gen3Config


class Gen3Resources:
    """MCP resources using config properties consistently"""

    def __init__(self, config: Gen3Config):
        self.config = config

    def gen3_info(self) -> str:
        """Basic information about the Gen3 data commons instance"""
        return f"""Gen3 Data Commons MCP Server
        
Endpoint: {self.config.base_url}
Log Level: {self.config.log_level}

Available APIs:
- Schema: {self.config.schema_url}
- GraphQL: {self.config.graphql_url}
- Auth: {self.config.auth_url}

Use the tools below to fetch live data from these endpoints."""

    def gen3_endpoints(self) -> dict[str, str]:
        """Available API endpoints for the Gen3 data commons"""
        return {
            "base_url": self.config.base_url,
            "schema": self.config.schema_url,
            "graphql": self.config.graphql_url,
            "auth": self.config.auth_url,
        }

    def gen3_validation_guide(self) -> str:
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
