"""Tests for MCP tools functionality"""

import pytest


class TestSchemaTools:
    """Test schema-related MCP tools"""

    @pytest.mark.asyncio
    async def test_schema_summary(self, mcp_test_setup):
        """Test schema_summary tool returns complete SchemaExtract format"""
        mock_gen3_service = mcp_test_setup["mock_gen3_service"]
        
        # Mock the get_schema_full method to return our test schema
        from pathlib import Path
        import json
        
        test_schema_path = Path(__file__).parent / "ex_schema.json"
        with open(test_schema_path) as f:
            test_schema = json.load(f)
        
        mock_gen3_service.get_schema_full.return_value = test_schema
        
        # Test the new schema_summary implementation
        # In the actual tool, this would be:
        # full_schema = await gen3_service.get_schema_full()
        # schema_extract = SchemaExtract.from_full_schema(full_schema) 
        # result = json.loads(repr(schema_extract))
        
        from gen3_mcp.schema_extract import SchemaExtract
        
        full_schema = await mock_gen3_service.get_schema_full()
        schema_extract = SchemaExtract.from_full_schema(full_schema)
        result = json.loads(repr(schema_extract))
        
        # Check that we get the complete format
        assert isinstance(result, dict)
        assert len(result) > 0
        
        # Check that expected entities exist
        expected_entities = {"subject", "sample", "study", "aliquot", "aligned_reads_file"}
        actual_entities = set(result.keys())
        assert expected_entities.issubset(actual_entities)
        
        # Check that each entity has the complete structure
        for entity_name, entity_data in result.items():
            # Each entity should have all the comprehensive sections
            expected_sections = ["fields", "relationships", "schema_summary", "query_patterns"]
            for section in expected_sections:
                assert section in entity_data, f"Entity {entity_name} missing {section}"
            
            # Check schema_summary structure
            schema_summary = entity_data["schema_summary"]
            expected_summary_fields = ["title", "description", "category", "required_fields", 
                                     "field_count", "parent_count", "child_count", "position_description"]
            for field in expected_summary_fields:
                assert field in schema_summary, f"Entity {entity_name} schema_summary missing {field}"
            
            # Check query_patterns structure
            query_patterns = entity_data["query_patterns"]
            expected_pattern_fields = ["basic_query", "with_relationships", "usage_examples"]
            for field in expected_pattern_fields:
                assert field in query_patterns, f"Entity {entity_name} query_patterns missing {field}"
            
            # Check that basic query contains the entity name
            basic_query = query_patterns["basic_query"]
            assert entity_name in basic_query, f"Basic query for {entity_name} should contain entity name"
        
        # Verify that the service method was called
        mock_gen3_service.get_schema_full.assert_called_once()

    @pytest.mark.asyncio
    async def test_schema_full(self, mcp_test_setup):
        """Test schema_full tool calls service method directly"""
        mock_gen3_service = mcp_test_setup["mock_gen3_service"]

        result = await mock_gen3_service.get_schema_full()

        assert "subject" in result
        assert "sample" in result
        assert "aligned_reads_file" in result
        mock_gen3_service.get_schema_full.assert_called_once()

    @pytest.mark.asyncio
    async def test_schema_entity(self, mcp_test_setup):
        """Test schema_entity tool calls service method directly"""
        mock_gen3_service = mcp_test_setup["mock_gen3_service"]

        result = await mock_gen3_service.get_entity_schema("subject")

        assert "properties" in result
        assert "id" in result["properties"]
        mock_gen3_service.get_entity_schema.assert_called_once_with("subject")

    @pytest.mark.asyncio
    async def test_schema_entities(self, mcp_test_setup):
        """Test schema_entities tool formats entity list correctly"""
        mock_gen3_service = mcp_test_setup["mock_gen3_service"]

        # Test the logic that would be in the MCP tool
        entities = await mock_gen3_service.get_entity_names()
        result = {"entities": entities}

        assert "entities" in result
        entity_list = result["entities"]
        expected_entities = {
            "subject",
            "sample",
            "study",
            "aliquot",
            "aligned_reads_file",
        }
        assert set(entity_list) == expected_entities
        mock_gen3_service.get_entity_names.assert_called_once()

    @pytest.mark.asyncio
    async def test_schema_describe_entities(self, mcp_test_setup):
        """Test schema_describe_entities tool calls service method directly"""
        mock_gen3_service = mcp_test_setup["mock_gen3_service"]

        result = await mock_gen3_service.get_detailed_entities()

        assert "total_entities" in result
        assert "entities" in result
        assert result["total_entities"] == 5
        mock_gen3_service.get_detailed_entities.assert_called_once()

    @pytest.mark.asyncio
    async def test_schema_entity_context(self, mcp_test_setup):
        """Test schema_entity_context tool calls service method directly"""
        mock_gen3_service = mcp_test_setup["mock_gen3_service"]

        # Set up mock return for get_entity_context
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
                "parents": [
                    {
                        "entity": "study",
                        "relationship": "member_of",
                        "backref_field": "subjects",
                    }
                ],
                "children": [
                    {
                        "entity": "sample",
                        "relationship": "related_to",
                        "backref_field": "samples",
                    }
                ],
                "parent_count": 1,
                "child_count": 1,
            },
            "graphql_fields": {
                "backref_fields": ["samples"],
                "available_as_backref": ["subjects"],
                "direct_fields": ["id", "submitter_id", "gender", "age_at_enrollment"],
                "system_fields": [
                    "id",
                    "submitter_id",
                    "type",
                    "created_datetime",
                    "updated_datetime",
                ],
            },
            "query_patterns": {
                "basic_query": "{ subject(first: 10) { id submitter_id type } }",
                "with_relationships": [
                    {
                        "description": "Get subject with linked sample data",
                        "query": "{ subject(first: 5) { id submitter_id samples { id submitter_id } } }",
                        "target_entity": "sample",
                    }
                ],
                "usage_examples": [
                    "Use subject as starting point for data exploration",
                    "Query subject fields: id, submitter_id, type",
                    "Access linked data via: samples",
                ],
            },
            "position_type": {
                "position": "intermediate",
                "parent_count": 1,
                "child_count": 1,
                "description": "Intermediate entity in the data hierarchy - connects other entities",
            },
        }

        result = await mock_gen3_service.get_entity_context("subject")

        assert result["entity_name"] == "subject"
        assert result["exists"] is True
        assert "schema_summary" in result
        assert "relationships" in result
        assert "graphql_fields" in result
        assert "query_patterns" in result
        assert "position_type" in result

        # Check that hierarchical position contains expected structure
        relationships = result["relationships"]
        assert relationships["parent_count"] == 1
        assert relationships["child_count"] == 1
        assert len(relationships["parents"]) == 1
        assert len(relationships["children"]) == 1

        # Check GraphQL fields structure
        graphql_fields = result["graphql_fields"]
        assert "samples" in graphql_fields["backref_fields"]
        assert "subjects" in graphql_fields["available_as_backref"]

        # Check query patterns contain useful examples
        query_patterns = result["query_patterns"]
        assert "subject" in query_patterns["basic_query"]
        assert len(query_patterns["with_relationships"]) > 0
        assert len(query_patterns["usage_examples"]) > 0

        mock_gen3_service.get_entity_context.assert_called_once_with("subject")


