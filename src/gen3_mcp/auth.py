"""Authentication management with token refresh"""

import json
import os
import asyncio
from datetime import datetime, timedelta, UTC
from dataclasses import dataclass
from typing import Optional
import httpx
from .config import Gen3Config
from .exceptions import Gen3ClientError


@dataclass
class TokenInfo:
    """Container for access token and its metadata"""

    access_token: str
    expires_at: datetime
    refresh_threshold: datetime

    @classmethod
    def from_response(
        cls, token_data: dict, refresh_margin_seconds: int = 300
    ) -> "TokenInfo":
        """Create TokenInfo from API response"""
        expires_in = token_data.get("expires_in", 1800)  # Default 30 minutes
        issued_at = datetime.now(UTC)
        expires_at = issued_at + timedelta(seconds=expires_in)
        refresh_threshold = expires_at - timedelta(seconds=refresh_margin_seconds)

        return cls(
            access_token=token_data["access_token"],
            expires_at=expires_at,
            refresh_threshold=refresh_threshold,
        )

    def needs_refresh(self) -> bool:
        """Check if token needs to be refreshed"""
        return datetime.now(UTC) >= self.refresh_threshold

    def is_expired(self) -> bool:
        """Check if token is expired"""
        return datetime.now(UTC) >= self.expires_at


class AuthManager:
    """Manages authentication tokens using config endpoints"""

    def __init__(self, config: Gen3Config, http_client: httpx.AsyncClient):
        self.config = config
        self.http_client = http_client
        self.token_info: Optional[TokenInfo] = None
        self.credentials: Optional[dict] = None
        self._credentials_loaded = False
        self._lock = asyncio.Lock()  # Prevent concurrent token refreshes

    async def ensure_valid_token(self):
        """Ensure we have a valid token, refreshing if necessary"""
        async with self._lock:  # Prevent concurrent refreshes
            if not self._credentials_loaded:
                await self._load_credentials()

            if not self.token_info or self.token_info.needs_refresh():
                await self._refresh_token()
            elif self.token_info.is_expired():
                await self._refresh_token()

    async def _load_credentials(self):
        """Load credentials from file"""
        try:
            credentials_path = os.path.expanduser(self.config.credentials_file)
            with open(credentials_path) as f:
                self.credentials = json.load(f)
            self._credentials_loaded = True
        except FileNotFoundError:
            raise Gen3ClientError(
                f"Credentials file not found: {self.config.credentials_file}"
            )
        except json.JSONDecodeError:
            raise Gen3ClientError(
                f"Invalid JSON in credentials file: {self.config.credentials_file}"
            )

    async def _refresh_token(self):
        """Refresh the access token using config.auth_url"""
        if not self.credentials:
            raise Gen3ClientError("No credentials available")

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

        except httpx.HTTPStatusError as e:
            raise Gen3ClientError(
                f"HTTP error during token refresh: {e.response.status_code}"
            )
        except Exception as e:
            raise Gen3ClientError(f"Failed to refresh token: {e}")
