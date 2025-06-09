"""Gen3 MCP Server Package

A Model Context Protocol (MCP) server for interacting with Gen3 data commons,
with GraphQL query validation to reduce field name hallucinations.
"""

from .client import Gen3Client, get_client
from .config import Config, get_config
from .consts import PACKAGE_VERSION
from .exceptions import (
    ConfigError,
    Gen3MCPError,
    GraphQLError,
    NoSuchEntityError,
    ParseError,
)
from .query import QueryService, get_query_service
from .schema import SchemaManager, get_schema_manager

__version__ = PACKAGE_VERSION

__all__ = [
    "__version__",
    "get_config",
    "get_client",
    "get_schema_manager",
    "get_query_service",
    "Config",
    "Gen3Client",
    "SchemaManager",
    "QueryService",
    "Gen3MCPError",
    "ParseError",
    "ConfigError",
    "NoSuchEntityError",
    "GraphQLError",
]
