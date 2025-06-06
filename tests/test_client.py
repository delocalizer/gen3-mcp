"""Tests for Gen3Client and ClientResponse"""

from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from gen3_mcp.client import Gen3Client
from gen3_mcp.config import Config
from gen3_mcp.exceptions import Gen3SchemaError
from gen3_mcp.models import ClientResponse, ErrorCategory
from gen3_mcp.schema import SchemaManager


class TestClientResponse:
    """Test the ClientResponse model"""

    def test_success_response(self):
        """Test creating a successful response"""
        response = ClientResponse(success=True, status_code=200, data={"test": "data"})

        assert response.success
        assert response.status_code == 200
        assert response.data == {"test": "data"}
        assert response.error_category is None
        assert response.errors == []

    def test_error_response(self):
        """Test creating an error response"""
        response = ClientResponse(
            success=False,
            status_code=404,
            error_category=ErrorCategory.HTTP_CLIENT,
            errors=["Not found"],
        )

        assert not response.success
        assert response.status_code == 404
        assert response.error_category == ErrorCategory.HTTP_CLIENT
        assert response.errors == ["Not found"]
        assert response.data is None

    def test_error_categories(self):
        """Test all error categories are available"""
        categories = [
            ErrorCategory.NETWORK,
            ErrorCategory.HTTP_CLIENT,
            ErrorCategory.HTTP_SERVER,
            ErrorCategory.JSON_PARSE,
            ErrorCategory.OTHER,
        ]

        for category in categories:
            response = ClientResponse(
                success=False, error_category=category, errors=["Test error"]
            )
            assert response.error_category == category


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

        assert isinstance(result, ClientResponse)
        assert result.success
        assert result.status_code == 200
        assert result.data == {"test": "data"}
        assert result.errors == []

    @pytest.mark.asyncio
    async def test_get_json_http_error(self, client_with_mocks, mock_http_client):
        """Test get_json with HTTP error"""
        # Mock HTTP error response
        mock_response = Mock()
        mock_response.status_code = 404

        mock_http_client.get = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Not found", request=Mock(), response=mock_response
            )
        )

        # Test the request
        result = await client_with_mocks.get_json("https://test.gen3.io/schema")

        assert isinstance(result, ClientResponse)
        assert not result.success
        assert result.status_code == 404
        assert result.error_category == ErrorCategory.HTTP_CLIENT
        assert "HTTP 404 error" in result.errors[0]

    @pytest.mark.asyncio
    async def test_get_json_network_error(self, client_with_mocks, mock_http_client):
        """Test get_json with network error"""
        mock_http_client.get = AsyncMock(
            side_effect=httpx.ConnectError("Connection failed")
        )

        # Test the request
        result = await client_with_mocks.get_json("https://test.gen3.io/schema")

        assert isinstance(result, ClientResponse)
        assert not result.success
        assert result.status_code is None
        assert result.error_category == ErrorCategory.NETWORK
        assert "Network error" in result.errors[0]

    @pytest.mark.asyncio
    async def test_get_json_invalid_json(self, client_with_mocks, mock_http_client):
        """Test get_json with invalid JSON response"""
        # Mock response with invalid JSON
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.raise_for_status.return_value = None

        mock_http_client.get = AsyncMock(return_value=mock_response)

        # Test the request
        result = await client_with_mocks.get_json("https://test.gen3.io/schema")

        assert isinstance(result, ClientResponse)
        assert not result.success
        assert result.status_code == 200
        assert result.error_category == ErrorCategory.JSON_PARSE
        assert "Response is not valid JSON" in result.errors[0]

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

        assert isinstance(result, ClientResponse)
        assert result.success
        assert result.status_code == 200
        assert result.data == {"data": {"test": "result"}}

    @pytest.mark.asyncio
    async def test_post_json_graphql_error(self, client_with_mocks, mock_http_client):
        """Test post_json with GraphQL error (HTTP 400)"""
        # Mock GraphQL error response
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

        assert isinstance(result, ClientResponse)
        assert not result.success
        assert result.status_code == 400
        assert result.error_category == ErrorCategory.HTTP_CLIENT
        assert result.data is not None  # Should include GraphQL error details
        assert "errors" in result.data


class TestClientIntegration:
    """Integration tests for client with other components"""

    @pytest.mark.asyncio
    async def test_schema_manager_integration(self, schema_manager, test_schema):
        """Test that SchemaManager still works with new ClientResponse interface"""
        # This should work with the mocked ClientResponse from conftest.py
        full_schema = await schema_manager.get_schema_full()
        assert full_schema == test_schema

        # Extract should also work
        extract = await schema_manager.get_schema_extract()
        assert len(extract) > 0

    @pytest.mark.asyncio
    async def test_schema_manager_error_handling(self, mock_client):
        """Test error handling with new ClientResponse interface"""

        # Clear side_effect and set return_value for error response
        mock_client.get_json.side_effect = None
        mock_client.get_json.return_value = ClientResponse(
            success=False,
            error_category=ErrorCategory.NETWORK,
            errors=["Connection timeout"],
        )

        manager = SchemaManager(mock_client)

        with pytest.raises(Gen3SchemaError, match="Failed to fetch schema from Gen3"):
            await manager.get_schema_full()

    @pytest.mark.asyncio
    async def test_query_service_integration(self, mock_client):
        """Test that QueryService works with new ClientResponse interface"""
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
