import logging
import httpx
import os
import json
import asyncio
from datetime import datetime, timedelta, UTC
from dataclasses import dataclass
from typing import Any, Dict, Optional
from contextlib import asynccontextmanager
from mcp.server.fastmcp import FastMCP
from gen3_validator import Gen3SchemaValidator

USER_AGENT: str = "gen3-mcp/1.0"
TOKEN_REFRESH_MARGIN: int = 300  # Refresh token 5 minutes before expiry


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Configure logging for the entire application"""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        force=True,  # Override any existing configuration
    )
    return logging.getLogger("gen3-mcp")


@dataclass
class Config:
    base_url: str = "https://gen3.datacommons.io"
    credentials_file: str = "~/credentials.json"
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables"""
        return cls(
            base_url=os.getenv("BASE_URL", cls.base_url),
            credentials_file=os.getenv("CREDENTIALS_FILE", cls.credentials_file),
            log_level=os.getenv("LOG_LEVEL", cls.log_level).upper(),
        )

    @property
    def auth_url(self) -> str:
        """URL for fetching access tokens"""
        return f"{self.base_url}/user/credentials/cdis/access_token"

    @property
    def graphql_url(self) -> str:
        """URL for GraphQL queries"""
        return f"{self.base_url}/api/v0/submission/graphql"

    @property
    def schema_base_url(self) -> str:
        """URL for schema dictionary"""
        return f"{self.base_url}/api/v0/submission/_dictionary"

    @property
    def schema_url(self) -> str:
        """URL for schema dictionary"""
        return f"{self.schema_base_url}/_all"


# Initialize config and logging
config = Config.from_env()
logger = setup_logging(config.log_level)


@dataclass
class TokenInfo:
    """Container for access token and its metadata"""

    access_token: str
    expires_at: datetime
    refresh_threshold: datetime

    @classmethod
    def from_response(
        cls, token_data: dict, refresh_margin_seconds: int = 300
    ) -> "TokenInfo":
        """Create TokenInfo from API response"""
        # Gen3 tokens typically last 30 minutes
        expires_in = token_data.get("expires_in", 1800)  # Default 30 minutes
        issued_at = datetime.now(UTC)
        expires_at = issued_at + timedelta(seconds=expires_in)
        refresh_threshold = expires_at - timedelta(seconds=refresh_margin_seconds)

        return cls(
            access_token=token_data["access_token"],
            expires_at=expires_at,
            refresh_threshold=refresh_threshold,
        )

    def needs_refresh(self) -> bool:
        """Check if token needs to be refreshed"""
        return datetime.now(UTC) >= self.refresh_threshold

    def is_expired(self) -> bool:
        """Check if token is expired"""
        return datetime.now(UTC) >= self.expires_at


class Gen3Client:
    """
    Manages authenticated connections to Gen3 data commons with automatic token refresh
    """

    def __init__(self, config: Config):
        self.config = config
        self.client: Optional[httpx.AsyncClient] = None
        self.token_info: Optional[TokenInfo] = None
        self.credentials: Optional[dict] = None
        self._lock = asyncio.Lock()  # Prevent concurrent token refreshes

    async def __aenter__(self):
        """Async context manager entry"""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()

    async def initialize(self):
        """Initialize the client with credentials and token"""
        # Load credentials
        try:
            with open(os.path.expanduser(self.config.credentials_file)) as f:
                self.credentials = json.load(f)
        except FileNotFoundError:
            raise ValueError(
                f"Credentials file not found: {self.config.credentials_file}"
            )
        except json.JSONDecodeError:
            raise ValueError(
                f"Invalid JSON in credentials file: {self.config.credentials_file}"
            )

        # Create HTTP client
        self.client = httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT}, timeout=30.0, follow_redirects=True
        )

        # Get initial access token
        await self._refresh_token()

    async def close(self):
        """Close the HTTP client"""
        if self.client:
            await self.client.aclose()
            self.client = None

    async def _refresh_token(self):
        """Refresh the access token"""
        if not self.credentials:
            raise ValueError("No credentials available")

        try:
            response = await self.client.post(
                self.config.auth_url, json=self.credentials
            )
            response.raise_for_status()
            token_data = response.json()

            self.token_info = TokenInfo.from_response(token_data, TOKEN_REFRESH_MARGIN)

            # Update client headers
            self.client.headers.update(
                {"Authorization": f"bearer {self.token_info.access_token}"}
            )

            logger.info(f"Token refreshed, expires at {self.token_info.expires_at}")

        except Exception as e:
            logger.error(f"Failed to refresh token: {e}")
            raise

    async def _ensure_valid_token(self):
        """Ensure we have a valid token, refreshing if necessary"""
        async with self._lock:  # Prevent concurrent refreshes
            if not self.token_info or self.token_info.needs_refresh():
                logger.debug("Token needs refresh")
                await self._refresh_token()
            elif self.token_info.is_expired():
                logger.warning("Token is expired, forcing refresh")
                await self._refresh_token()

    async def get_json(
        self, endpoint: str, authenticated: bool = True, **kwargs
    ) -> dict[str, Any] | None:
        """Make GET request and return JSON, optionally authenticated"""
        url = (
            endpoint
            if endpoint.startswith("http")
            else f"{self.config.base_url}{endpoint}"
        )

        try:
            if authenticated:
                await self._ensure_valid_token()

            response = await self.client.get(url, **kwargs)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"GET {endpoint} failed: {e}")
            return None

    async def post_json(self, endpoint: str, **kwargs) -> dict[str, Any] | None:
        """Make authenticated POST request and return JSON"""
        await self._ensure_valid_token()
        url = (
            endpoint
            if endpoint.startswith("http")
            else f"{self.config.base_url}{endpoint}"
        )

        try:
            response = await self.client.post(url, **kwargs)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"POST {endpoint} failed: {e}")
            return None


