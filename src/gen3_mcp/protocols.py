"""Protocol definitions for dependency injection and interface contracts."""

from typing import Protocol


class TokenProvider(Protocol):
    """Protocol for authentication token providers."""

    async def get_valid_token(self) -> str:
        """Get a valid authentication token.

        Returns:
            Valid bearer token string.

        Raises:
            ConfigError: If credentials cannot be loaded.
            Gen3MCPError: If token cannot be obtained.
        """
        ...