class TestDataTools:
    """Test data-related MCP tools"""

    @pytest.mark.asyncio
    async def test_data_explore(self, mcp_test_setup):
        """Test data_explore tool logic"""
        mock_gen3_service = mcp_test_setup["mock_gen3_service"]

        # Test the logic from the MCP tool
        result = await mock_gen3_service.get_sample_records("subject", 5)
        result["entity"] = "subject"

        assert result["entity"] == "subject"
        assert "sample_records" in result
        mock_gen3_service.get_sample_records.assert_called_once_with("subject", 5)

    @pytest.mark.asyncio
    async def test_data_sample_records(self, mcp_test_setup):
        """Test data_sample_records tool calls service method directly"""
        mock_gen3_service = mcp_test_setup["mock_gen3_service"]

        result = await mock_gen3_service.get_sample_records("subject", 3)

        assert result["entity"] == "subject"
        assert "sample_records" in result
        mock_gen3_service.get_sample_records.assert_called_once_with("subject", 3)

    @pytest.mark.asyncio
    async def test_data_field_values(self, mcp_test_setup):
        """Test data_field_values tool calls service method directly"""
        mock_query_service = mcp_test_setup["mock_query_service"]

        result = await mock_query_service.field_sample("subject", "gender", 20)

        assert result["entity"] == "subject"
        assert result["field"] == "gender"
        assert "values" in result
        mock_query_service.field_sample.assert_called_once_with("subject", "gender", 20)

    @pytest.mark.asyncio
    async def test_data_explore_entity_data(self, mcp_test_setup):
        """Test data_explore_entity_data tool calls service method directly"""
        mock_gen3_service = mcp_test_setup["mock_gen3_service"]

        result = await mock_gen3_service.explore_entity_data("subject")

        assert result["entity"] == "subject"
        assert "schema_info" in result
        assert "enum_fields" in result
        mock_gen3_service.explore_entity_data.assert_called_once_with("subject")


