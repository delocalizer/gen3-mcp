"""Gen3 client — handles low-level API calls."""

import logging
from functools import cache
from typing import Any

import httpx

from .auth import AuthManager
from .config import Config, get_config
from .consts import USER_AGENT
from .protocols import TokenProvider

logger = logging.getLogger("gen3-mcp.client")


class Gen3Client:
    """Gen3 API client with authentication.

    Responsibilities:
    - Provide high-level HTTP API methods
    - Handle HTTP errors and responses
    """

    def __init__(
        self,
        config: Config | None = None,
        token_provider: TokenProvider | None = None,
        http_client: httpx.AsyncClient | None = None,
    ):
        """Initialize Gen3Client.

        Args:
            config: Config instance. If None, uses get_config().
            token_provider: Authentication token provider. If None, creates AuthManager.
            http_client: HTTP client. If None, creates a new one.
        """
        self.config = config or get_config()

        self.http_client = http_client or httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            timeout=self.config.timeout_seconds,
            follow_redirects=True,
        )

        self.token_provider = token_provider or AuthManager(
            self.config, self.http_client
        )

        logger.info(f"Gen3 client created for {self.config.base_url}")

    async def get_json(self, url: str, **kwargs) -> Any:
        """Get JSON from URL with authentication.

        Args:
            url: Complete URL to fetch.
            **kwargs: Additional arguments for httpx.get.

        Returns:
            Parsed JSON data.

        Raises:
            ConfigError: From auth if there is a config issue.
            Gen3MCPError: From auth if server response format unexpected.
            httpx.HTTPStatusError: For HTTP 4xx/5xx responses.
            httpx.RequestError: For network errors, timeouts, DNS failures.
        """
        headers = kwargs.pop("headers", {})

        token = await self.token_provider.get_valid_token()
        headers["Authorization"] = f"bearer {token}"

        logger.debug(f"GET {url}")
        response = await self.http_client.get(url, headers=headers, **kwargs)
        response.raise_for_status()
        logger.debug(f"GET {url} successful")
        return response.json()

    async def post_json(self, url: str, **kwargs) -> Any:
        """Post JSON to URL with authentication.

        Args:
            url: Complete URL to post to.
            **kwargs: Additional arguments for httpx.post.

        Returns:
            Parsed JSON response data.

        Raises:
            ConfigError: From auth if there is a config issue.
            Gen3MCPError: From auth if server response format unexpected.
            httpx.HTTPStatusError: For HTTP 4xx/5xx responses.
            httpx.RequestError: For network errors, timeouts, DNS failures.
        """
        headers = kwargs.pop("headers", {})
        token = await self.token_provider.get_valid_token()
        headers["Authorization"] = f"bearer {token}"

        logger.debug(f"POST {url}")
        response = await self.http_client.post(url, headers=headers, **kwargs)
        response.raise_for_status()
        logger.debug(f"POST {url} successful")
        return response.json()


@cache
def get_client() -> Gen3Client:
    """Get a cached Gen3Client instance with default configuration.

    Raises:
        No exceptions raised directly.
        May propagate exceptions from Config() initialization via get_config().
    """
    return Gen3Client()
