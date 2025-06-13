"""Pytest configuration and shared fixtures"""

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from gen3_mcp.config import Config
from gen3_mcp.consts import SCHEMA_URL_PATH
from gen3_mcp.schema import SchemaManager

# Configure pytest-asyncio
pytest_plugins = ("pytest_asyncio",)


def load_test_schema():
    """Load the test schema from ex_schema.json"""
    schema_path = Path(__file__).parent / "ex_schema.json"
    with open(schema_path) as f:
        return json.load(f)


def load_reference_extract():
    """Load the reference schema extract from ex_schema_extract.json"""
    extract_path = Path(__file__).parent / "ex_schema_extract.json"
    with open(extract_path) as f:
        return f.read()


# Load the schema and reference data
FULL_SCHEMA = load_test_schema()
REFERENCE_EXTRACT = load_reference_extract()


@pytest.fixture
def mock_graphql_schema(schema_extract):
    """Create GraphQL schema dynamically from our test entity schema extract"""
    from graphql import build_schema

    # Build schema definition from schema_extract
    schema_parts = ["type Query {"]

    # Add query fields for each entity
    for entity_name in schema_extract.keys():
        type_name = _capitalize(entity_name)
        schema_parts.append(f"    {entity_name}(first: Int): [{type_name}]")

    schema_parts.append("}")

    # Add type definitions for each entity
    for entity_name, entity in schema_extract.items():
        type_name = _capitalize(entity_name)
        schema_parts.append(f"type {type_name} {{")

        # Add all scalar fields
        for field_name, field in entity.fields.items():
            graphql_type = _convert_field_type_to_graphql(field.type_)
            schema_parts.append(f"    {field_name}: {graphql_type}")

        # Add relationship fields
        for rel_name, rel in entity.relationships.items():
            target_type = _capitalize(rel.target_type)
            schema_parts.append(f"    {rel_name}: [{target_type}]")

        schema_parts.append("}")

    schema_def = "\n".join(schema_parts)
    return build_schema(schema_def)


def _capitalize(name):
    """Convert snake_case to PascalCase"""
    return "".join(word.capitalize() for word in name.split("_"))


def _convert_field_type_to_graphql(field_type):
    """Convert Gen3 field type to GraphQL type"""
    mapping = {
        "string": "String",
        "integer": "Int",
        "number": "Float",
        "boolean": "Boolean",
        "enum": "String",  # Simplified - could create actual enums
        "array": "[String]",
        "object": "String",  # JSON as string
        "anyOf": "String",
        "oneOf": "String",
    }
    return mapping.get(field_type.value, "String")


@pytest.fixture(scope="session")
def test_schema():
    """Test schema fixture"""
    return FULL_SCHEMA


@pytest.fixture(scope="session")
def reference_extract_json():
    """Reference extract JSON string fixture"""
    return REFERENCE_EXTRACT


def mock_get_json_side_effect(url, **kwargs):
    """Mock side effect that returns raw data based on URL"""
    if url.endswith(SCHEMA_URL_PATH):

        return FULL_SCHEMA
    # For any other URL, raise appropriate exception
    import httpx

    mock_response = Mock()
    mock_response.status_code = 404
    mock_response.url = url
    raise httpx.HTTPStatusError("Not found", request=Mock(), response=mock_response)


@pytest.fixture
def mock_client():
    """Mock Gen3 client for testing"""
    from gen3_mcp.client import Gen3Client

    # Create a mock token provider
    mock_token_provider = Mock()
    mock_token_provider.get_valid_token = AsyncMock(return_value="mock_token")

    # Create a mock HTTP client
    mock_http_client = Mock()

    # Create client with mocked dependencies
    client = Gen3Client(
        config=Config(
            base_url="https://test.gen3.io",
            credentials_file="/tmp/test_creds.json",
            log_level="DEBUG",
        ),
        token_provider=mock_token_provider,
        http_client=mock_http_client,
    )

    # Override methods with AsyncMocks for easier testing
    client.get_json = AsyncMock(side_effect=mock_get_json_side_effect)

    # Mock GraphQL responses with realistic data
    def mock_post_json_side_effect(url, **kwargs):
        # Return raw data
        return {
            "data": {
                "subject": [
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "submitter_id": "test_subject_001",
                        "type": "subject",
                        "gender": "Female",
                        "age_at_enrollment": 45,
                        "race": "White",
                        "ethnicity": "Not Hispanic or Latino",
                    }
                ]
            }
        }

    client.post_json = AsyncMock(side_effect=mock_post_json_side_effect)

    return client


@pytest.fixture
async def schema_manager(mock_client):
    """SchemaManager fixture with mock client"""
    manager = SchemaManager(mock_client)
    manager.clear_cache()  # Ensure clean state
    return manager


@pytest.fixture
async def schema_extract(schema_manager):
    """Schema extract fixture using SchemaManager"""
    return await schema_manager.get_schema_extract()


@pytest.fixture
def clean_env():
    """Fixture that temporarily clears GEN3MCP_* environment variables.

    This ensures Config tests see the true defaults without interference
    from environment variables that might be set in the user's shell.
    """
    # Find all GEN3MCP_* environment variables
    gen3mcp_vars = {
        key: value for key, value in os.environ.items() if key.startswith("GEN3MCP_")
    }

    # Temporarily remove them
    for key in gen3mcp_vars:
        os.environ.pop(key, None)

    try:
        yield
    finally:
        # Restore original environment variables
        for key, value in gen3mcp_vars.items():
            os.environ[key] = value


@pytest.fixture
def clean_config(clean_env):
    """Fixture that provides a Config instance with clean environment.

    This ensures tests can verify default values without environment
    variable interference.
    """
    return Config()
