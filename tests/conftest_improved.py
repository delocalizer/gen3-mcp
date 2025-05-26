"""Pytest configuration and shared fixtures with improved schema loading"""

import json
import pytest
from pathlib import Path
from typing import Dict, Any
from unittest.mock import AsyncMock, patch

from gen3_mcp.config import Gen3Config

# Configure pytest-asyncio
pytest_plugins = ("pytest_asyncio",)

# ============================================================================
# OPTION 1: Simple global variable approach
# ============================================================================

def load_test_schema() -> Dict[str, Any]:
    """Load the test schema from ex_schema.json"""
    schema_path = Path(__file__).parent / "ex_schema.json"
    with open(schema_path, 'r') as f:
        return json.load(f)

# Load once at module level
TEST_SCHEMA = load_test_schema()

# ============================================================================
# OPTION 2: Lazy loading with caching
# ============================================================================

_schema_cache = None

def get_test_schema() -> Dict[str, Any]:
    """Get test schema with lazy loading and caching"""
    global _schema_cache
    if _schema_cache is None:
        schema_path = Path(__file__).parent / "ex_schema.json"
        with open(schema_path, 'r') as f:
            _schema_cache = json.load(f)
    return _schema_cache

# ============================================================================
# OPTION 3: Class-based resource manager (most robust)
# ============================================================================

class TestSchemaManager:
    """Manages test schema resources with proper lifecycle"""
    
    def __init__(self):
        self._schema = None
        self._schema_path = Path(__file__).parent / "ex_schema.json"
    
    @property
    def schema(self) -> Dict[str, Any]:
        """Get the full schema"""
        if self._schema is None:
            self._load_schema()
        return self._schema
    
    def _load_schema(self) -> None:
        """Load schema from file"""
        with open(self._schema_path, 'r') as f:
            self._schema = json.load(f)
    
    def get_entity_schema(self, entity_name: str) -> Dict[str, Any]:
        """Get schema for a specific entity"""
        return self.schema.get(entity_name, {})
    
    def get_entity_properties(self, entity_name: str) -> Dict[str, Any]:
        """Get properties for a specific entity"""
        return self.get_entity_schema(entity_name).get("properties", {})
    
    def get_entity_links(self, entity_name: str) -> list:
        """Get links for a specific entity"""
        return self.get_entity_schema(entity_name).get("links", [])
    
    def get_available_entities(self) -> list:
        """Get list of available entity names"""
        return list(self.schema.keys())
    
    def reload(self) -> None:
        """Force reload schema from file"""
        self._schema = None

# Global instance
schema_manager = TestSchemaManager()

# ============================================================================
# OPTION 4: Pytest fixture-based approach
# ============================================================================

@pytest.fixture(scope="session")
def test_schema_fixture() -> Dict[str, Any]:
    """Session-scoped fixture for test schema"""
    schema_path = Path(__file__).parent / "ex_schema.json"
    with open(schema_path, 'r') as f:
        return json.load(f)

@pytest.fixture(scope="session")
def schema_manager_fixture() -> TestSchemaManager:
    """Session-scoped fixture for schema manager"""
    return TestSchemaManager()

# ============================================================================
# Individual entity fixtures (convenient for specific tests)
# ============================================================================

@pytest.fixture
def subject_schema(test_schema_fixture):
    """Fixture for subject entity schema"""
    return test_schema_fixture["subject"]

@pytest.fixture  
def sample_schema(test_schema_fixture):
    """Fixture for sample entity schema"""
    return test_schema_fixture["sample"]

@pytest.fixture
def study_schema(test_schema_fixture):
    """Fixture for study entity schema"""
    return test_schema_fixture["study"]

# ============================================================================
# Enhanced mock fixtures using the real schema
# ============================================================================

def mock_get_json_side_effect_realistic(url, **kwargs):
    """Enhanced mock side effect using real schema structure"""
    schema = get_test_schema()
    
    if url.endswith("/_all"):
        # Full schema request
        return schema
    elif url.endswith("/subject"):
        return schema.get("subject", {})
    elif url.endswith("/sample"):
        return schema.get("sample", {})
    elif url.endswith("/study"):
        return schema.get("study", {})
    else:
        # Extract entity name from URL and try to find it
        entity_name = url.split("/")[-1]
        return schema.get(entity_name, None)

