"""Tests for Gen3Client and Response"""

from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from gen3_mcp.client import Gen3Client
from gen3_mcp.config import Config
from gen3_mcp.exceptions import Gen3SchemaError
from gen3_mcp.models import ErrorCategory, Response
from gen3_mcp.schema import SchemaManager


class TestResponse:
    """Test the Response model"""

    @pytest.mark.parametrize(
        "test_case",
        [
            {
                "name": "success_response",
                "params": {
                    "success": True,
                    "status_code": 200,
                    "data": {"test": "data"},
                },
                "expected": {
                    "success": True,
                    "status_code": 200,
                    "error_category": None,
                    "errors": [],
                    "data": {"test": "data"},
                },
            },
            {
                "name": "http_client_error",
                "params": {
                    "success": False,
                    "status_code": 404,
                    "error_category": ErrorCategory.HTTP_CLIENT,
                    "errors": ["Not found"],
                },
                "expected": {
                    "success": False,
                    "status_code": 404,
                    "error_category": ErrorCategory.HTTP_CLIENT,
                    "errors": ["Not found"],
                    "data": None,
                },
            },
            {
                "name": "network_error",
                "params": {
                    "success": False,
                    "error_category": ErrorCategory.NETWORK,
                    "errors": ["Network error"],
                },
                "expected": {
                    "success": False,
                    "error_category": ErrorCategory.NETWORK,
                    "errors": ["Network error"],
                    "status_code": None,
                    "data": None,
                },
            },
            {
                "name": "http_server_error",
                "params": {
                    "success": False,
                    "status_code": 500,
                    "error_category": ErrorCategory.HTTP_SERVER,
                    "errors": ["Server error"],
                },
                "expected": {
                    "success": False,
                    "status_code": 500,
                    "error_category": ErrorCategory.HTTP_SERVER,
                    "errors": ["Server error"],
                    "data": None,
                },
            },
            {
                "name": "json_parse_error",
                "params": {
                    "success": False,
                    "status_code": 200,
                    "error_category": ErrorCategory.JSON_PARSE,
                    "errors": ["Invalid JSON"],
                },
                "expected": {
                    "success": False,
                    "status_code": 200,
                    "error_category": ErrorCategory.JSON_PARSE,
                    "errors": ["Invalid JSON"],
                    "data": None,
                },
            },
            {
                "name": "other_error",
                "params": {
                    "success": False,
                    "error_category": ErrorCategory.OTHER,
                    "errors": ["Other error"],
                },
                "expected": {
                    "success": False,
                    "error_category": ErrorCategory.OTHER,
                    "errors": ["Other error"],
                    "status_code": None,
                    "data": None,
                },
            },
        ],
    )
    def test_client_response_creation(self, test_case):
        """Test Response creation with various configurations"""
        response = Response(**test_case["params"])

        for attr, expected_value in test_case["expected"].items():
            actual_value = getattr(response, attr)
            assert (
                actual_value == expected_value
            ), f"Expected {attr}={expected_value}, got {actual_value}"


