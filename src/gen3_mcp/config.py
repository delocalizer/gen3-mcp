"""Configuration management."""

from functools import cache

from pydantic import ConfigDict, Field, computed_field
from pydantic_settings import BaseSettings

from .consts import AUTH_URL_PATH, GRAPHQL_URL_PATH, SCHEMA_URL_PATH


class Config(BaseSettings):
    """Configuration with computed API endpoints."""

    model_config = ConfigDict(
        env_prefix="GEN3MCP_", case_sensitive=False, extra="ignore"
    )
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

    @computed_field
    @property
    def auth_url(self) -> str:
        """URL for fetching access tokens."""
        return f"{self.base_url}{AUTH_URL_PATH}"

    @computed_field
    @property
    def graphql_url(self) -> str:
        """URL for GraphQL queries."""
        return f"{self.base_url}{GRAPHQL_URL_PATH}"

    @computed_field
    @property
    def schema_url(self) -> str:
        """URL for full schema."""
        return f"{self.base_url}{SCHEMA_URL_PATH}"


@cache
def get_config() -> Config:
    """Get a cached Config instance."""
    return Config()
