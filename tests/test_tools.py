"""Tests for MCP tools functionality"""

import json
from pathlib import Path

import pytest

from gen3_mcp.schema_extract import SchemaExtract


@pytest.fixture(autouse=True)
def clear_schema_cache():
    """Clear SchemaExtract cache before each test to prevent interference"""
    SchemaExtract.clear_cache()
    yield
    SchemaExtract.clear_cache()


class TestSchemaTools:
    """Test schema-related MCP tools"""

    @pytest.mark.asyncio
    async def test_schema_summary_tool(self, mcp_test_setup):
        """Test schema_summary tool returns complete SchemaExtract format"""
        mock_gen3_service = mcp_test_setup["mock_gen3_service"]

        # Load test schema for the mock
        test_schema_path = Path(__file__).parent / "ex_schema.json"
        with open(test_schema_path) as f:
            test_schema = json.load(f)

        mock_gen3_service.get_schema_full.return_value = test_schema

        # Test the schema_summary tool logic
        full_schema = await mock_gen3_service.get_schema_full()
        schema_extract = SchemaExtract.from_full_schema(full_schema)
        result = json.loads(repr(schema_extract))

        # Verify complete schema extract format
        assert isinstance(result, dict)
        assert len(result) > 0

        # Check that expected entities exist
        expected_entities = {
            "subject",
            "sample",
            "study",
            "aliquot",
            "aligned_reads_file",
        }
        actual_entities = set(result.keys())
        assert expected_entities.issubset(actual_entities)

        # Check that each entity has the complete structure
        for entity_name, entity_data in result.items():
            # Each entity should have all the comprehensive sections
            expected_sections = [
                "fields",
                "relationships",
                "schema_summary",
                "query_patterns",
            ]
            for section in expected_sections:
                assert section in entity_data, f"Entity {entity_name} missing {section}"

            # Check schema_summary structure
            schema_summary = entity_data["schema_summary"]
            expected_summary_fields = [
                "title",
                "description",
                "category",
                "required_fields",
                "field_count",
                "parent_count",
                "child_count",
                "position_description",
            ]
            for field in expected_summary_fields:
                assert (
                    field in schema_summary
                ), f"Entity {entity_name} schema_summary missing {field}"

            # Check position_description
            position_desc = schema_summary["position_description"]
            assert "position" in position_desc
            assert "description" in position_desc
            assert position_desc["position"] in ["root", "leaf", "intermediate"]

            # Check query_patterns structure
            query_patterns = entity_data["query_patterns"]
            expected_pattern_fields = [
                "basic_query",
                "with_relationships",
            ]
            for field in expected_pattern_fields:
                assert (
                    field in query_patterns
                ), f"Entity {entity_name} query_patterns missing {field}"

            # Check that basic query contains the entity name
            basic_query = query_patterns["basic_query"]
            assert (
                entity_name in basic_query
            ), f"Basic query for {entity_name} should contain entity name"

            # Check that relationship queries exist for entities with relationships
            if entity_data["relationships"]:
                assert (
                    len(query_patterns["with_relationships"]) > 0
                ), f"Entity {entity_name} has relationships but no relationship queries"

        # Verify that the service method was called
        mock_gen3_service.get_schema_full.assert_called_once()


