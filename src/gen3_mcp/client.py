"""Gen3 client — handles low-level API calls."""

import logging
from functools import cache
from typing import Any

import httpx

from .auth import AuthManager
from .config import Config, get_config
from .consts import USER_AGENT

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
            ConfigError: From auth if there is a config issue.
            Gen3MCPError: From auth if server response format unexpected.
            httpx.HTTPStatusError: For HTTP 4xx/5xx responses.
            httpx.RequestError: For network errors, timeouts, DNS failures.
        """
        if authenticated:
            await self._auth_manager.ensure_valid_token()

        logger.debug(f"GET {url}")
        response = await self._http_client.get(url, **kwargs)
        response.raise_for_status()
        logger.debug(f"GET {url} successful")
        return response.json()

    async def post_json(self, url: str, **kwargs) -> Any:
        """Post JSON to URL.

        Args:
            url: Complete URL to post to (should be from config properties).
            **kwargs: Additional arguments passed to httpx.post.

        Returns:
            Parsed JSON response data.

        Raises:
            ConfigError: From auth if there is a config issue.
            Gen3MCPError: From auth if server response format unexpected.
            httpx.HTTPStatusError: For HTTP 4xx/5xx responses.
            httpx.RequestError: For network errors, timeouts, DNS failures.
        """
        await self._auth_manager.ensure_valid_token()

        logger.debug(f"POST {url}")
        response = await self._http_client.post(url, **kwargs)
        response.raise_for_status()
        logger.debug(f"POST {url} successful")
        return response.json()


@cache
def get_client() -> Gen3Client:
    """Get a cached Gen3Client instance.

    Raises:
        No exceptions raised directly.
        May propagate exceptions from Config() initialization via get_config().
    """
    return Gen3Client(get_config())
