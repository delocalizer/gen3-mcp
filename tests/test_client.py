"""Tests for Gen3Client and Response"""

from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from gen3_mcp.client import Gen3Client
from gen3_mcp.config import Config
from gen3_mcp.models import Response


class TestResponse:
    """Test the Response model"""

    @pytest.mark.parametrize(
        "test_case",
        [
            {
                "name": "success_response",
                "params": {
                    "status": "success",
                    "message": "Success",
                    "data": {"test": "data"},
                },
                "expected": {
                    "status": "success",
                    "message": "Success",
                    "errors": [],
                    "data": {"test": "data"},
                },
            },
            {
                "name": "error_response",
                "params": {
                    "status": "error",
                    "message": "Not found",
                    "errors": ["Not found"],
                },
                "expected": {
                    "status": "error",
                    "message": "Not found",
                    "errors": ["Not found"],
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
    """Test Gen3Client HTTP operations

    This class is the authoritative source for HTTP error handling tests.
    Service layers should focus on domain-specific error transformations.
    """

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

        assert result == {"test": "data"}

    @pytest.mark.parametrize(
        "method,http_method,error_setup,expected_exception",
        [
            # Network errors
            (
                "get_json",
                "get",
                {"exception": httpx.ConnectError("Connection failed")},
                httpx.ConnectError,
            ),
            (
                "post_json",
                "post",
                {"exception": httpx.ConnectError("Connection failed")},
                httpx.ConnectError,
            ),
            # HTTP client errors
            (
                "get_json",
                "get",
                {"http_error": 404},
                httpx.HTTPStatusError,
            ),
            (
                "post_json",
                "post",
                {"http_error": 400},
                httpx.HTTPStatusError,
            ),
            # HTTP server errors
            (
                "get_json",
                "get",
                {"http_error": 500},
                httpx.HTTPStatusError,
            ),
            (
                "post_json",
                "post",
                {"http_error": 500},
                httpx.HTTPStatusError,
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
        expected_exception,
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

        # Execute the method
        url = "https://test.gen3.io/test"
        kwargs = {"json": {"test": "data"}} if method == "post_json" else {}

        # Client methods raise exceptions
        with pytest.raises(expected_exception):
            await getattr(client_with_mocks, method)(url, **kwargs)

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

        assert result == {"data": {"test": "result"}}

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

        # Test the request - should raise HTTPStatusError
        with pytest.raises(httpx.HTTPStatusError):
            await client_with_mocks.post_json(
                "https://test.gen3.io/graphql", json={"query": "{ invalid }"}
            )


class TestClientIntegration:
    """Integration tests for client with other components"""

    @pytest.mark.asyncio
    async def test_server_response_from_error(self):
        """Test that Response.from_error works with various exception types"""
        # Test with httpx.HTTPStatusError
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.url = "https://test.example.com"
        http_error = httpx.HTTPStatusError(
            "Not found", request=Mock(), response=mock_response
        )

        response = Response.from_error(http_error)
        assert response.status == "error"
        assert "404" in response.message
        assert response.metadata["status_code"] == 404

        # Test with httpx.ConnectError
        mock_request = Mock()
        mock_request.url = "https://test.example.com"
        network_error = httpx.ConnectError("Connection failed", request=mock_request)
        response = Response.from_error(network_error)
        assert response.status == "error"
        assert "Network error" in response.message
        assert "Check your internet connection" in response.suggestions
