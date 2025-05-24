"""Gen3 MCP Server Package

A Model Context Protocol (MCP) server for interacting with Gen3 data commons,
with comprehensive GraphQL query validation to prevent field name hallucinations.
"""

__version__ = "0.3.0"

from .client import Gen3Client
from .config import Gen3Config, setup_logging
from .exceptions import (
    Gen3ClientError,
    Gen3MCPError,
    Gen3SchemaError,
    QueryValidationError,
)
from .query import QueryService
from .service import Gen3Service
from .tools import Tools

__all__ = [
    "__version__",
    "Gen3Config",
    "setup_logging",
    "Gen3Client",
    "Gen3Service",
    "QueryService",
    "Tools",
    "Gen3MCPError",
    "Gen3ClientError",
    "Gen3SchemaError",
    "QueryValidationError",
]