# Global client instance
_client_instance: Optional[Gen3Client] = None


async def get_client() -> Gen3Client:
    """Get or create the global client instance"""
    global _client_instance
    if _client_instance is None:
        _client_instance = Gen3Client(config)
        await _client_instance.initialize()
    return _client_instance


@asynccontextmanager
async def client_context():
    """Context manager for the global client"""
    client = await get_client()
    try:
        yield client
    finally:
        # Don't close here since it's a global instance
        pass


# Initialize MCP server
mcp = FastMCP("gen3")


# Resources for reference/context (lightweight)
@mcp.resource("gen3://info")
def gen3_info() -> str:
    """Basic information about the Gen3 data commons instance."""
    return f"""Gen3 Data Commons MCP Server
    
Endpoint: {config.base_url}
Log Level: {config.log_level}

Available APIs:
- Schema: {config.schema_url}
- GraphQL: {config.graphql_url}
- Auth: {config.auth_url}

Use the tools below to fetch live data from these endpoints."""


@mcp.resource("gen3://endpoints")
def gen3_endpoints() -> dict[str, str]:
    """Available API endpoints for the Gen3 data commons."""
    return {
        "schema": config.schema_url,
        "graphql": config.graphql_url,
        "auth": config.auth_url,
    }


@mcp.resource("gen3://validation")
def gen3_validation_guide() -> str:
    """Guide for using the GraphQL query validation tools."""
    return """Gen3 GraphQL Query Validation Tools

These tools help prevent field name hallucinations when working with Gen3 GraphQL queries:

1. validate_query_fields(query: str)
   - Validates all field names in a GraphQL query against the actual schema
   - Returns detailed errors and suggestions for invalid fields
   - Use before executing queries to catch mistakes early

2. suggest_similar_fields(field_name: str, entity_name: str)
   - Finds similar field names when you use an invalid field
   - Uses string similarity and pattern matching
   - Suggests alternative entity names if entity doesn't exist

3. get_query_template(entity_name: str, include_relationships: bool = True)
   - Generates safe query templates with guaranteed valid fields
   - Includes basic fields, important properties, and relationship examples
   - Use as starting point for building queries

Recommended Workflow:
1. Start with get_query_template() for a safe foundation
2. Modify the template as needed
3. Use validate_query_fields() to check your changes
4. If validation fails, use suggest_similar_fields() to fix errors
5. Execute the validated query with query_graphql()

Example:
```
# Get a template
template = get_query_template("subject")

# Modify it
query = "{ subject { id gender invalid_field } }"

# Validate
validation = validate_query_fields(query)

# Fix errors using suggestions
if not validation["valid"]:
    suggestions = suggest_similar_fields("invalid_field", "subject")
```

This approach significantly reduces GraphQL query errors and field name hallucinations."""


