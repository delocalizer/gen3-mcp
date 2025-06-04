"""Gen3 client — handles low-level API calls."""

import logging
from functools import lru_cache
from typing import Any

import httpx

from .auth import AuthManager
from .config import Config, get_config

logger = logging.getLogger("gen3-mcp.client")

USER_AGENT = "gen3-mcp/1.0"


class Gen3Client:
    """Gen3 API client."""

    def __init__(self, config: Config):
        """Initialize Gen3Client.

        Args:
            config: Config instance with API settings.
        """
        self.config = config
        self._http_client: httpx.AsyncClient | None = None
        self._auth_manager: AuthManager | None = None
        self._initialized = False

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
        """
        await self._ensure_initialized()

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
            JSON response as dict. For HTTP errors, the 'errors' key will
            contain detailed errors from the response content (if any), and
            '_http_error_context' will describe the HTTP error context e.g.
            status_code. Returns None only for network/connection errors.
        """
        await self._ensure_initialized()

        try:
            await self._auth_manager.ensure_valid_token()

            logger.debug(f"POST {url}")
            response = await self._http_client.post(url, **kwargs)
            response.raise_for_status()

            result = response.json()
            logger.debug(f"POST {url} successful")
            return result
        except httpx.HTTPStatusError as e:
            status_code = httpx.codes(e.response.status_code)
            logger.error(f"HTTP error for POST {url}: {repr(status_code)}")

            # Try to extract response content (may contain GraphQL errors)
            response_content = {}
            try:
                response_content = e.response.json()
                # At the graphql endpoint, an example of this:
                # {'data': None, 'errors': ['Cannot query field "demographic" on type "subject".']}
            except ValueError:
                pass
            if "errors" not in response_content:
                response_content["errors"] = [f"HTTP {repr(status_code)} error"]

            # Add HTTP error context to the response content
            response_content["_http_error_context"] = {
                "status_code": status_code.value,
                "error_category": status_code.name,
                "is_client_error": httpx.codes.is_client_error(status_code),
                "is_server_error": httpx.codes.is_server_error(status_code),
            }

            logger.debug(
                f"HTTP error response includes: {list(response_content.keys())}"
            )
            return response_content

        except Exception as e:
            logger.error(f"POST {url} failed: {e}")
            return None

    async def _ensure_initialized(self) -> None:
        """Ensure the client is initialized before making requests."""
        if self._initialized:
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


@lru_cache
def get_client() -> Gen3Client:
    """Get a cached Gen3Client instance.

    Returns:
        Gen3Client instance that will auto-initialize on first use.
    """
    return Gen3Client(get_config())
