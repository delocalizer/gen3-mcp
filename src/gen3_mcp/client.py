"""Gen3 client implementation"""

import logging
from typing import Any

import httpx

from .auth import AuthManager
from .config import Gen3Config
from .exceptions import Gen3ClientError

logger = logging.getLogger("gen3-mcp.client")

USER_AGENT: str = "gen3-mcp/1.0"


class Gen3Client:
    """Gen3 API client"""

    def __init__(self, config: Gen3Config):
        self.config = config
        self._http_client: httpx.AsyncClient | None = None
        self._auth_manager: AuthManager | None = None
        self._initialized = False

    async def __aenter__(self):
        await self._initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._cleanup()

    async def _initialize(self):
        """Initialize HTTP client and auth manager"""
        if self._initialized:
            return

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

    async def _cleanup(self):
        """Clean up resources"""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        self._auth_manager = None
        self._initialized = False
        logger.debug("Gen3 client cleaned up")

    async def get_json(
        self, url: str, authenticated: bool = True, **kwargs
    ) -> dict[str, Any] | None:
        """Get JSON from URL - URL should be complete, from config properties"""
        if not self._initialized:
            raise Gen3ClientError("Client not initialized - use async context manager")

        try:
            if authenticated:
                await self._auth_manager.ensure_valid_token()

            logger.debug(f"GET {url}")
            response = await self._http_client.get(url, **kwargs)
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error for GET {url}: {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"GET {url} failed: {e}")
            return None

    async def post_json(self, url: str, **kwargs) -> dict[str, Any] | None:
        """Post JSON to URL - URL should be complete, from config properties"""
        if not self._initialized:
            raise Gen3ClientError("Client not initialized - use async context manager")

        try:
            await self._auth_manager.ensure_valid_token()

            logger.debug(f"POST {url}")
            response = await self._http_client.post(url, **kwargs)
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error for POST {url}: {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"POST {url} failed: {e}")
            return None