class TestGen3Client:
    """Test Gen3Client HTTP operations"""

    @pytest.fixture
    def config(self):
        """Config fixture for client tests"""
        return Config(
            base_url="https://test.gen3.io",
            credentials_file="/tmp/test_creds.json",
            log_level="DEBUG",
        )

    @pytest.fixture
    def mock_auth_manager(self):
        """Mock auth manager"""
        mock_auth = Mock()
        mock_auth.ensure_valid_token = AsyncMock()
        return mock_auth

    @pytest.fixture
    def mock_http_client(self):
        """Mock httpx AsyncClient"""
        return Mock(spec=httpx.AsyncClient)

    @pytest.fixture
    def client_with_mocks(
        self, config, mock_auth_manager, mock_http_client, monkeypatch
    ):
        """Gen3Client with mocked dependencies"""
        client = Gen3Client(config)

        # Replace the real clients with mocks
        client._http_client = mock_http_client
        client._auth_manager = mock_auth_manager

        return client

    @pytest.mark.asyncio
    async def test_get_json_success(self, client_with_mocks, mock_http_client):
        """Test successful get_json request"""
        # Mock successful HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"test": "data"}
        mock_response.raise_for_status.return_value = None

        mock_http_client.get = AsyncMock(return_value=mock_response)

        # Test the request
        result = await client_with_mocks.get_json("https://test.gen3.io/schema")

        assert isinstance(result, Response)
        assert result.is_success
        assert result.status_code == 200
        assert result.data == {"test": "data"}
        assert result.errors == []

    @pytest.mark.parametrize(
        "method,http_method,error_setup,expected",
        [
            # Network errors
            (
                "get_json",
                "get",
                {"exception": httpx.ConnectError("Connection failed")},
                {
                    "category": ErrorCategory.NETWORK,
                    "status_code": None,
                    "error_contains": "Network error",
                },
            ),
            (
                "post_json",
                "post",
                {"exception": httpx.ConnectError("Connection failed")},
                {
                    "category": ErrorCategory.NETWORK,
                    "status_code": None,
                    "error_contains": "Network error",
                },
            ),
            # HTTP client errors
            (
                "get_json",
                "get",
                {"http_error": 404},
                {
                    "category": ErrorCategory.HTTP_CLIENT,
                    "status_code": 404,
                    "error_contains": "HTTP 404 error",
                },
            ),
            (
                "post_json",
                "post",
                {"http_error": 400},
                {
                    "category": ErrorCategory.HTTP_CLIENT,
                    "status_code": 400,
                    "error_contains": "HTTP 400 error",
                },
            ),
            # HTTP server errors
            (
                "get_json",
                "get",
                {"http_error": 500},
                {
                    "category": ErrorCategory.HTTP_SERVER,
                    "status_code": 500,
                    "error_contains": "HTTP 500 error",
                },
            ),
            (
                "post_json",
                "post",
                {"http_error": 500},
                {
                    "category": ErrorCategory.HTTP_SERVER,
                    "status_code": 500,
                    "error_contains": "HTTP 500 error",
                },
            ),
            # JSON parse errors
            (
                "get_json",
                "get",
                {"json_error": ValueError("Invalid JSON")},
                {
                    "category": ErrorCategory.JSON_PARSE,
                    "status_code": 200,
                    "error_contains": "Response is not valid JSON",
                },
            ),
            (
                "post_json",
                "post",
                {"json_error": ValueError("Invalid JSON")},
                {
                    "category": ErrorCategory.JSON_PARSE,
                    "status_code": 200,
                    "error_contains": "Response is not valid JSON",
                },
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_http_error_handling(
        self,
        client_with_mocks,
        mock_http_client,
        method,
        http_method,
        error_setup,
        expected,
    ):
        """Test error handling patterns across GET and POST methods"""
        # Setup mock based on error_setup
        if "exception" in error_setup:
            getattr(mock_http_client, http_method).side_effect = error_setup[
                "exception"
            ]
        elif "http_error" in error_setup:
            mock_response = Mock()
            mock_response.status_code = error_setup["http_error"]
            getattr(mock_http_client, http_method).side_effect = httpx.HTTPStatusError(
                "Error", request=Mock(), response=mock_response
            )
        elif "json_error" in error_setup:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.side_effect = error_setup["json_error"]
            mock_response.raise_for_status.return_value = None
            getattr(mock_http_client, http_method).return_value = mock_response

        # Execute the method
        url = "https://test.gen3.io/test"
        kwargs = {"json": {"test": "data"}} if method == "post_json" else {}
        result = await getattr(client_with_mocks, method)(url, **kwargs)

        # Validate results
        assert isinstance(result, Response)
        assert not result.is_success
        assert result.error_category == expected["category"]
        assert result.status_code == expected["status_code"]
        assert any(expected["error_contains"] in error for error in result.errors)

    @pytest.mark.asyncio
    async def test_post_json_success(self, client_with_mocks, mock_http_client):
        """Test successful post_json request"""
        # Mock successful HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"test": "result"}}
        mock_response.raise_for_status.return_value = None

        mock_http_client.post = AsyncMock(return_value=mock_response)

        # Test the request
        result = await client_with_mocks.post_json(
            "https://test.gen3.io/graphql", json={"query": "{ test }"}
        )

        assert isinstance(result, Response)
        assert result.is_success
        assert result.status_code == 200
        assert result.data == {"data": {"test": "result"}}

    @pytest.mark.asyncio
    async def test_post_json_graphql_error_with_data(
        self, client_with_mocks, mock_http_client
    ):
        """Test post_json with GraphQL error that includes response data"""
        # Mock GraphQL error response with data
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "data": None,
            "errors": ["Cannot query field 'invalid' on type 'Subject'"],
        }

        mock_http_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Bad Request", request=Mock(), response=mock_response
            )
        )

        # Test the request
        result = await client_with_mocks.post_json(
            "https://test.gen3.io/graphql", json={"query": "{ invalid }"}
        )

        assert isinstance(result, Response)
        assert not result.is_success
        assert result.status_code == 400
        assert result.error_category == ErrorCategory.HTTP_CLIENT
        assert result.data is not None  # Should include GraphQL error details
        assert "errors" in result.data


class TestClientIntegration:
    """Integration tests for client with other components"""

    @pytest.mark.asyncio
    async def test_schema_manager_integration(self, schema_manager, test_schema):
        """Test that SchemaManager still works with new Response interface"""
        # This should work with the mocked Response from conftest.py
        full_schema = await schema_manager.get_schema_full()
        assert full_schema == test_schema

        # Extract should also work
        extract = await schema_manager.get_schema_extract()
        assert len(extract) > 0

    @pytest.mark.asyncio
    async def test_schema_manager_error_handling(self, mock_client):
        """Test error handling with new Response interface"""

        # Clear side_effect and set return_value for error response
        mock_client.get_json.side_effect = None
        mock_client.get_json.return_value = Response(
            success=False,
            error_category=ErrorCategory.NETWORK,
            errors=["Connection timeout"],
        )

        manager = SchemaManager(mock_client)

        with pytest.raises(Gen3SchemaError, match="Failed to fetch schema from Gen3"):
            await manager.get_schema_full()

    @pytest.mark.asyncio
    async def test_query_service_integration(self, mock_client):
        """Test that QueryService works with new Response interface"""
        from gen3_mcp.query import QueryService

        schema_manager = SchemaManager(mock_client)
        query_service = QueryService(schema_manager)

        # Test execute_graphql with success
        result = await query_service.execute_graphql("{ subject { id } }")

        # Should return the data portion of the mocked response
        assert "data" in result
        assert "subject" in result["data"]

    @pytest.mark.asyncio
    async def test_server_get_schema_summary(self):
        """Test the updated get_schema_summary function returns MCPResponse"""
        from gen3_mcp.models import MCPResponse
        from gen3_mcp.server import get_schema_summary

        # This will use the mocked client from conftest.py
        response = await get_schema_summary()

        assert isinstance(response, MCPResponse)
        assert response.status == "success"
        assert response.data is not None
        assert "schema_extract" in response.data
        assert "entity_count" in response.data
        assert "entity_names" in response.data
