"""Gen3 client — handles low-level API calls."""

import logging
from functools import cache

import httpx

from .auth import AuthManager
from .config import Config, get_config
from .consts import USER_AGENT
from .models import ClientResponse, ErrorCategory

logger = logging.getLogger("gen3-mcp.client")


class Gen3Client:
    """Gen3 API client."""

    def __init__(self, config: Config):
        """Initialize Gen3Client.

        Args:
            config: Config instance with API settings.
        """
        self.config = config
        self._http_client = httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            timeout=config.timeout_seconds,
            follow_redirects=True,
        )
        self._auth_manager = AuthManager(config, self._http_client)

        logger.info(f"Gen3 client created for {config.base_url}")

    async def get_json(
        self, url: str, authenticated: bool = True, **kwargs
    ) -> ClientResponse:
        """Get JSON from URL.

        Args:
            url: Complete URL to fetch (should be from config properties).
            authenticated: Whether to include authentication token.
            **kwargs: Additional arguments passed to httpx.get.

        Returns:
            ClientResponse with success/error details and data.
        """
        try:
            if authenticated:
                await self._auth_manager.ensure_valid_token()

            logger.debug(f"GET {url}")
            response = await self._http_client.get(url, **kwargs)
            response.raise_for_status()

            try:
                data = response.json()
                logger.debug(f"GET {url} successful")
                return ClientResponse(
                    success=True, status_code=response.status_code, data=data
                )
            except ValueError as e:
                logger.error(f"JSON parse error for GET {url}: {e}")
                return ClientResponse(
                    success=False,
                    status_code=response.status_code,
                    error_message=f"Response is not valid JSON: {e}",
                    error_category=ErrorCategory.JSON_PARSE,
                )

        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            logger.error(f"HTTP error for GET {url}: {status_code}")

            # Determine error category
            if 400 <= status_code < 500:
                category = ErrorCategory.HTTP_CLIENT
            elif 500 <= status_code < 600:
                category = ErrorCategory.HTTP_SERVER
            else:
                category = ErrorCategory.OTHER

            return ClientResponse(
                success=False,
                status_code=status_code,
                error_message=f"HTTP {status_code} error",
                error_category=category,
            )

        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as e:
            logger.error(f"Network error for GET {url}: {e}")
            return ClientResponse(
                success=False,
                error_message=f"Network error: {e}",
                error_category=ErrorCategory.NETWORK,
            )

        except Exception as e:
            logger.error(f"GET {url} failed: {e}")
            return ClientResponse(
                success=False,
                error_message=f"Unexpected error: {e}",
                error_category=ErrorCategory.OTHER,
            )

    async def post_json(self, url: str, **kwargs) -> ClientResponse:
        """Post JSON to URL.

        Args:
            url: Complete URL to post to (should be from config properties).
            **kwargs: Additional arguments passed to httpx.post.

        Returns:
            ClientResponse with success/error details and data. For successful
            requests, data contains the JSON response. For HTTP errors, data
            may contain server response details (like GraphQL errors).
        """
        try:
            await self._auth_manager.ensure_valid_token()

            logger.debug(f"POST {url}")
            response = await self._http_client.post(url, **kwargs)
            response.raise_for_status()

            try:
                data = response.json()
                logger.debug(f"POST {url} successful")
                return ClientResponse(
                    success=True, status_code=response.status_code, data=data
                )
            except ValueError as e:
                logger.error(f"JSON parse error for POST {url}: {e}")
                return ClientResponse(
                    success=False,
                    status_code=response.status_code,
                    error_message=f"Response is not valid JSON: {e}",
                    error_category=ErrorCategory.JSON_PARSE,
                )

        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            logger.error(f"HTTP error for POST {url}: {status_code}")

            # Try to extract response content (may contain GraphQL errors)
            response_data = None
            try:
                response_data = e.response.json()
                # Example GraphQL error response:
                # {
                #   'data': None,
                #   'errors': [
                #     'Cannot query field "demographic" on type "subject".'
                #   ]
                # }
            except ValueError:
                # If we can't parse JSON, include raw text if available
                try:
                    response_data = {"raw_response": e.response.text}
                except:
                    response_data = {"error": "Could not parse error response"}

            # Determine error category
            if 400 <= status_code < 500:
                category = ErrorCategory.HTTP_CLIENT
            elif 500 <= status_code < 600:
                category = ErrorCategory.HTTP_SERVER
            else:
                category = ErrorCategory.OTHER

            logger.debug(f"HTTP error response data: {response_data}")

            # Return error response but include the server's response data
            # This preserves GraphQL error details while providing consistent interface
            return ClientResponse(
                success=False,
                status_code=status_code,
                error_message=f"HTTP {status_code} error",
                error_category=category,
                data=response_data,
            )

        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as e:
            logger.error(f"Network error for POST {url}: {e}")
            return ClientResponse(
                success=False,
                error_message=f"Network error: {e}",
                error_category=ErrorCategory.NETWORK,
            )

        except Exception as e:
            logger.error(f"POST {url} failed: {e}")
            return ClientResponse(
                success=False,
                error_message=f"Unexpected error: {e}",
                error_category=ErrorCategory.OTHER,
            )


@cache
def get_client() -> Gen3Client:
    """Get a cached Gen3Client instance."""
    return Gen3Client(get_config())