# Tools for actions/data fetching
@mcp.tool()
async def get_schema_summary() -> dict[str, Any]:
    """Get a summary of the Gen3 data commons schema structure."""
    logger.info("Fetching schema summary")

    async with client_context() as client:
        full_schema = await client.get_json(config.schema_url, authenticated=False)

        if not full_schema:
            return {"error": "Failed to fetch schema"}

        return {
            "endpoint": config.base_url,
            "total_entities": len(full_schema) if isinstance(full_schema, dict) else 0,
            "entity_names": list(full_schema.keys())
            if isinstance(full_schema, dict)
            else [],
            "schema_url": config.schema_url,
        }


@mcp.tool()
async def get_full_schema() -> dict[str, Any] | None:
    """
    Get the complete data model and dictionary schema of the Gen3 data commons.
    Warning: This can be a large response.
    """
    logger.info("Fetching full schema")

    async with client_context() as client:
        return await client.get_json(config.schema_url, authenticated=False)


@mcp.tool()
async def get_entity_schema(entity_name: str) -> dict[str, Any] | None:
    """
    Get the schema for a specific entity type.

    Args:
        entity_name: Name of the entity (e.g., 'case', 'sample', 'file')
    """
    logger.info(f"Fetching schema for entity '{entity_name}'")

    async with client_context() as client:
        return await client.get_json(
            f"{config.schema_base_url}/{entity_name}", authenticated=False
        )


@mcp.tool()
async def list_available_entities() -> dict[str, Any]:
    """List all available entity types in the data commons with their relationships."""
    logger.info("Fetching entity list with relationships")

    async with client_context() as client:
        full_schema = await client.get_json(config.schema_url, authenticated=False)

        if not full_schema or not isinstance(full_schema, dict):
            return {"error": "Failed to fetch schema or invalid format"}

        entities = {}
        all_links = []  # Track all relationships for summary

        for entity_name, entity_data in full_schema.items():
            if isinstance(entity_data, dict):
                # Extract link information
                links = entity_data.get("links", [])
                processed_links = []

                for link in links:
                    if isinstance(link, dict):
                        # Handle subgroup links (common in Gen3)
                        if "subgroup" in link:
                            for sublink in link.get("subgroup", []):
                                if isinstance(sublink, dict):
                                    link_info = {
                                        "target_entity": sublink.get("target_type"),
                                        "relationship": sublink.get(
                                            "label", "related_to"
                                        ),
                                        "multiplicity": sublink.get(
                                            "multiplicity", "unknown"
                                        ),
                                        "required": sublink.get("required", False),
                                        "backref": sublink.get("backref"),
                                    }
                                    processed_links.append(link_info)

                                    # Add to global links for relationship mapping
                                    all_links.append(
                                        {
                                            "from": entity_name,
                                            "to": sublink.get("target_type"),
                                            "relationship": sublink.get(
                                                "label", "related_to"
                                            ),
                                            "multiplicity": sublink.get(
                                                "multiplicity", "unknown"
                                            ),
                                        }
                                    )
                        else:
                            # Direct link
                            link_info = {
                                "target_entity": link.get("target_type"),
                                "relationship": link.get("label", "related_to"),
                                "multiplicity": link.get("multiplicity", "unknown"),
                                "required": link.get("required", False),
                                "backref": link.get("backref"),
                            }
                            processed_links.append(link_info)

                            # Add to global links
                            all_links.append(
                                {
                                    "from": entity_name,
                                    "to": link.get("target_type"),
                                    "relationship": link.get("label", "related_to"),
                                    "multiplicity": link.get("multiplicity", "unknown"),
                                }
                            )

                entities[entity_name] = {
                    "title": entity_data.get("title", ""),
                    "description": entity_data.get("description", ""),
                    "category": entity_data.get("category", ""),
                    "properties_count": len(entity_data.get("properties", {})),
                    "links": processed_links,
                    "links_count": len(processed_links),
                }

        # Build relationship summary
        relationship_summary = {}
        for link in all_links:
            rel_type = link["relationship"]
            if rel_type not in relationship_summary:
                relationship_summary[rel_type] = []
            relationship_summary[rel_type].append(f"{link['from']} -> {link['to']}")

        # Find entities by category for better organization
        entities_by_category = {}
        for entity_name, entity_info in entities.items():
            category = entity_info["category"] or "uncategorized"
            if category not in entities_by_category:
                entities_by_category[category] = []
            entities_by_category[category].append(entity_name)

        return {
            "total_entities": len(entities),
            "entities": entities,
            "entities_by_category": entities_by_category,
            "relationship_summary": relationship_summary,
            "total_relationships": len(all_links),
            "common_graphql_patterns": {
                "hierarchical_query": "project -> study -> subject -> sample -> files",
                "file_with_subject": "Use links to query: file { subjects { age_at_enrollment sex } }",
                "subject_with_samples": "Use links to query: subject { samples { sample_type anatomic_site } }",
            },
        }


