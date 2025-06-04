"""Configuration management."""

from functools import lru_cache
from pydantic import ConfigDict, Field, computed_field
from pydantic_settings import BaseSettings


class Config(BaseSettings):
    """Configuration with computed API endpoints."""

    model_config = ConfigDict(env_prefix="GEN3MCP_", case_sensitive=False, extra="ignore")

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
        """URL for full schema."""
        return f"{self.base_url}/api/v0/submission/_dictionary/_all"


@lru_cache
def get_config():
    return Config()
