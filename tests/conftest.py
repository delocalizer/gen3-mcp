"""Pytest configuration and shared fixtures"""

from unittest.mock import AsyncMock

import pytest

from gen3_mcp.config import Gen3Config

# Configure pytest-asyncio
pytest_plugins = ("pytest_asyncio",)


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
                    }
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
        "required": ["submitter_id", "type"],
        "category": "biospecimen",
    },
}

SUBJECT_SCHEMA = FULL_SCHEMA["subject"]
SAMPLE_SCHEMA = FULL_SCHEMA["sample"]


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
