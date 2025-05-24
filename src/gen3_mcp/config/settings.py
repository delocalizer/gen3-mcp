"""Configuration management with Pydantic v2"""

import os
from typing import Optional
from pydantic import Field, computed_field, ConfigDict
from pydantic_settings import BaseSettings


class Gen3Config(BaseSettings):
    """Type-safe configuration with pre-computed endpoints"""

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

    # HTTP settings
    timeout_seconds: int = Field(
        default=30, gt=0, le=300, description="HTTP request timeout in seconds"
    )
    max_retries: int = Field(
        default=3, ge=0, le=10, description="Maximum number of HTTP retries"
    )

    # Cache settings
    schema_cache_ttl: int = Field(
        default=300, ge=60, le=3600, description="Schema cache TTL in seconds"
    )
    max_cache_size: int = Field(
        default=100, ge=10, le=1000, description="Maximum number of items in cache"
    )

    # Pre-computed endpoint properties (maintaining the original elegant approach)
    @computed_field
    @property
    def auth_url(self) -> str:
        """URL for fetching access tokens"""
        return f"{self.base_url}/user/credentials/cdis/access_token"

    @computed_field
    @property
    def graphql_url(self) -> str:
        """URL for GraphQL queries"""
        return f"{self.base_url}/api/v0/submission/graphql"

    @computed_field
    @property
    def schema_base_url(self) -> str:
        """URL for schema dictionary"""
        return f"{self.base_url}/api/v0/submission/_dictionary"

    @computed_field
    @property
    def schema_url(self) -> str:
        """URL for complete schema dictionary"""
        return f"{self.schema_base_url}/_all"

    def entity_schema_url(self, entity_name: str) -> str:
        """URL for specific entity schema"""
        return f"{self.schema_base_url}/{entity_name}"

    def __repr__(self) -> str:
        """String representation of the configuration"""
        return f"Gen3Config(base_url='{self.base_url}', log_level='{self.log_level}')"
