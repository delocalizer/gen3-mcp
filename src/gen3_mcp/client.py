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
                    error_category=ErrorCategory.JSON_PARSE,
                    errors=[f"Response is not valid JSON: {e}"],
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
                error_category=category,
                errors=[f"HTTP {status_code} error"],
            )

        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as e:
            logger.error(f"Network error for GET {url}: {e}")
            return ClientResponse(
                success=False,
                error_category=ErrorCategory.NETWORK,
                errors=[f"Network error: {e}"],
            )

        except Exception as e:
            logger.error(f"GET {url} failed: {e}")
            return ClientResponse(
                success=False,
                error_category=ErrorCategory.OTHER,
                errors=[f"Unexpected error: {e}"],
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
                    error_category=ErrorCategory.JSON_PARSE,
                    errors=[f"Response is not valid JSON: {e}"],
                )

        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            logger.error(f"HTTP error for POST {url}: {status_code}")

            # Extract response data and errors
            response_data = None
            error_list = []

            try:
                response_data = e.response.json()

                # Extract errors from response if they exist (common in GraphQL responses)
                if isinstance(response_data, dict) and "errors" in response_data:
                    errors_field = response_data["errors"]
                    if isinstance(errors_field, list):
                        for error_item in errors_field:
                            if isinstance(error_item, str):
                                error_list.append(error_item)
                            elif (
                                isinstance(error_item, dict) and "message" in error_item
                            ):
                                error_list.append(error_item["message"])
                            else:
                                error_list.append(str(error_item))

            except ValueError:
                # Non-JSON response
                try:
                    response_data = {"raw_response": e.response.text}
                except:
                    response_data = {"error": "Could not parse error response"}

            # If no errors extracted, use the HTTP error as fallback
            if not error_list:
                error_list.append(f"HTTP {status_code} error")

            # Determine error category
            if 400 <= status_code < 500:
                category = ErrorCategory.HTTP_CLIENT
            elif 500 <= status_code < 600:
                category = ErrorCategory.HTTP_SERVER
            else:
                category = ErrorCategory.OTHER

            logger.debug(f"HTTP error response data: {response_data}")

            return ClientResponse(
                success=False,
                status_code=status_code,
                error_category=category,
                data=response_data,
                errors=error_list,
            )

        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as e:
            logger.error(f"Network error for POST {url}: {e}")
            return ClientResponse(
                success=False,
                error_category=ErrorCategory.NETWORK,
                errors=[f"Network error: {e}"],
            )

        except Exception as e:
            logger.error(f"POST {url} failed: {e}")
            return ClientResponse(
                success=False,
                error_category=ErrorCategory.OTHER,
                errors=[f"Unexpected error: {e}"],
            )


@cache
def get_client() -> Gen3Client:
    """Get a cached Gen3Client instance."""
    return Gen3Client(get_config())
