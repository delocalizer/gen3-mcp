"""Gen3 client — handles low-level API calls."""

import logging
from typing import Any

import httpx

from .auth import AuthManager
from .config import Gen3Config
from .exceptions import Gen3ClientError

logger = logging.getLogger("gen3-mcp.client")

USER_AGENT = "gen3-mcp/1.0"


class Gen3Client:
    """Gen3 API client."""

    def __init__(self, config: Gen3Config):
        """Initialize Gen3Client.

        Args:
            config: Gen3Config instance with API settings.
        """
        self.config = config
        self._http_client: httpx.AsyncClient | None = None
        self._auth_manager: AuthManager | None = None
        self._initialized = False

    async def __aenter__(self):
        """Async context manager entry.

        Returns:
            Self after initialization.
        """
        await self._initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self._cleanup()

    async def get_json(
        self, url: str, authenticated: bool = True, **kwargs
    ) -> dict[str, Any] | None:
        """Get JSON from URL.

        Args:
            url: Complete URL to fetch (should be from config properties).
            authenticated: Whether to include authentication token.
            **kwargs: Additional arguments passed to httpx.get.

        Returns:
            JSON response as dict or None if request fails.

        Raises:
            Gen3ClientError: If client not initialized.
        """
        if not self._initialized:
            raise Gen3ClientError("Client not initialized - use async context manager")

        try:
            if authenticated:
                await self._auth_manager.ensure_valid_token()

            logger.debug(f"GET {url}")
            response = await self._http_client.get(url, **kwargs)
            response.raise_for_status()

            result = response.json()
            logger.debug(f"GET {url} successful")
            return result
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error for GET {url}: {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"GET {url} failed: {e}")
            return None

    async def post_json(self, url: str, **kwargs) -> dict[str, Any] | None:
        """Post JSON to URL.

        Args:
            url: Complete URL to post to (should be from config properties).
            **kwargs: Additional arguments passed to httpx.post.

        Returns:
            JSON response as dict or None if request fails.

        Raises:
            Gen3ClientError: If client not initialized.
        """
        if not self._initialized:
            raise Gen3ClientError("Client not initialized - use async context manager")

        try:
            await self._auth_manager.ensure_valid_token()

            logger.debug(f"POST {url}")
            response = await self._http_client.post(url, **kwargs)
            response.raise_for_status()

            result = response.json()
            logger.debug(f"POST {url} successful")
            return result
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error for POST {url}: {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"POST {url} failed: {e}")
            return None

    async def _initialize(self) -> None:
        """Initialize HTTP client and auth manager.

        Raises:
            Gen3ClientError: If initialization fails.
        """
        if self._initialized:
            logger.debug("Client already initialized")
            return

        logger.debug("Initializing Gen3 client")

        self._http_client = httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            timeout=self.config.timeout_seconds,
            follow_redirects=True,
        )

        self._auth_manager = AuthManager(self.config, self._http_client)

        # Get initial token
        await self._auth_manager.ensure_valid_token()
        self._initialized = True

        logger.info(f"Gen3 client initialized for {self.config.base_url}")

    async def _cleanup(self) -> None:
        """Clean up resources."""
        logger.debug("Cleaning up Gen3 client")

        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

        self._auth_manager = None
        self._initialized = False

        logger.debug("Gen3 client cleaned up")