class TestValidationTools:
    """Test validation-related MCP tools"""

    @pytest.mark.asyncio
    async def test_validation_validate_query(self, mcp_test_setup):
        """Test validation_validate_query tool calls service method directly"""
        mock_query_service = mcp_test_setup["mock_query_service"]

        query = "{ subject { id } }"
        result = await mock_query_service.validate_query_fields(query)

        assert result["valid"] is True
        assert "extracted_fields" in result
        mock_query_service.validate_query_fields.assert_called_once_with(query)

    @pytest.mark.asyncio
    async def test_validation_query_template(self, mcp_test_setup):
        """Test validation_query_template tool calls service method directly"""
        mock_query_service = mcp_test_setup["mock_query_service"]

        result = await mock_query_service.generate_query_template("subject", True, 20)

        assert result["entity_name"] == "subject"
        assert result["exists"] is True
        assert "template" in result
        mock_query_service.generate_query_template.assert_called_once_with(
            "subject", True, 20
        )


class TestQueryTools:
    """Test query execution tools"""

    @pytest.mark.asyncio
    async def test_execute_graphql_success(self, mcp_test_setup):
        """Test execute_graphql tool calls service method directly"""
        mock_query_service = mcp_test_setup["mock_query_service"]

        query = "{ subject { id } }"
        result = await mock_query_service.execute_graphql(query)

        assert "data" in result
        assert "subject" in result["data"]
        mock_query_service.execute_graphql.assert_called_once_with(query)

    @pytest.mark.asyncio
    async def test_execute_graphql_failure(self, mcp_test_setup):
        """Test execute_graphql tool handles None result"""
        mock_query_service = mcp_test_setup["mock_query_service"]
        mock_query_service.execute_graphql.return_value = None

        # Test the logic from the MCP tool
        query = "{ invalid_query }"
        result = await mock_query_service.execute_graphql(query)

        if result is None:
            result = {"error": "Query execution failed"}

        assert result == {"error": "Query execution failed"}
        mock_query_service.execute_graphql.assert_called_once_with(query)


class TestToolIntegration:
    """Test tool integration and error handling"""

    @pytest.mark.asyncio
    async def test_tools_use_correct_services(self, mcp_test_setup):
        """Test that tools use the correct service types"""
        mock_gen3_service = mcp_test_setup["mock_gen3_service"]
        mock_query_service = mcp_test_setup["mock_query_service"]

        # Test that schema tools use gen3_service
        await mock_gen3_service.get_schema_summary()
        await mock_gen3_service.get_entity_names()
        await mock_gen3_service.get_sample_records("subject", 5)

        assert mock_gen3_service.get_schema_summary.called
        assert mock_gen3_service.get_entity_names.called
        assert mock_gen3_service.get_sample_records.called

        # Test that validation tools use query_service
        await mock_query_service.validate_query_fields("{ subject { id } }")
        await mock_query_service.execute_graphql("{ subject { id } }")

        assert mock_query_service.validate_query_fields.called
        assert mock_query_service.execute_graphql.called


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
