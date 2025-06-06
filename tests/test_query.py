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

    @pytest.mark.asyncio
    async def test_generate_query_template_success(self, query_service):
        """Test successful query template generation"""
        result = await query_service.generate_query_template("subject")

        assert result["exists"]
        assert result["entity_name"] == "subject"
        assert "template" in result
        assert "subject(first: 10)" in result["template"]
        assert "id" in result["template"]
        assert "submitter_id" in result["template"]

    @pytest.mark.asyncio
    async def test_generate_query_template_with_relationships(self, query_service):
        """Test template generation with relationships included"""
        result = await query_service.generate_query_template(
            "subject", include_relationships=True
        )

        assert result["exists"]
        template = result["template"]

        # Should include relationship fields
        assert "studies {" in template

    @pytest.mark.asyncio
    async def test_generate_query_template_without_relationships(self, query_service):
        """Test template generation without relationships"""
        result = await query_service.generate_query_template(
            "subject", include_relationships=False
        )

        assert result["exists"]
        template = result["template"]

        # Should not include relationship fields
        assert "studies {" not in template

    @pytest.mark.asyncio
    async def test_generate_query_template_max_fields_limit(self, query_service):
        """Test template generation with field limit"""
        result = await query_service.generate_query_template("subject", max_fields=5)
        print(result)

        assert result["exists"]
        template = result["template"]

        # Count the number of scalar fields in root entity
        lines = template.split("\n")
        root_fields = []
        for line in lines[2:]:
            if line.endswith("{"):
                break
            root_fields.append(line)
        # Should respect the max_fields limit
        assert len(root_fields) == 5

    @pytest.mark.asyncio
    async def test_generate_query_template_entity_not_found(self, query_service):
        """Test template generation for non-existent entity"""
        result = await query_service.generate_query_template("nonexistent_entity")

        assert not result["exists"]
        assert result["entity_name"] == "nonexistent_entity"
        assert result["template"] is None
        assert "error" in result
        assert "suggestions" in result

    @pytest.mark.asyncio
    async def test_generate_query_template_similar_suggestions(self, query_service):
        """Test that similar entity suggestions are provided"""
        result = await query_service.generate_query_template("subjct")  # Typo

        assert not result["exists"]
        assert "suggestions" in result

        # Should suggest "subject" as similar
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


class TestSimilarityUtilities:
    """Test similarity utility functions"""

    def test_suggest_similar_strings_with_scores_exact_match(self, schema_extract):
        """Test finding similar entities with exact match"""
        from gen3_mcp.utils import suggest_similar_strings_with_scores

        suggestions = suggest_similar_strings_with_scores(
            "subject", set(schema_extract.keys())
        )

        # Should find exact match with high similarity
        subject_suggestions = [s for s in suggestions if s["name"] == "subject"]
        assert len(subject_suggestions) == 1
        assert subject_suggestions[0]["similarity"] == 1.0

    def test_suggest_similar_strings_with_scores_typo(self, schema_extract):
        """Test finding similar entities with typo"""
        from gen3_mcp.utils import suggest_similar_strings_with_scores

        suggestions = suggest_similar_strings_with_scores(
            "subjct", set(schema_extract.keys())
        )

        # Should find "subject" as similar
        assert len(suggestions) > 0
        assert "subject" in [s["name"] for s in suggestions]

        # Should be sorted by similarity (highest first)
        similarities = [s["similarity"] for s in suggestions]
        assert similarities == sorted(similarities, reverse=True)

    def test_suggest_similar_strings_with_scores_no_match(self, schema_extract):
        """Test finding similar entities with no good matches"""
        from gen3_mcp.utils import suggest_similar_strings_with_scores

        suggestions = suggest_similar_strings_with_scores(
            "completely_different", set(schema_extract.keys())
        )

        # May return empty list or very low similarity matches
        # All similarities should be below the default threshold or list should be empty
        for suggestion in suggestions:
            assert suggestion["similarity"] <= 0.5

    def test_suggest_similar_strings_with_scores_case_insensitive(self, schema_extract):
        """Test that similarity matching is case insensitive"""
        from gen3_mcp.utils import suggest_similar_strings_with_scores

        suggestions_lower = suggest_similar_strings_with_scores(
            "subject", set(schema_extract.keys())
        )
        suggestions_upper = suggest_similar_strings_with_scores(
            "SUBJECT", set(schema_extract.keys())
        )

        # Should return same results regardless of case
        assert len(suggestions_lower) == len(suggestions_upper)

    def test_suggest_similar_strings_simple(self):
        """Test the simple string suggestion function"""
        from gen3_mcp.utils import suggest_similar_strings

        candidates = ["subject", "study", "sample", "aliquot"]
        suggestions = suggest_similar_strings("subjct", candidates)

        # Should suggest "subject" as most similar
        assert "subject" in suggestions
        assert suggestions[0] == "subject"  # Should be first due to highest similarity


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
        assert template_result["exists"] is True

        # 2. Validate the generated template
        query = template_result["template"]
        # Mock validation success
        with patch("gen3_mcp.query.validate_graphql") as mock_validate:
            mock_validate.return_value = QueryValidationResult(valid=True, query=query)
            validation_result = await query_service.validate_query(query)
            assert validation_result.valid is True

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
        assert template_result["exists"] is False
        assert "suggestions" in template_result

        # 2. Use suggested entity if available
        if template_result["suggestions"]:
            suggested_entity = template_result["suggestions"][0]["name"]
            template_result = await query_service.generate_query_template(
                suggested_entity
            )
            assert template_result["exists"] is True


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


# Additional test utilities
class TestUtils:
    """Utility methods for testing"""

    @staticmethod
    def create_mock_client_response(
        success=True,
        status_code=200,
        data=None,
        error_message=None,
        error_category=None,
    ):
        """Helper to create ClientResponse objects for testing"""
        return ClientResponse(
            success=success,
            status_code=status_code,
            data=data,
            error_message=error_message,
            error_category=error_category,
        )

    @staticmethod
    def assert_graphql_template_structure(template: str, entity_name: str):
        """Helper to assert GraphQL template has expected structure"""
        assert f"{entity_name}(first: 10)" in template
        assert template.startswith("{")
        assert template.endswith("}")
        assert "id" in template  # Should always include id field
