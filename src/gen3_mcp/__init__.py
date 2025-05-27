"""Gen3 MCP Server Package

A Model Context Protocol (MCP) server for interacting with Gen3 data commons,
with GraphQL query validation to reduce field name hallucinations.
"""

from .client import Gen3Client
from .config import Gen3Config, setup_logging
from .schema import SchemaService
from .exceptions import (
    Gen3ClientError,
    Gen3MCPError,
    Gen3SchemaError,
)
from .query import QueryService

__version__ = "1.1.0"

__all__ = [
    "__version__",
    "Gen3Config",
    "setup_logging",
    "Gen3Client",
    "SchemaService",
    "QueryService",
    "Gen3MCPError",
    "Gen3ClientError",
    "Gen3SchemaError",
]