@pytest.fixture
def mock_client_realistic():
    """Mock Gen3 client using realistic schema"""
    from gen3_mcp.client import Gen3Client

    client = AsyncMock(spec=Gen3Client)
    client.get_json.side_effect = mock_get_json_side_effect_realistic

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
                    "ethnicity": "Not Hispanic or Latino"
                }
            ]
        }
    }
    return client

def create_realistic_test_services():
    """Create mock services using realistic schema"""
    mock_gen3_service = AsyncMock()
    mock_query_service = AsyncMock()
    
    schema = get_test_schema()
    entity_names = list(schema.keys())
    
    # Set up mock returns based on real schema
    mock_gen3_service.get_schema_summary.return_value = {
        "total_entities": len(entity_names),
        "entity_names": entity_names,
        "entities_by_category": {
            "administrative": ["subject", "study"],
            "biospecimen": ["sample"],
        },
    }

    mock_gen3_service.get_schema_full.return_value = schema
    mock_gen3_service.get_entity_names.return_value = entity_names

    # Set up realistic entity schema responses
    def get_entity_schema_side_effect(entity_name):
        return schema.get(entity_name, {})
    
    mock_gen3_service.get_entity_schema.side_effect = get_entity_schema_side_effect

    mock_gen3_service.get_detailed_entities.return_value = {
        "total_entities": len(entity_names),
        "entities": {name: {"title": schema[name].get("title", name.title())} 
                    for name in entity_names},
    }

    # Sample realistic data
    mock_gen3_service.get_sample_records.return_value = {
        "entity": "subject",
        "sample_records": [
            {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "submitter_id": "subject_001", 
                "gender": "Female",
                "age_at_enrollment": 45
            }
        ],
    }

    # Use realistic enum values from schema
    subject_gender_enum = schema["subject"]["properties"]["gender"]["enum"]
    mock_gen3_service.explore_entity_data.return_value = {
        "entity": "subject",
        "schema_info": {"title": "Subject"},
        "enum_fields": [
            {"field": "gender", "enum_values": subject_gender_enum}
        ],
    }

    # Rest of the mock setup...
    mock_query_service.field_sample.return_value = {
        "entity": "subject",
        "field": "gender",
        "values": {"Female": 5, "Male": 3, "Not Reported": 1},
    }

    mock_query_service.validate_query_fields.return_value = {
        "valid": True,
        "extracted_fields": {"subject": ["id", "submitter_id", "gender"]},
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
        "template": "{ subject { id submitter_id gender } }",
    }

    mock_query_service.execute_graphql.return_value = {
        "data": {"subject": [{"id": "123e4567-e89b-12d3-a456-426614174000"}]}
    }

    return mock_gen3_service, mock_query_service

@pytest.fixture
async def mcp_test_setup_realistic():
    """Enhanced MCP test setup using realistic schema"""
    from gen3_mcp import main
    from gen3_mcp.main import create_mcp_server

    # Store original state
    original_config = main._config
    original_client = main._client
    original_gen3_service = main._gen3_service
    original_query_service = main._query_service

    # Reset state
    main._config = None
    main._client = None
    main._gen3_service = None
    main._query_service = None

    # Create realistic test services
    mock_gen3_service, mock_query_service = create_realistic_test_services()

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
                "schema": get_test_schema(),
                "schema_manager": schema_manager,
            }
    finally:
        # Restore original state
        main._config = original_config
        main._client = original_client
        main._gen3_service = original_gen3_service
        main._query_service = original_query_service

# ============================================================================
# Legacy compatibility
# ============================================================================

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

# Backward compatibility - provide the old fixture name mapping to new realistic schema
@pytest.fixture
def mock_client():
    """Legacy mock client - now points to realistic version"""
    return mock_client_realistic()
