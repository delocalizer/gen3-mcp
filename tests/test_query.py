"""Comprehensive tests for QueryService module"""

from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from gen3_mcp.exceptions import GraphQLError, NoSuchEntityError
from gen3_mcp.query import QueryService, get_query_service
from gen3_mcp.schema import SchemaManager


class TestQueryServiceInitialization:
    """Test QueryService initialization and basic properties"""

    def test_query_service_initialization(self, mock_client):
        """Test QueryService initialization"""
        schema_manager = SchemaManager(mock_client)
        service = QueryService(schema_manager)

        assert service.schema_manager is schema_manager
        assert service.client is mock_client
        assert service.config is mock_client.config


class TestExecuteGraphQL:
    """Test execute_graphql method with various scenarios

    Focuses on GraphQL-specific error transformations and business logic.
    Generic HTTP transport errors are tested in test_client.py.
    """

    @pytest.mark.asyncio
    async def test_execute_graphql_success(self, query_service):
        """Test successful GraphQL query execution"""
        # Override the default mock to return specific test data
        query_service.client.post_json.side_effect = None  # Clear side_effect
        query_service.client.post_json.return_value = {
            "data": {
                "subject": [
                    {"id": "123", "submitter_id": "test_001", "gender": "Female"}
                ]
            }
        }

        query = "{ subject { id submitter_id gender } }"
        result = await query_service.execute_graphql(query)

        assert result["data"]["subject"][0]["id"] == "123"
        assert "errors" not in result
        query_service.client.post_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_graphql_http_client_error_graphql_transformation(
        self, query_service
    ):
        """Test GraphQL execution transforms HTTP 400 errors with GraphQL content to GraphQLError"""
        # Mock HTTP 400 error with GraphQL error response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.url = "https://test.gen3.io/graphql"
        mock_response.json.return_value = {
            "data": None,
            "errors": ["Cannot query field 'invalid_field' on type 'Subject'"],
        }

        http_error = httpx.HTTPStatusError(
            "Bad Request", request=Mock(), response=mock_response
        )
        query_service.client.post_json.side_effect = http_error

        query = "{ subject { invalid_field } }"
        # Domain-specific: HTTP 400 with GraphQL errors gets converted to GraphQLError
        with pytest.raises(GraphQLError) as exc_info:
            await query_service.execute_graphql(query)

        error = exc_info.value
        assert "invalid_field" in str(error.errors)
        assert "GraphQL query execution failed" in error.message

    @pytest.mark.asyncio
    async def test_execute_graphql_with_graphql_errors(self, query_service):
        """Test successful HTTP but with GraphQL errors in response"""
        query_service.client.post_json.side_effect = None  # Clear side_effect
        query_service.client.post_json.return_value = {
            "data": None,
            "errors": ["Syntax error in query"],
        }

        query = "{ subject { id }"  # Missing closing brace
        result = await query_service.execute_graphql(query)

        # Should return the GraphQL errors as-is
        assert "errors" in result
        assert "Syntax error in query" in result["errors"]


