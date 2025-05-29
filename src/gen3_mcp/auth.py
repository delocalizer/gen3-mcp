"""Authentication management with token refresh."""

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx

from .config import Gen3Config
from .exceptions import Gen3ClientError

logger = logging.getLogger("gen3-mcp.auth")


@dataclass
class TokenInfo:
    """Container for access token and its metadata."""

    access_token: str
    expires_at: datetime
    refresh_threshold: datetime

    @classmethod
    def from_response(
        cls, token_data: dict, refresh_margin_seconds: int = 300
    ) -> "TokenInfo":
        """Create TokenInfo from API response.

        Args:
            token_data: Response from token endpoint containing access_token and expires_in.
            refresh_margin_seconds: Seconds before expiry to trigger refresh.

        Returns:
            TokenInfo instance with calculated expiry times.
        """
        expires_in = token_data.get("expires_in", 1800)  # Default 30 minutes
        issued_at = datetime.now(UTC)
        expires_at = issued_at + timedelta(seconds=expires_in)
        refresh_threshold = expires_at - timedelta(seconds=refresh_margin_seconds)

        return cls(
            access_token=token_data["access_token"],
            expires_at=expires_at,
            refresh_threshold=refresh_threshold,
        )

    def is_expired(self) -> bool:
        """Check if token is expired.

        Returns:
            True if token has expired, False otherwise.
        """
        return datetime.now(UTC) >= self.expires_at

    def needs_refresh(self) -> bool:
        """Check if token needs to be refreshed.

        Returns:
            True if token should be refreshed, False otherwise.
        """
        return datetime.now(UTC) >= self.refresh_threshold


class AuthManager:
    """Manages authentication tokens using config endpoints."""

    def __init__(self, config: Gen3Config, http_client: httpx.AsyncClient):
        """Initialize AuthManager.

        Args:
            config: Gen3Config instance with auth settings.
            http_client: Async HTTP client for API calls.
        """
        self.config = config
        self.http_client = http_client
        self.token_info: TokenInfo | None = None
        self.credentials: dict | None = None
        self._credentials_loaded = False
        self._lock = asyncio.Lock()  # Prevent concurrent token refreshes

    async def ensure_valid_token(self) -> None:
        """Ensure we have a valid token, refreshing if necessary.

        Raises:
            Gen3ClientError: If credentials cannot be loaded or token refresh fails.
        """
        async with self._lock:
            logger.debug("Checking token validity")

            if not self._credentials_loaded:
                await self._load_credentials()

            if not self.token_info or self.token_info.needs_refresh():
                logger.info("Token needs refresh")
                await self._refresh_token()

    async def _load_credentials(self) -> None:
        """Load credentials from file.

        Raises:
            Gen3ClientError: If credentials file not found or contains invalid JSON.
        """
        logger.debug(f"Loading credentials from {self.config.credentials_file}")

        try:
            credentials_path = os.path.expanduser(self.config.credentials_file)
            with open(credentials_path) as f:
                self.credentials = json.load(f)
            self._credentials_loaded = True
            logger.info("Credentials loaded successfully")
        except FileNotFoundError as e:
            logger.error(f"Credentials file not found: {self.config.credentials_file}")
            raise Gen3ClientError(
                f"Credentials file not found: {self.config.credentials_file}"
            ) from e
        except json.JSONDecodeError as e:
            logger.error(
                f"Invalid JSON in credentials file: {self.config.credentials_file}"
            )
            raise Gen3ClientError(
                f"Invalid JSON in credentials file: {self.config.credentials_file}"
            ) from e

    async def _refresh_token(self) -> None:
        """Refresh the access token using config.auth_url.

        Raises:
            Gen3ClientError: If no credentials available or token refresh fails.
        """
        if not self.credentials:
            logger.error("No credentials available for token refresh")
            raise Gen3ClientError("No credentials available")

        logger.debug(f"Refreshing token via {self.config.auth_url}")

        try:
            response = await self.http_client.post(
                self.config.auth_url, json=self.credentials
            )
            response.raise_for_status()
            token_data = response.json()

            self.token_info = TokenInfo.from_response(token_data)

            # Update client headers
            self.http_client.headers.update(
                {"Authorization": f"bearer {self.token_info.access_token}"}
            )

            logger.info("Token refreshed successfully")
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error during token refresh: {e.response.status_code}")
            raise Gen3ClientError(
                f"HTTP error during token refresh: {e.response.status_code}"
            ) from e
        except Exception as e:
            logger.error(f"Failed to refresh token: {e}")
            raise Gen3ClientError(f"Failed to refresh token: {e}") from e
