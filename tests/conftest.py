"""Pytest configuration and shared fixtures"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from gen3_mcp.config import Config

# Configure pytest-asyncio
pytest_plugins = ("pytest_asyncio",)


def load_test_schema():
    """Load the test schema from ex_schema.json"""
    schema_path = Path(__file__).parent / "ex_schema.json"
    with open(schema_path) as f:
        return json.load(f)


@pytest.fixture(autouse=True)
def reset_global_state():
    """Reset global state before each test"""
    from gen3_mcp import main

    # Reset global state
    main._config = None
    main._client = None

    yield

    # Clean up after test
    main._config = None
    main._client = None


@pytest.fixture
def config():
    """Test configuration"""
    return Config(
        base_url="https://test.gen3.io",
        credentials_file="/tmp/test_creds.json",
        log_level="DEBUG",
        schema_cache_ttl=60,  # Shorter TTL for testing
    )


# Load the schema from ex_schema.json
FULL_SCHEMA = load_test_schema()


def mock_get_json_side_effect(url, **kwargs):
    """Mock side effect that may return different responses based on URL"""
    if url.endswith("/_all"):
        # Full schema request
        return FULL_SCHEMA


@pytest.fixture
def mock_client():
    """Mock Gen3 client for testing"""
    from gen3_mcp.client import Gen3Client

    client = AsyncMock(spec=Gen3Client)

    # Configure mock to return different responses based on URL
    client.get_json.side_effect = mock_get_json_side_effect

    # Mock GraphQL responses with realistic data
    client.post_json.return_value = {
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

    return client


def create_test_services():
    """Helper to create mock services for testing"""
    mock_gen3_service = AsyncMock()
    mock_query_service = AsyncMock()

    # Load schema to get realistic data
    schema = load_test_schema()

    mock_gen3_service.get_schema_full.return_value = schema

    # QueryService has 3 methods: generate_query_template, validate_query, execute_graphql
    mock_query_service.generate_query_template.return_value = {
        "entity_name": "subject",
        "exists": True,
        "template": "{ subject { id submitter_id } }",
        "basic_fields": ["id", "submitter_id", "type"],
        "entity_fields": ["gender", "age_at_enrollment"],
        "relationship_fields": [],
        "total_fields": 5,
    }

    mock_query_service.validate_query.return_value = {
        "valid": True,
        "errors": [],
        "next_steps": {
            "ready_to_execute": True,
            "suggestion": "Query is valid! Use execute_graphql() to run it.",
        },
    }

    mock_query_service.execute_graphql.return_value = {
        "data": {
            "subject": [
                {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "submitter_id": "subject_001",
                    "gender": "Female",
                    "age_at_enrollment": 45,
                }
            ]
        }
    }

    return mock_gen3_service, mock_query_service


@pytest.fixture
async def mcp_test_setup():
    """Fixture that handles MCP test setup and teardown"""
    from gen3_mcp import main
    from gen3_mcp.main import create_mcp_server

    # Store original state
    original_config = main._config
    original_client = main._client
    original_gen3_service = main._gen3_service
    original_query_service = main._query_service

    # Reset state (this is already done by reset_global_state, but being explicit)
    main._config = None
    main._client = None
    main._gen3_service = None
    main._query_service = None

    # Create test services
    mock_gen3_service, mock_query_service = create_test_services()

    try:
        with (
            patch("gen3_mcp.main.get_gen3_service", return_value=mock_gen3_service),
            patch("gen3_mcp.main.get_query_service", return_value=mock_query_service),
        ):

            mcp_server = create_mcp_server()

            yield {
                "mcp_server": mcp_server,
                "mock_gen3_service": mock_gen3_service,
                "mock_query_service": mock_query_service,
            }
    finally:
        # Restore original state
        main._config = original_config
        main._client = original_client
        main._gen3_service = original_gen3_service
        main._query_service = original_query_service
