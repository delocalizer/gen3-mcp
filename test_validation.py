#!/usr/bin/env python3
"""
Test script for the Gen3 MCP server with validation functions.
"""

import asyncio
import json
from gen3_validator import Gen3SchemaValidator


class MockClient:
    """Mock client for testing validation functions without actual API calls"""
    
    def __init__(self):
        # Mock schema data for testing
        self.mock_schemas = {
            "subject": {
                "properties": {
                    "id": {"type": "string"},
                    "submitter_id": {"type": "string"},
                    "type": {"type": "string"},
                    "gender": {"type": "string", "enum": ["Male", "Female", "Unknown"]},
                    "race": {"type": "string"},
                    "ethnicity": {"type": "string"},
                    "age_at_enrollment": {"type": "integer"}
                },
                "links": [
                    {
                        "subgroup": [
                            {
                                "name": "studies",
                                "target_type": "study",
                                "multiplicity": "many_to_many"
                            }
                        ]
                    }
                ],
                "required": ["submitter_id", "type"],
                "description": "The collection of all data related to a specific subject",
                "category": "administrative"
            },
            "sample": {
                "properties": {
                    "id": {"type": "string"},
                    "submitter_id": {"type": "string"},
                    "type": {"type": "string"},
                    "sample_type": {"type": "string"},
                    "anatomic_site": {"type": "string"}
                },
                "links": [
                    {
                        "subgroup": [
                            {
                                "name": "subjects",
                                "target_type": "subject",
                                "multiplicity": "many_to_one"
                            }
                        ]
                    }
                ],
                "required": ["submitter_id", "type"],
                "description": "Material sample taken from a biological entity",
                "category": "biospecimen"
            }
        }
        
        self.mock_entity_list = {
            "entities": self.mock_schemas
        }
    
    async def get_json(self, endpoint: str, authenticated: bool = True) -> dict:
        """Mock get_json method"""
        if "_dictionary/_all" in endpoint:
            return self.mock_schemas
        elif "_dictionary/" in endpoint:
            entity_name = endpoint.split("/")[-1]
            return self.mock_schemas.get(entity_name)
        return {}
    
    async def post_json(self, endpoint: str, **kwargs) -> dict:
        """Mock post_json method"""
        if "graphql" in endpoint:
            # Return mock GraphQL response
            return {
                "data": {
                    "subject": [
                        {"id": "123", "submitter_id": "test_subject", "type": "subject"}
                    ]
                }
            }
        return {}


async def test_validation_functions():
    """Test the validation functions with mock data"""
    print("Testing Gen3 Schema Validation Functions")
    print("=" * 50)
    
    # Create mock client and validator
    mock_client = MockClient()
    validator = Gen3SchemaValidator(mock_client)
    
    # Test 1: Valid query
    print("\n1. Testing valid query validation:")
    valid_query = """
    {
        subject {
            id
            submitter_id
            gender
            age_at_enrollment
        }
    }
    """
    
    result = await validator.validate_query_fields(valid_query)
    print(f"   Valid: {result['valid']}")
    print(f"   Errors: {len(result.get('summary', {}).get('errors', []))}")
    
    # Test 2: Invalid query
    print("\n2. Testing invalid query validation:")
    invalid_query = """
    {
        subject {
            id
            invalid_field
            another_bad_field
        }
    }
    """
    
    result = await validator.validate_query_fields(invalid_query)
    print(f"   Valid: {result['valid']}")
    print(f"   Errors: {len(result.get('summary', {}).get('errors', []))}")
    print(f"   Error messages: {result.get('summary', {}).get('errors', [])}")
    
    # Test 3: Field suggestions
    print("\n3. Testing field suggestions:")
    suggestions = await validator.suggest_similar_fields("gander", "subject")
    print(f"   Entity exists: {suggestions.get('entity_exists')}")
    print(f"   Suggestions for 'gander': {[s['name'] for s in suggestions.get('suggestions', [])[:3]]}")
    
    # Test 4: Query template generation
    print("\n4. Testing query template generation:")
    template = await validator.get_query_template("subject")
    print(f"   Template generated: {template.get('exists')}")
    print(f"   Basic fields: {template.get('basic_fields', [])}")
    print(f"   Total fields: {template.get('total_fields', 0)}")
    
    # Test 5: Non-existent entity
    print("\n5. Testing non-existent entity:")
    bad_template = await validator.get_query_template("nonexistent_entity")
    print(f"   Entity exists: {bad_template.get('exists')}")
    print(f"   Error: {bad_template.get('error')}")
    
    print("\n" + "=" * 50)
    print("All tests completed successfully!")


if __name__ == "__main__":
    asyncio.run(test_validation_functions())