class TestGenerateQueryTemplate:
    """Test generate_query_template method"""

    @pytest.mark.parametrize(
        "entity,include_relationships,max_fields,expected_checks",
        [
            (
                "subject",
                True,
                20,
                {
                    "has_relationships": True,
                    "has_basic_fields": ["id", "submitter_id"],
                    "relationship_check": "studies {",
                },
            ),
            (
                "subject",
                False,
                20,
                {
                    "has_relationships": False,
                    "has_basic_fields": ["id", "submitter_id"],
                    "relationship_check": None,
                },
            ),
            (
                "subject",
                True,
                5,
                {
                    "has_relationships": True,
                    "max_fields": 5,
                    "has_basic_fields": ["id"],
                },
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_generate_query_template_variations(
        self, query_service, entity, include_relationships, max_fields, expected_checks
    ):
        """Test query template generation with various parameters"""
        result = await query_service.generate_query_template(
            entity, include_relationships, max_fields
        )

        # Common assertions
        assert result["entity_name"] == entity
        template = result["template"]
        assert f"{entity}(first: 10)" in template

        # Check basic fields
        for field in expected_checks.get("has_basic_fields", []):
            assert field in template

        # Check relationships
        if expected_checks.get("has_relationships"):
            relationship_check = expected_checks.get("relationship_check")
            if relationship_check:
                assert relationship_check in template
        elif (
            "has_relationships" in expected_checks
            and not expected_checks["has_relationships"]
        ):
            assert "studies {" not in template

        # Check field limits
        if "max_fields" in expected_checks:
            lines = template.split("\n")
            # Count only root-level scalar fields (exclude relationship blocks)
            root_fields = []
            in_relationship = False
            for line in lines[2:]:  # Skip first two lines: { and entity(
                line = line.strip()
                if not line:  # Skip empty lines
                    continue
                if line.endswith("}}"):  # End of template
                    break
                if line.endswith("{"):  # Start of relationship block
                    in_relationship = True
                    continue
                if line == "}":
                    in_relationship = False
                    continue
                if not in_relationship and not line.endswith("{"):
                    root_fields.append(line)

            assert (
                len(root_fields) == expected_checks["max_fields"]
            ), f"Expected {expected_checks['max_fields']} root fields, got {len(root_fields)}: {root_fields}"

    @pytest.mark.asyncio
    async def test_generate_query_template_nonexistent_entity(self, query_service):
        """Test generate_query_template with nonexistent entity"""
        with pytest.raises(NoSuchEntityError) as exc_info:
            await query_service.generate_query_template("nonexistent_entity")

        error = exc_info.value
        assert "nonexistent_entity" in error.message
        # Suggestions may be empty if no similar entity names exist
        assert isinstance(error.suggestions, list)

    @pytest.mark.asyncio
    async def test_generate_query_template_typo(self, query_service):
        """Test generate_query_template with typo suggests correct entity"""
        with pytest.raises(NoSuchEntityError) as exc_info:
            await query_service.generate_query_template("subjct")  # Typo

        error = exc_info.value
        # Should suggest "subject"
        assert any("subject" in suggestion for suggestion in error.suggestions)


class TestValidateQuery:
    """Test validate_query method"""

    @pytest.mark.asyncio
    async def test_validate_query_success(self, query_service):
        """Test successful query validation"""
        # Mock the graphql_validator.validate_graphql function
        with patch("gen3_mcp.query.validate_graphql") as mock_validate:
            mock_validate.return_value = None  # Success returns None

            query = "{ subject { id } }"

            result = await query_service.validate_query(query)
            assert result is None  # Success returns None

    @pytest.mark.asyncio
    async def test_validate_query_with_errors(self, query_service):
        """Test query validation with errors"""
        # Mock validation to raise GraphQLError
        with patch("gen3_mcp.query.validate_graphql") as mock_validate:
            mock_validate.side_effect = GraphQLError(
                "Validation failed",
                errors=["Field 'invalid_field' not found on type 'Subject'"],
                suggestions=["Try 'submitter_id' instead"],
            )

            query = "{ subject { invalid_field } }"
            # validate_query raises GraphQLError on failure
            with pytest.raises(GraphQLError) as exc_info:
                await query_service.validate_query(query)

            error = exc_info.value
            assert "invalid_field" in str(error.errors)


class TestEntitySuggestionIntegration:
    """Test entity suggestion integration in query context"""

    @pytest.mark.asyncio
    async def test_entity_suggestion_integration(self, query_service):
        """Test that entity suggestions work in query template generation context"""
        with pytest.raises(NoSuchEntityError) as exc_info:
            await query_service.generate_query_template("subjct")  # Typo

        error = exc_info.value
        # Should suggest "subject"
        assert any("subject" in suggestion for suggestion in error.suggestions)


class TestGetQueryService:
    """Test get_query_service singleton factory"""

    def test_get_query_service_returns_same_instance(self):
        """Test that get_query_service returns the same instance"""
        service1 = get_query_service()
        service2 = get_query_service()

        assert service1 is service2

    def test_get_query_service_cache_clear(self):
        """Test clearing the singleton cache"""
        service1 = get_query_service()

        # Clear the cache
        get_query_service.cache_clear()

        # Should get new instance
        service2 = get_query_service()
        assert service1 is not service2


class TestIntegration:
    """Integration tests combining multiple QueryService components"""

    @pytest.mark.asyncio
    async def test_full_workflow_success(self, query_service):
        """Test complete query-specific workflow: template -> validate -> execute"""
        # 1. Generate template (query-specific functionality)
        template_result = await query_service.generate_query_template("subject")
        assert "template" in template_result

        # 2. Validate the generated template (query-specific functionality)
        query = template_result["template"]
        # Mock validation success
        with patch("gen3_mcp.query.validate_graphql") as mock_validate:
            mock_validate.return_value = None  # Success
            validation_result = await query_service.validate_query(query)
            assert validation_result is None  # Success returns None

        # 3. Execute the validated query (query-specific functionality)
        query_service.client.post_json.side_effect = None  # Clear side_effect
        query_service.client.post_json.return_value = {
            "data": {"subject": [{"id": "123"}]}
        }
        execution_result = await query_service.execute_graphql(query)
        assert "data" in execution_result
        assert "errors" not in execution_result

    @pytest.mark.asyncio
    async def test_error_handling_chain(self, query_service):
        """Test error handling across the workflow"""
        # 1. Try invalid entity
        with pytest.raises(NoSuchEntityError) as exc_info:
            await query_service.generate_query_template("invalid_entity")

        error = exc_info.value
        assert len(error.suggestions) >= 0  # May or may not have suggestions

        # 2. If suggestions available, they should be valid entity names
        if error.suggestions:
            # The context should include the available suggestions
            assert "available_suggestions" in error.context


# Test Fixtures leveraging existing conftest.py infrastructure
@pytest.fixture
async def query_service(mock_client, schema_extract):
    """QueryService fixture using existing test infrastructure from conftest.py"""
    # Create SchemaManager with the properly configured mock_client from conftest.py
    schema_manager = SchemaManager(mock_client)

    # Override get_schema_extract to return test data directly
    # This avoids the full schema fetch process and uses our test data
    schema_manager.get_schema_extract = AsyncMock(return_value=schema_extract)

    # Create QueryService with the mocked schema manager
    service = QueryService(schema_manager)

    return service
