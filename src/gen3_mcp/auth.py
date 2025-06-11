"""Authentication management with token refresh."""

import json
import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from .config import Config
from .consts import DEFAULT_TOKEN_EXPIRY_SECONDS, TOKEN_REFRESH_BUFFER_MINUTES
from .exceptions import ConfigError, Gen3MCPError

logger = logging.getLogger("gen3-mcp.auth")


class AuthManager:
    """Authentication token manager.

    Responsibilities:
    - Manage token lifecycle (refresh, expiry)
    - Load credentials from config
    - Request new tokens from auth server
    """

    def __init__(self, config: Config, http_client: httpx.AsyncClient):
        """Initialize AuthManager.

        Args:
            config: Config instance with auth settings.
            http_client: HTTP client (for token requests only)
        """
        self.config = config
        self.http_client = http_client
        self._access_token: str | None = None
        self._token_expires_at: datetime | None = None

    async def get_valid_token(self) -> str:
        """Get a valid authentication token.

        Returns:
            Valid bearer token string.

        Raises:
            ConfigError: If credentials cannot be loaded.
            Gen3MCPError: If token cannot be obtained.
        """
        if self._needs_refresh():
            await self._refresh_token()

        if not self._access_token:
            raise Gen3MCPError("No valid token available")

        return self._access_token

    def _needs_refresh(self) -> bool:
        """Check if token needs refresh."""
        if self._token_expires_at is None or self._access_token is None:
            return True

        refresh_time = self._token_expires_at - timedelta(
            minutes=TOKEN_REFRESH_BUFFER_MINUTES
        )
        return datetime.now(UTC) >= refresh_time

    async def _refresh_token(self) -> None:
        """Refresh the access token."""
        logger.debug("Refreshing authentication token")

        credentials = self._load_credentials()

        try:
            response = await self.http_client.post(
                self.config.auth_url, json=credentials
            )
            response.raise_for_status()
            token_data = response.json()

            self._access_token = token_data["access_token"]
            expires_in = token_data.get("expires_in", DEFAULT_TOKEN_EXPIRY_SECONDS)
            self._token_expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

            logger.info("Token refreshed successfully")

        except KeyError as e:
            logger.error("Missing access_token in response")
            raise Gen3MCPError(
                "Auth server returned response without access_token",
                errors=[f"Missing required field: {e}"],
                suggestions=[
                    "This may indicate an auth server bug or API change",
                    "Contact system administrator",
                ],
                context={"auth_url": self.config.auth_url},
            ) from e

    def _load_credentials(self) -> dict[str, Any]:
        """Load credentials from config file."""
        logger.debug(f"Loading credentials from {self.config.credentials_file}")

        try:
            credentials_path = os.path.expanduser(self.config.credentials_file)
            with open(credentials_path) as f:
                credentials = json.load(f)
            return credentials

        except (FileNotFoundError, PermissionError) as e:
            raise ConfigError(
                f"Credentials file not found: {self.config.credentials_file}",
                suggestions=[
                    f"Create credentials file at {self.config.credentials_file}",
                    "Check file permissions",
                ],
                context={"credentials_path": self.config.credentials_file},
            ) from e
        except json.JSONDecodeError as e:
            raise ConfigError(
                f"Invalid JSON in credentials file: {self.config.credentials_file}",
                errors=[f"JSON error: {e.msg}"],
                suggestions=["Fix JSON syntax in credentials file"],
                context={"credentials_path": self.config.credentials_file},
            ) from e
