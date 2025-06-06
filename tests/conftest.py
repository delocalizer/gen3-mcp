"""Pytest configuration and shared fixtures"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from gen3_mcp.config import Config
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


@pytest.fixture(scope="session")
def test_schema():
    """Test schema fixture"""
    return FULL_SCHEMA


@pytest.fixture(scope="session")
def reference_extract_json():
    """Reference extract JSON string fixture"""
    return REFERENCE_EXTRACT


def mock_get_json_side_effect(url, **kwargs):
    """Mock side effect that may return different responses based on URL"""
    if url.endswith("/_all"):
        # Full schema request
        return FULL_SCHEMA


@pytest.fixture
def mock_client():
    """Mock Gen3 client for testing"""
    from gen3_mcp.client import Gen3Client

    client = Mock(spec=Gen3Client)
    # Create a default config for the client
    client.config = Config(
        base_url="https://test.gen3.io",
        credentials_file="/tmp/test_creds.json",
        log_level="DEBUG",
    )

    # Configure mock to return different responses based on URL
    client.get_json = AsyncMock(side_effect=mock_get_json_side_effect)

    # Mock GraphQL responses with realistic data
    client.post_json = AsyncMock(
        return_value={
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
    )

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
