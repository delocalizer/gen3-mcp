"""Gen3 MCP Server Package

A Model Context Protocol (MCP) server for interacting with Gen3 data commons,
with comprehensive GraphQL query validation to prevent field name hallucinations.
"""

__version__ = "0.2.0"

from .config import Gen3Config, setup_logging
from .client import Gen3Client
from .service import Gen3Service
from .query import QueryService
from .tools import Tools
from .exceptions import (
    Gen3MCPError,
    Gen3ClientError,
    Gen3SchemaError,
    QueryValidationError,
)

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
