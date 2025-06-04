"""Gen3 MCP Server Package

A Model Context Protocol (MCP) server for interacting with Gen3 data commons,
with GraphQL query validation to reduce field name hallucinations.
"""

from .client import Gen3Client, get_client
from .config import Config, get_config
from .exceptions import (
    Gen3ClientError,
    Gen3MCPError,
    Gen3SchemaError,
)
from .query import QueryService
from .schema import SchemaService

__version__ = "1.2.0"

__all__ = [
    "__version__",
    "get_config",
    "get_client",
    "Config",
    "Gen3Client",
    "SchemaService",
    "QueryService",
    "Gen3MCPError",
    "Gen3ClientError",
    "Gen3SchemaError",
]