class TestQueryTools:
    """Test query-related MCP tools"""

    @pytest.mark.asyncio
    async def test_query_template_tool(self, mcp_test_setup):
        """Test query_template tool"""
        mock_query_service = mcp_test_setup["mock_query_service"]

        # Test the tool call
        result = await mock_query_service.generate_query_template("subject", True, 20)

        # Check the expected structure
        assert result["entity_name"] == "subject"
        assert result["exists"] is True
        assert "template" in result
        assert "basic_fields" in result
        assert "entity_fields" in result

        # Verify service method was called with correct parameters
        mock_query_service.generate_query_template.assert_called_once_with(
            "subject", True, 20
        )

    @pytest.mark.asyncio
    async def test_validate_query_tool(self, mcp_test_setup):
        """Test validate_query tool"""
        mock_query_service = mcp_test_setup["mock_query_service"]

        query = "{ subject { id submitter_id } }"
        result = await mock_query_service.validate_query(query)

        # Check validation result structure
        assert "valid" in result
        assert "errors" in result
        assert result["valid"] is True
        assert isinstance(result["errors"], list)

        # Check workflow guidance
        assert "next_steps" in result

        mock_query_service.validate_query.assert_called_once_with(query)

    @pytest.mark.asyncio
    async def test_execute_graphql_tool(self, mcp_test_setup):
        """Test execute_graphql tool"""
        mock_query_service = mcp_test_setup["mock_query_service"]

        query = "{ subject { id submitter_id } }"
        result = await mock_query_service.execute_graphql(query)

        # Check execution result structure
        assert "data" in result
        assert "subject" in result["data"]
        assert isinstance(result["data"]["subject"], list)

        # Check that data has expected fields
        if result["data"]["subject"]:
            subject_record = result["data"]["subject"][0]
            assert "id" in subject_record
            assert "submitter_id" in subject_record

        mock_query_service.execute_graphql.assert_called_once_with(query)

    @pytest.mark.asyncio
    async def test_query_template_nonexistent_entity(self, mcp_test_setup):
        """Test query_template with nonexistent entity"""
        mock_query_service = mcp_test_setup["mock_query_service"]

        # Mock a failure case
        mock_query_service.generate_query_template.return_value = {
            "entity_name": "nonexistent",
            "exists": False,
            "template": None,
            "error": "Entity 'nonexistent' does not exist",
            "suggestions": ["subject", "sample", "study"],
        }

        result = await mock_query_service.generate_query_template(
            "nonexistent", True, 20
        )

        assert result["entity_name"] == "nonexistent"
        assert result["exists"] is False
        assert result["template"] is None
        assert "error" in result
        assert "suggestions" in result

        mock_query_service.generate_query_template.assert_called_once_with(
            "nonexistent", True, 20
        )

    @pytest.mark.asyncio
    async def test_validate_query_invalid(self, mcp_test_setup):
        """Test validate_query with invalid query"""
        mock_query_service = mcp_test_setup["mock_query_service"]

        # Mock validation failure
        mock_query_service.validate_query.return_value = {
            "valid": False,
            "errors": [
                {
                    "entity": "subject",
                    "field": "invalid_field",
                    "message": "Field 'invalid_field' does not exist on entity 'subject'",
                    "suggestions": ["id", "submitter_id", "gender"],
                }
            ],
            "next_steps": {
                "suggestions": [
                    "Fix the validation errors using the suggestions above"
                ],
                "workflow": [
                    "1. Fix the validation errors",
                    "2. Re-run validate_query()",
                ],
                "alternative": "Start fresh with query_template() for a guaranteed valid query",
            },
        }

        result = await mock_query_service.validate_query(
            "{ subject { invalid_field } }"
        )

        assert result["valid"] is False
        assert len(result["errors"]) > 0
        assert "next_steps" in result

        # Check error structure
        error = result["errors"][0]
        assert "entity" in error
        assert "field" in error
        assert "message" in error
        assert "suggestions" in error

    @pytest.mark.asyncio
    async def test_execute_graphql_with_errors(self, mcp_test_setup):
        """Test execute_graphql returning GraphQL errors"""
        mock_query_service = mcp_test_setup["mock_query_service"]

        # Mock GraphQL errors
        mock_query_service.execute_graphql.return_value = {
            "errors": [
                {"message": "Field 'invalid_field' doesn't exist on type 'Subject'"}
            ],
            "data": None,
            "execution_guidance": {
                "suggestions": ["Use validate_query() to check field names"],
                "recommended_workflow": [
                    "1. Use validate_query() to check your query syntax and field names",
                    "2. If validation fails, use the suggestions to fix errors",
                    "3. Use execute_graphql() to run the validated query",
                ],
            },
        }

        result = await mock_query_service.execute_graphql(
            "{ subject { invalid_field } }"
        )

        assert "errors" in result
        assert len(result["errors"]) > 0
        assert "execution_guidance" in result

        # Check error guidance structure
        guidance = result["execution_guidance"]
        assert "suggestions" in guidance
        assert "recommended_workflow" in guidance


class TestToolIntegration:
    """Test tool integration and workflow"""

    @pytest.mark.asyncio
    async def test_complete_workflow(self, mcp_test_setup):
        """Test complete workflow: schema_summary -> query_template -> validate -> execute"""
        mock_gen3_service = mcp_test_setup["mock_gen3_service"]
        mock_query_service = mcp_test_setup["mock_query_service"]

        # Load test schema
        test_schema_path = Path(__file__).parent / "ex_schema.json"
        with open(test_schema_path) as f:
            test_schema = json.load(f)

        mock_gen3_service.get_schema_full.return_value = test_schema

        # Step 1: Get schema summary
        full_schema = await mock_gen3_service.get_schema_full()
        schema_extract = SchemaExtract.from_full_schema(full_schema)
        schema_result = json.loads(repr(schema_extract))

        # Verify we have comprehensive entity information in one call
        assert "subject" in schema_result
        subject_info = schema_result["subject"]

        # This should include everything
        assert "schema_summary" in subject_info
        assert "query_patterns" in subject_info
        assert "position_description" in subject_info["schema_summary"]

        # Step 2: Generate template
        template_result = await mock_query_service.generate_query_template("subject")
        assert template_result["exists"] is True
        assert "template" in template_result

        # Step 3: Validate query
        query = template_result["template"]
        validation_result = await mock_query_service.validate_query(query)
        assert validation_result["valid"] is True

        # Step 4: Execute query
        execution_result = await mock_query_service.execute_graphql(query)
        assert "data" in execution_result

        # Verify service calls
        mock_gen3_service.get_schema_full.assert_called()
        mock_query_service.generate_query_template.assert_called()
        mock_query_service.validate_query.assert_called()
        mock_query_service.execute_graphql.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
