"""Comprehensive tests for QueryService module"""

from unittest.mock import AsyncMock, patch

import pytest

from gen3_mcp.models import ClientResponse, ErrorCategory, QueryValidationResult
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
    """Test execute_graphql method with various scenarios"""

    @pytest.mark.asyncio
    async def test_execute_graphql_success(self, query_service):
        """Test successful GraphQL query execution"""
        # Clear the side_effect and set return_value
        query_service.client.post_json.side_effect = None
        query_service.client.post_json.return_value = ClientResponse(
            success=True,
            status_code=200,
            data={
                "data": {
                    "subject": [
                        {"id": "123", "submitter_id": "test_001", "gender": "Female"}
                    ]
                }
            },
        )

        query = "{ subject { id submitter_id gender } }"
        result = await query_service.execute_graphql(query)

        assert result["data"]["subject"][0]["id"] == "123"
        assert "errors" not in result
        query_service.client.post_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_graphql_network_error(self, query_service):
        """Test GraphQL execution with network error"""
        # Clear the side_effect and set return_value
        query_service.client.post_json.side_effect = None
        query_service.client.post_json.return_value = ClientResponse(
            success=False,
            error_category=ErrorCategory.NETWORK,
            errors=["Network error: Connection timeout"],
        )

        query = "{ subject { id } }"
        result = await query_service.execute_graphql(query)

        assert "errors" in result
        assert "Connection timeout" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_execute_graphql_http_client_error(self, query_service):
        """Test GraphQL execution with HTTP 4xx error (bad query)"""
        # Clear the side_effect and set return_value
        query_service.client.post_json.side_effect = None
        query_service.client.post_json.return_value = ClientResponse(
            success=False,
            status_code=400,
            error_category=ErrorCategory.HTTP_CLIENT,
            errors=["Cannot query field 'invalid_field' on type 'Subject'"],
            data={
                "data": None,
                "errors": ["Cannot query field 'invalid_field' on type 'Subject'"],
            },
        )

        query = "{ subject { invalid_field } }"
        result = await query_service.execute_graphql(query)

        assert "errors" in result
        assert "invalid_field" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_execute_graphql_http_server_error(self, query_service):
        """Test GraphQL execution with HTTP 5xx error"""
        # Clear the side_effect and set return_value
        query_service.client.post_json.side_effect = None
        query_service.client.post_json.return_value = ClientResponse(
            success=False,
            status_code=500,
            error_category=ErrorCategory.HTTP_SERVER,
            errors=["Unexpected error: Internal server error"],
        )

        query = "{ subject { id } }"
        result = await query_service.execute_graphql(query)

        assert "errors" in result
        assert "Internal server error" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_execute_graphql_with_graphql_errors(self, query_service):
        """Test successful HTTP but with GraphQL errors in response"""
        # Clear the side_effect and set return_value
        query_service.client.post_json.side_effect = None
        query_service.client.post_json.return_value = ClientResponse(
            success=True,
            status_code=200,
            data={"data": None, "errors": ["Syntax error in query"]},
        )

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
                    "exists": True,
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
                    "exists": True,
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
                    "exists": True,
                    "has_relationships": True,
                    "max_fields": 5,
                    "has_basic_fields": ["id"],
                },
            ),
            (
                "nonexistent_entity",
                True,
                20,
                {
                    "exists": False,
                    "should_have_suggestions": True,
                    "should_have_error": True,
                },
            ),
            (
                "subjct",
                True,
                20,
                {  # Typo test
                    "exists": False,
                    "should_have_suggestions": True,
                    "should_suggest_subject": True,
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
        assert result["exists"] == expected_checks["exists"]

        if expected_checks["exists"]:
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
        else:
            # Non-existent entity checks
            if expected_checks.get("should_have_suggestions"):
                assert "suggestions" in result
            if expected_checks.get("should_have_error"):
                assert "error" in result
            if expected_checks.get("should_suggest_subject"):
                suggestion_names = [s["name"] for s in result["suggestions"]]
                assert "subject" in suggestion_names


class TestValidateQuery:
    """Test validate_query method"""

    @pytest.mark.asyncio
    async def test_validate_query_success(self, query_service):
        """Test successful query validation"""
        # Mock the graphql_validator.validate_graphql function
        mock_validation_result = QueryValidationResult(
            valid=True, query="{ subject { id } }"
        )

        with patch("gen3_mcp.query.validate_graphql") as mock_validate:
            mock_validate.return_value = mock_validation_result

            query = "{ subject { id } }"
            result = await query_service.validate_query(query)

            assert isinstance(result, QueryValidationResult)
            assert result.valid
            assert result.query == query

    @pytest.mark.asyncio
    async def test_validate_query_with_errors(self, query_service):
        """Test query validation with errors"""
        from gen3_mcp.models import QueryValidationError

        mock_validation_result = QueryValidationResult(
            valid=False,
            query="{ subject { invalid_field } }",
            errors=[
                QueryValidationError(
                    entity="subject",
                    field="invalid_field",
                    error_type="unknown_field",
                    message="Field 'invalid_field' not found on type 'Subject'",
                    suggestions=["Try 'submitter_id' instead"],
                )
            ],
        )

        with patch("gen3_mcp.query.validate_graphql") as mock_validate:
            mock_validate.return_value = mock_validation_result

            query = "{ subject { invalid_field } }"
            result = await query_service.validate_query(query)

            assert isinstance(result, QueryValidationResult)
            assert not result.valid
            assert len(result.errors) == 1
            assert result.errors[0].field == "invalid_field"


class TestEntitySuggestionIntegration:
    """Test entity suggestion integration in query context"""

    @pytest.mark.asyncio
    async def test_entity_suggestion_integration(self, query_service):
        """Test that entity suggestions work in query template generation context"""
        result = await query_service.generate_query_template("subjct")  # Typo

        assert not result["exists"]
        assert "suggestions" in result
        suggestion_names = [s["name"] for s in result["suggestions"]]
        assert (
            "subject" in suggestion_names
        )  # Integration with utils.suggest_similar_strings_with_scores


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
        """Test complete workflow from template generation to execution"""
        # 1. Generate template
        template_result = await query_service.generate_query_template("subject")
        assert template_result["exists"]

        # 2. Validate the generated template
        query = template_result["template"]
        # Mock validation success
        with patch("gen3_mcp.query.validate_graphql") as mock_validate:
            mock_validate.return_value = QueryValidationResult(valid=True, query=query)
            validation_result = await query_service.validate_query(query)
            assert validation_result.valid

        # 3. Execute the validated query
        query_service.client.post_json.return_value = ClientResponse(
            success=True, status_code=200, data={"data": {"subject": [{"id": "123"}]}}
        )
        execution_result = await query_service.execute_graphql(query)
        assert "data" in execution_result
        assert "errors" not in execution_result

    @pytest.mark.asyncio
    async def test_error_handling_chain(self, query_service):
        """Test error handling across the workflow"""
        # 1. Try invalid entity
        template_result = await query_service.generate_query_template("invalid_entity")
        assert not template_result["exists"]
        assert "suggestions" in template_result

        # 2. Use suggested entity if available
        if template_result["suggestions"]:
            suggested_entity = template_result["suggestions"][0]["name"]
            template_result = await query_service.generate_query_template(
                suggested_entity
            )
            assert template_result["exists"]


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
