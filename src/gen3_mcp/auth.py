"""Authentication management with token refresh."""

import json
import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from .config import Config
from .consts import DEFAULT_TOKEN_EXPIRY_SECONDS, TOKEN_REFRESH_BUFFER_MINUTES
from .exceptions import ClientError

logger = logging.getLogger("gen3-mcp.auth")


class AuthManager:
    """Manages authentication tokens using config endpoints."""

    def __init__(self, config: Config, http_client: httpx.AsyncClient):
        """Initialize AuthManager.

        Args:
            config: Config instance with auth settings.
            http_client: Async HTTP client for API calls.

        Raises:
            No exceptions raised during initialization.
        """
        self.config = config
        self.http_client = http_client
        self.token_expires_at: datetime | None = None

    async def ensure_valid_token(self) -> None:
        """Ensure we have a valid token, refreshing if necessary.

        Raises:
            ClientError: If credentials cannot be loaded or token refresh fails.
                Raised from the following underlying exceptions:
                - FileNotFoundError: Credentials file not found
                - json.JSONDecodeError: Invalid JSON in credentials file
                - httpx.HTTPStatusError: HTTP error during token request
                - KeyError: Missing access_token in response
                - Exception: Any other unexpected error during token refresh
        """
        # Check if we need a new token
        if self._needs_token():
            await self._get_new_token()

    def _needs_token(self) -> bool:
        """Check if we need to get a new token.

        Raises:
            No exceptions raised.
        """
        if self.token_expires_at is None:
            return True

        # Refresh 5 minutes before expiry
        refresh_time = self.token_expires_at - timedelta(
            minutes=TOKEN_REFRESH_BUFFER_MINUTES
        )
        return datetime.now(UTC) >= refresh_time

    async def _get_new_token(self) -> None:
        """Get a new access token.

        Raises:
            ClientError: If credentials cannot be loaded or token request fails.
                Raised from the following underlying exceptions:
                - FileNotFoundError: Credentials file not found (via _load_credentials)
                - json.JSONDecodeError: Invalid JSON in credentials file (via _load_credentials)
                - httpx.HTTPStatusError: HTTP error during token request
                - KeyError: Missing access_token in response
                - Exception: Any other unexpected error during token refresh
        """
        logger.debug("Getting new token")

        # Load credentials
        credentials = self._load_credentials()

        # Request token
        try:
            response = await self.http_client.post(
                self.config.auth_url, json=credentials
            )
            response.raise_for_status()
            token_data = response.json()

            # Extract token and calculate expiry
            access_token = token_data["access_token"]
            expires_in = token_data.get("expires_in", DEFAULT_TOKEN_EXPIRY_SECONDS)
            self.token_expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

            # Update client headers
            self.http_client.headers.update({"Authorization": f"bearer {access_token}"})

            logger.info("Token obtained successfully")

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error during token request: {e.response.status_code}")
            raise ClientError(
                f"HTTP error during token request: {e.response.status_code}",
                context={
                    "status_code": e.response.status_code,
                    "method": e.request.method,
                    "url": str(e.response.url),
                    "response_body": e.response.json(),
                },
            ) from e
        except KeyError as e:
            logger.error("Missing access_token in response")
            raise ClientError(
                "Missing access_token in response", errors=[f"Missing key: {e}"]
            ) from e
        except Exception as e:
            logger.error(f"Failed to get token: {e}")
            raise ClientError(f"Failed to get token: {e}", errors=[str(e)]) from e

    def _load_credentials(self) -> dict[str, Any]:
        """Load credentials from file.

        Returns:
            Credentials dictionary.

        Raises:
            ClientError: If credentials file not found or contains invalid JSON.
                Raised from the following underlying exceptions:
                - FileNotFoundError: Credentials file not found
                - json.JSONDecodeError: Invalid JSON in credentials file
        """
        logger.debug(f"Loading credentials from {self.config.credentials_file}")

        try:
            credentials_path = os.path.expanduser(self.config.credentials_file)
            with open(credentials_path) as f:
                credentials = json.load(f)
            logger.debug("Credentials loaded successfully")
            return credentials

        except FileNotFoundError as e:
            logger.error(f"Credentials file not found: {self.config.credentials_file}")
            raise ClientError(
                f"Credentials file not found: {self.config.credentials_file}"
            ) from e
        except json.JSONDecodeError as e:
            logger.error(
                f"Invalid JSON in credentials file: {self.config.credentials_file}"
            )
            raise ClientError(
                f"Invalid JSON in credentials file: {self.config.credentials_file}",
                errors=[f"JSON error: {e.msg} at line {e.lineno}, column {e.colno}"],
            ) from e
