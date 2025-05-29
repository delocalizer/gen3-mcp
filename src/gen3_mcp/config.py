"""Configuration management and logging setup."""

import logging

from pydantic import ConfigDict, Field, computed_field
from pydantic_settings import BaseSettings


class Gen3Config(BaseSettings):
    """Configuration with computed API endpoints."""

    model_config = ConfigDict(env_prefix="GEN3_", case_sensitive=False, extra="ignore")

    base_url: str = Field(
        default="https://gen3.datacommons.io",
        description="Base URL for the Gen3 data commons",
    )
    credentials_file: str = Field(
        default="~/credentials.json", description="Path to the credentials JSON file"
    )
    log_level: str = Field(
        default="INFO",
        pattern=r"^(DEBUG|INFO|WARNING|ERROR)$",
        description="Logging level",
    )
    timeout_seconds: int = Field(
        default=30, gt=0, le=300, description="HTTP request timeout in seconds"
    )
    schema_cache_ttl: int = Field(
        default=3600, ge=60, description="Schema cache TTL in seconds"
    )

    @computed_field
    @property
    def auth_url(self) -> str:
        """URL for fetching access tokens."""
        return f"{self.base_url}/user/credentials/cdis/access_token"

    @computed_field
    @property
    def graphql_url(self) -> str:
        """URL for GraphQL queries."""
        return f"{self.base_url}/api/v0/submission/graphql"

    @computed_field
    @property
    def schema_url(self) -> str:
        """URL for schema dictionary."""
        return f"{self.base_url}/api/v0/submission/_dictionary/_all"

    def __repr__(self) -> str:
        """String representation of the configuration."""
        return f"Gen3Config(base_url='{self.base_url}', log_level='{self.log_level}')"


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Configure logging for the entire application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR).

    Returns:
        Logger instance for gen3-mcp.
    """
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Only configure if not already configured to avoid conflicts
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=numeric_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
    else:
        # Just set the level if logging is already configured
        logging.getLogger().setLevel(numeric_level)

    logger = logging.getLogger("gen3-mcp")
    logger.debug(f"Logging configured with level: {log_level}")
    return logger
