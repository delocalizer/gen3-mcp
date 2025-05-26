"""Pytest configuration and shared fixtures"""

from unittest.mock import AsyncMock, patch

import pytest

from gen3_mcp.config import Gen3Config

# Configure pytest-asyncio
pytest_plugins = ("pytest_asyncio",)


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


# Define the test schema data
FULL_SCHEMA = {
    "subject": {
        "properties": {
            "id": {"type": "string"},
            "submitter_id": {"type": "string"},
            "type": {"type": "string"},
            "gender": {"type": "string", "enum": ["Male", "Female", "Unknown"]},
            "age_at_enrollment": {"type": "integer"},
            "race": {"type": "string"},
            "ethnicity": {"type": "string"},
        },
        "links": [
            {
                "subgroup": [
                    {
                        "name": "studies",
                        "target_type": "study",
                        "multiplicity": "many_to_many",
                        "backref": "subjects",
                        "required": True,
                    },
                    {
                        "name": "samples",
                        "target_type": "sample",
                        "multiplicity": "one_to_many",
                        "backref": "subjects",
                        "required": False,
                    },
                ]
            }
        ],
        "required": ["submitter_id", "type"],
        "description": "The collection of all data related to a specific subject",
        "category": "administrative",
    },
    "sample": {
        "properties": {
            "id": {"type": "string"},
            "submitter_id": {"type": "string"},
            "type": {"type": "string"},
            "sample_type": {"type": "string"},
            "anatomic_site": {"type": "string"},
        },
        "links": [
            {
                "subgroup": [
                    {
                        "name": "subjects",
                        "target_type": "subject",
                        "multiplicity": "many_to_one",
                        "backref": "samples",
                        "required": True,
                    }
                ]
            }
        ],
        "required": ["submitter_id", "type"],
        "category": "biospecimen",
    },
    "study": {
        "properties": {
            "id": {"type": "string"},
            "submitter_id": {"type": "string"},
            "type": {"type": "string"},
            "description": {"type": "string"},
            "study_design": {"type": "string"},
        },
        "links": [
            {
                "subgroup": [
                    {
                        "name": "subjects",
                        "target_type": "subject",
                        "multiplicity": "many_to_many",
                        "backref": "studies",
                        "required": True,
                    }
                ]
            }
        ],
        "required": ["submitter_id", "type"],
        "category": "administrative",
    },
}

SUBJECT_SCHEMA = FULL_SCHEMA["subject"]
SAMPLE_SCHEMA = FULL_SCHEMA["sample"]
STUDY_SCHEMA = FULL_SCHEMA["study"]


def mock_get_json_side_effect(url, **kwargs):
    """Mock side effect that returns different responses based on URL"""
    if url.endswith("/_all"):
        # Full schema request
        return FULL_SCHEMA
    elif url.endswith("/subject"):
        # Single entity schema request
        return SUBJECT_SCHEMA
    elif url.endswith("/sample"):
        # Single entity schema request
        return SAMPLE_SCHEMA
    elif url.endswith("/study"):
        # Single entity schema request
        return STUDY_SCHEMA
    else:
        # Unknown entity
        return None


@pytest.fixture
def mock_client():
    """Mock Gen3 client for testing"""
    from gen3_mcp.client import Gen3Client

    client = AsyncMock(spec=Gen3Client)

    # Configure mock to return different responses based on URL
    client.get_json.side_effect = mock_get_json_side_effect

    # Mock GraphQL responses
    client.post_json.return_value = {
        "data": {
            "subject": [
                {
                    "id": "123",
                    "submitter_id": "test_subject",
                    "type": "subject",
                    "gender": "Female",
                }
            ]
        }
    }

    return client


def create_test_services():
    """Helper to create mock services for testing"""
    mock_gen3_service = AsyncMock()
    mock_query_service = AsyncMock()

    # Set up mock returns for common service calls
    mock_gen3_service.get_schema_summary.return_value = {
        "total_entities": 3,
        "entity_names": ["subject", "sample", "study"],
        "entities_by_category": {
            "clinical": ["subject"],
            "biospecimen": ["sample"],
            "administrative": ["study"],
        },
    }

    mock_gen3_service.get_full_schema.return_value = {
        "subject": {"properties": {"id": {"type": "string"}}},
        "sample": {"properties": {"id": {"type": "string"}}},
        "study": {"properties": {"id": {"type": "string"}}},
    }

    mock_gen3_service.get_entity_schema.return_value = {
        "properties": {"id": {"type": "string"}, "gender": {"enum": ["Male", "Female"]}}
    }

    mock_gen3_service.get_entity_names.return_value = ["subject", "sample", "study"]

    mock_gen3_service.get_detailed_entities.return_value = {
        "total_entities": 3,
        "entities": {
            "subject": {"title": "Subject"},
            "sample": {"title": "Sample"},
            "study": {"title": "Study"},
        },
    }

    mock_gen3_service.get_sample_records.return_value = {
        "entity": "subject",
        "sample_records": [{"id": "1", "gender": "Male"}],
    }

    mock_gen3_service.explore_entity_data.return_value = {
        "entity": "subject",
        "schema_info": {"title": "Subject"},
        "enum_fields": [{"field": "gender", "enum_values": ["Male", "Female"]}],
    }

    mock_query_service.field_sample.return_value = {
        "entity": "subject",
        "field": "gender",
        "values": {"Male": 5, "Female": 3},
    }

    mock_query_service.validate_query_fields.return_value = {
        "valid": True,
        "extracted_fields": {"subject": ["id"]},
        "validation_results": {},
    }

    mock_query_service.suggest_similar_fields.return_value = {
        "field_name": "gander",
        "entity_name": "subject",
        "suggestions": [{"name": "gender", "similarity": 0.8}],
    }

    mock_query_service.generate_query_template.return_value = {
        "entity_name": "subject",
        "exists": True,
        "template": "{ subject { id submitter_id } }",
    }

    mock_query_service.execute_graphql.return_value = {
        "data": {"subject": [{"id": "1"}]}
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