@mcp.tool()
async def query_graphql(query: str) -> dict[str, Any] | None:
    """
    Execute a GraphQL query against the Gen3 data commons.

    Args:
        query: GraphQL query string
    """
    async with client_context() as client:
        logger.info("Executing GraphQL query")
        return await client.post_json(config.graphql_url, json={"query": query})


@mcp.tool()
async def get_field_values(
    entity_name: str, field_name: str, limit: int = 20
) -> dict[str, Any]:
    """
    Get actual values used in a specific field for an entity type.

    Args:
        entity_name: Name of the entity (e.g., 'imaging_file', 'subject')
        field_name: Name of the field (e.g., 'data_type', 'sex')
        limit: Maximum number of unique values to return
    """
    logger.info(f"Fetching field values for {entity_name}.{field_name}")

    # GraphQL query to get distinct values for a field
    query = f"""
    {{
        {entity_name}(first: 100) {{
            {field_name}
        }}
    }}
    """

    async with client_context() as client:
        result = await client.post_json(config.graphql_url, json={"query": query})

        if not result or "data" not in result:
            return {"error": f"Failed to fetch data for {entity_name}.{field_name}"}

        # Extract field values and count occurrences
        field_values = {}
        entity_data = result["data"].get(entity_name, [])

        for record in entity_data:
            value = record.get(field_name)
            if value is not None:
                field_values[str(value)] = field_values.get(str(value), 0) + 1

        # Sort by frequency and limit results
        sorted_values = sorted(field_values.items(), key=lambda x: x[1], reverse=True)[
            :limit
        ]

        return {
            "entity": entity_name,
            "field": field_name,
            "total_records_checked": len(entity_data),
            "unique_values_found": len(field_values),
            "values": dict(sorted_values),
            "query_used": query.strip(),
        }


@mcp.tool()
async def get_sample_records(entity_name: str, limit: int = 5) -> dict[str, Any]:
    """
    Get sample records for an entity to see actual field names and values.

    Args:
        entity_name: Name of the entity (e.g., 'imaging_file', 'subject')
        limit: Number of sample records to return
    """
    logger.info(f"Fetching sample records for {entity_name}")

    # First get the schema to know what fields are available
    async with client_context() as client:
        schema = await client.get_json(
            f"{config.schema_base_url}/{entity_name}", authenticated=False
        )

        if not schema or "properties" not in schema:
            return {"error": f"Could not get schema for {entity_name}"}

        # Get a reasonable subset of fields (avoid overwhelming response)
        properties = schema["properties"]

        # Prioritize commonly useful fields
        priority_fields = [
            "id",
            "submitter_id",
            "type",
            "file_name",
            "data_type",
            "data_format",
            "imaging_type",
            "sex",
            "race",
            "age_at_enrollment",
        ]

        # Include priority fields that exist, then add others up to a reasonable limit
        fields_to_query = []
        for field in priority_fields:
            if field in properties:
                fields_to_query.append(field)

        # Add other fields up to 15 total to keep response manageable
        for field in properties:
            if field not in fields_to_query and len(fields_to_query) < 15:
                fields_to_query.append(field)

        # Build GraphQL query
        fields_str = "\n            ".join(fields_to_query)
        query = f"""
        {{
            {entity_name}(first: {limit}) {{
                {fields_str}
            }}
        }}
        """

        result = await client.post_json(config.graphql_url, json={"query": query})

        if not result or "data" not in result:
            return {"error": f"Failed to fetch sample records for {entity_name}"}

        entity_data = result["data"].get(entity_name, [])

        return {
            "entity": entity_name,
            "total_records_returned": len(entity_data),
            "fields_queried": fields_to_query,
            "sample_records": entity_data,
            "query_used": query.strip(),
        }


