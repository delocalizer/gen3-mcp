"""Pytest configuration and shared fixtures"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from gen3_mcp.config import Gen3Config

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
    return Gen3Config(
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
    entity_names = list(schema.keys())

    # Categorize entities based on their actual category property
    entities_by_category = {}
    for entity_name, entity_schema in schema.items():
        category = entity_schema.get("category", "unknown")
        if category not in entities_by_category:
            entities_by_category[category] = []
        entities_by_category[category].append(entity_name)

    # Set up mock returns for common service calls
    mock_gen3_service.get_schema_summary.return_value = {
        "total_entities": len(entity_names),
        "entity_names": entity_names,
        "entities_by_category": entities_by_category,
    }

    mock_gen3_service.get_schema_full.return_value = schema

    # Use realistic entity schema based on the actual schema
    def get_entity_schema_side_effect(entity_name):
        return schema.get(entity_name, {})

    mock_gen3_service.get_entity_schema.side_effect = get_entity_schema_side_effect

    mock_gen3_service.get_entity_names.return_value = entity_names

    mock_gen3_service.get_detailed_entities.return_value = {
        "total_entities": len(entity_names),
        "entities": {
            name: {"title": schema[name].get("title", name.replace("_", " ").title())}
            for name in entity_names
        },
    }

    mock_gen3_service.get_sample_records.return_value = {
        "entity": "subject",
        "sample_records": [
            {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "submitter_id": "subject_001",
                "gender": "Female",
                "age_at_enrollment": 45,
                "race": "White",
                "ethnicity": "Not Hispanic or Latino",
            }
        ],
    }

    # Use realistic enum values from the actual schema
    subject_gender_enum = schema["subject"]["properties"]["gender"]["enum"]
    mock_gen3_service.explore_entity_data.return_value = {
        "entity": "subject",
        "schema_info": {"title": "Subject"},
        "enum_fields": [{"field": "gender", "enum_values": subject_gender_enum}],
    }

    mock_gen3_service.get_entity_context.return_value = {
        "entity_name": "subject",
        "exists": True,
        "schema_summary": {
            "title": "Subject",
            "description": "The collection of all data related to a specific subject",
            "category": "administrative",
            "total_properties": 7,
            "required_fields": ["submitter_id", "type"],
        },
        "relationships": {
            "parents": [],
            "children": [{"entity": "sample", "backref_field": "samples"}],
            "parent_count": 0,
            "child_count": 1,
        },
        "graphql_fields": {
            "backref_fields": ["samples"],
            "available_as_backref": ["subjects"],
            "direct_fields": ["id", "submitter_id", "gender"],
            "system_fields": ["id", "submitter_id", "type"],
        },
        "query_patterns": {
            "basic_query": "{ subject(first: 10) { id submitter_id type } }",
            "with_relationships": [],
            "usage_examples": ["Use subject as starting point"],
        },
        "position_type": {"position": "root", "description": "Top-level entity"},
    }

    mock_query_service.field_sample.return_value = {
        "entity": "subject",
        "field": "gender",
        "values": {"Female": 5, "Male": 3, "Not Reported": 1, "Unknown": 1},
    }

    mock_query_service.validate_query_fields.return_value = {
        "valid": True,
        "extracted_fields": {"subject": ["id"]},
        "validation_results": {},
    }

    mock_query_service.generate_query_template.return_value = {
        "entity_name": "subject",
        "exists": True,
        "template": "{ subject { id submitter_id } }",
    }

    mock_query_service.execute_graphql.return_value = {
        "data": {
            "subject": [
                {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "submitter_id": "subject_001",
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
