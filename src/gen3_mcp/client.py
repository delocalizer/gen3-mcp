"""Gen3 client — handles low-level API calls."""

import logging
from functools import cache
from typing import Any

import httpx

from .auth import AuthManager
from .config import Config, get_config
from .consts import USER_AGENT
from .exceptions import ClientError

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

    async def get_json(self, url: str, authenticated: bool = True, **kwargs) -> Any:
        """Get JSON from URL.

        Args:
            url: Complete URL to fetch (should be from config properties).
            authenticated: Whether to include authentication token.
            **kwargs: Additional arguments passed to httpx.get.

        Returns:
            Parsed JSON data.

        Raises:
            ClientError: For all HTTP, network, and JSON parsing errors.
                Raised from the following underlying exceptions:
                - httpx.HTTPStatusError: HTTP 4xx/5xx responses
                - httpx.RequestError (Network error, timeouts etc)
                - ValueError: JSON parsing errors from response.json()
                - Exception: Any other unexpected errors
        """
        try:
            if authenticated:
                await self._auth_manager.ensure_valid_token()

            logger.debug(f"GET {url}")
            response = await self._http_client.get(url, **kwargs)
            response.raise_for_status()
            data = response.json()
            logger.debug(f"GET {url} successful")
            return data

        # e.g. from failed ensure_valid_token
        except ClientError:
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error for GET {url}: {e.response.status_code}")
            raise ClientError(
                f"HTTP request failed with status {e.response.status_code}",
                context={
                    "status_code": e.response.status_code,
                    "method": e.request.method,
                    "url": str(e.response.url),
                    "response_body": e.response.json(),
                },
            ) from e
        except Exception as e:
            logger.error(f"GET {url} failed: {e}")
            raise ClientError(f"GET {url} failed: {e}", errors=[str(e)]) from e

    async def post_json(self, url: str, **kwargs) -> Any:
        """Post JSON to URL.

        Args:
            url: Complete URL to post to (should be from config properties).
            **kwargs: Additional arguments passed to httpx.post.

        Returns:
            Parsed JSON response data.

        Raises:
            ClientError: For all HTTP, network, and JSON parsing errors.
                Raised from the following underlying exceptions:
                - httpx.HTTPStatusError: HTTP 4xx/5xx responses
                - httpx.RequestError (Network error, timeouts etc)
                - ValueError: JSON parsing errors from response.json()
                - Exception: Any other unexpected errors
        """
        try:
            await self._auth_manager.ensure_valid_token()

            logger.debug(f"POST {url}")
            response = await self._http_client.post(url, **kwargs)
            response.raise_for_status()
            data = response.json()
            logger.debug(f"POST {url} successful")
            return data

        # e.g. from failed ensure_valid_token
        except ClientError:
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error for POST {url}: {e.response.status_code}")
            raise ClientError(
                f"HTTP request failed with status {e.response.status_code}",
                context={
                    "status_code": e.response.status_code,
                    "method": e.request.method,
                    "url": str(e.response.url),
                    "response_body": e.response.json(),
                },
            ) from e
        except Exception as e:
            logger.error(f"POST {url} failed: {e}")
            raise ClientError(f"POST {url} failed: {e}", errors=[str(e)]) from e


@cache
def get_client() -> Gen3Client:
    """Get a cached Gen3Client instance.

    Raises:
        No exceptions raised directly.
        May propagate exceptions from Config() initialization via get_config().
    """
    return Gen3Client(get_config())
