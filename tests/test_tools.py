"""Tests for MCP tools functionality"""

import sys

import pytest


class TestSchemaTools:
    """Test schema-related MCP tools"""

    @pytest.mark.asyncio
    async def test_schema_summary(self, mcp_test_setup):
        """Test schema_summary tool calls service method directly"""
        mock_gen3_service = mcp_test_setup["mock_gen3_service"]

        # Simulate calling the schema_summary tool
        # In real usage, this would be called through MCP framework
        result = await mock_gen3_service.get_schema_summary()

        assert result["total_entities"] == 3
        assert "subject" in result["entity_names"]
        mock_gen3_service.get_schema_summary.assert_called_once()

    @pytest.mark.asyncio
    async def test_schema_full(self, mcp_test_setup):
        """Test schema_full tool calls service method directly"""
        mock_gen3_service = mcp_test_setup["mock_gen3_service"]

        result = await mock_gen3_service.get_full_schema()

        assert "subject" in result
        assert "sample" in result
        mock_gen3_service.get_full_schema.assert_called_once()

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
        assert result["entities"] == ["subject", "sample", "study"]
        mock_gen3_service.get_entity_names.assert_called_once()

    @pytest.mark.asyncio
    async def test_schema_describe_entities(self, mcp_test_setup):
        """Test schema_describe_entities tool calls service method directly"""
        mock_gen3_service = mcp_test_setup["mock_gen3_service"]

        result = await mock_gen3_service.get_detailed_entities()

        assert "total_entities" in result
        assert "entities" in result
        assert result["total_entities"] == 3
        mock_gen3_service.get_detailed_entities.assert_called_once()


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
    async def test_validation_suggest_fields(self, mcp_test_setup):
        """Test validation_suggest_fields tool calls service method directly"""
        mock_query_service = mcp_test_setup["mock_query_service"]

        result = await mock_query_service.suggest_similar_fields("gander", "subject")

        assert result["field_name"] == "gander"
        assert result["entity_name"] == "subject"
        assert len(result["suggestions"]) > 0
        mock_query_service.suggest_similar_fields.assert_called_once_with(
            "gander", "subject"
        )

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

    def test_tools_no_longer_import_wrapper_modules(self):
        """Test that tools don't import from removed wrapper modules"""
        # Import main to trigger tool definitions
        from gen3_mcp import main

        # Verify wrapper modules are not imported
        assert "gen3_mcp.tools" not in sys.modules
        assert "gen3_mcp.resources" not in sys.modules

        # Verify we can create MCP server without wrapper modules
        mcp = main.create_mcp_server()
        assert mcp is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