@mcp.tool()
async def explore_entity_data(entity_name: str) -> dict[str, Any]:
    """
    Get comprehensive overview of an entity including schema, sample records, and common field values.

    Args:
        entity_name: Name of the entity (e.g., 'imaging_file', 'subject')
    """
    logger.info(f"Exploring entity data for {entity_name}")

    async with client_context() as client:
        # Get schema
        schema = await client.get_json(
            f"{config.schema_base_url}/{entity_name}", authenticated=False
        )

        if not schema:
            return {"error": f"Could not get schema for {entity_name}"}

        # Get sample records
        sample_query = f"""
        {{
            {entity_name}(first: 3) {{
                id
                submitter_id
                type
            }}
        }}
        """

        sample_result = await client.post_json(
            config.graphql_url, json={"query": sample_query}
        )

        # Analyze schema for enum fields and important fields
        properties = schema.get("properties", {})
        enum_fields = []
        important_fields = []

        for field_name, field_def in properties.items():
            if isinstance(field_def, dict):
                if "enum" in field_def:
                    enum_fields.append(
                        {"field": field_name, "enum_values": field_def["enum"]}
                    )

                # Mark fields that are likely important for filtering
                if any(
                    keyword in field_name.lower()
                    for keyword in [
                        "type",
                        "format",
                        "category",
                        "sex",
                        "race",
                        "status",
                    ]
                ):
                    important_fields.append(field_name)

        result = {
            "entity": entity_name,
            "schema_info": {
                "title": schema.get("title", ""),
                "description": schema.get("description", ""),
                "category": schema.get("category", ""),
                "total_properties": len(properties),
                "required_fields": schema.get("required", []),
            },
            "enum_fields": enum_fields,
            "important_filtering_fields": important_fields,
            "sample_records": sample_result.get("data", {}).get(entity_name, [])
            if sample_result
            else [],
        }

        return result


# Schema Validation Tools
@mcp.tool()
async def validate_query_fields(query: str) -> dict[str, Any]:
    """
    Validate all fields in a GraphQL query against the Gen3 schema.
    
    This tool parses a GraphQL query and checks every field name against the actual
    Gen3 schema to prevent hallucinated field names. It provides detailed error
    messages and suggestions for invalid fields.
    
    Args:
        query: GraphQL query string to validate
        
    Returns:
        Validation results with errors, suggestions, and summary statistics
    """
    logger.info("Validating GraphQL query fields")
    
    async with client_context() as client:
        validator = Gen3SchemaValidator(client)
        return await validator.validate_query_fields(query)


@mcp.tool()
async def suggest_similar_fields(field_name: str, entity_name: str) -> dict[str, Any]:
    """
    Suggest similar field names when a field doesn't exist in an entity.
    
    When you try to use a field that doesn't exist, this tool finds similar
    field names using string similarity and pattern matching. It also suggests
    alternative entity names if the entity itself doesn't exist.
    
    Args:
        field_name: Invalid field name to find alternatives for
        entity_name: Entity name to search within
        
    Returns:
        List of similar field suggestions with similarity scores and field types
    """
    logger.info(f"Suggesting similar fields for {field_name} in {entity_name}")
    
    async with client_context() as client:
        validator = Gen3SchemaValidator(client)
        return await validator.suggest_similar_fields(field_name, entity_name)


@mcp.tool()
async def get_query_template(entity_name: str, include_relationships: bool = True) -> dict[str, Any]:
    """
    Generate a safe GraphQL query template using only validated fields.
    
    This tool creates a complete GraphQL query template with fields that are
    guaranteed to exist in the schema. It includes basic fields, important
    properties, and commented relationship examples.
    
    Args:
        entity_name: Entity to generate template for (e.g., 'subject', 'sample')
        include_relationships: Whether to include relationship field examples
        
    Returns:
        Complete query template with validated fields and usage notes
    """
    logger.info(f"Generating query template for {entity_name}")
    
    async with client_context() as client:
        validator = Gen3SchemaValidator(client)
        return await validator.get_query_template(entity_name, include_relationships)


# Cleanup function for proper shutdown
async def cleanup():
    """Cleanup resources on shutdown"""
    global _client_instance
    if _client_instance:
        await _client_instance.close()
        _client_instance = None


if __name__ == "__main__":
    import signal
    import sys

    def signal_handler(signum, frame):
        """Handle shutdown signals"""
        logger.info("Shutting down...")
        if _client_instance:
            asyncio.create_task(cleanup())
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info(f"Starting Gen3 MCP Server with endpoint: {config.base_url}")

    try:
        mcp.run(transport="stdio")
    finally:
        # Ensure cleanup on exit
        if _client_instance:
            asyncio.run(cleanup())
