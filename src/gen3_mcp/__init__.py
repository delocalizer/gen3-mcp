"""Gen3 MCP Server Package

A Model Context Protocol (MCP) server for interacting with Gen3 data commons,
with GraphQL query validation to reduce field name hallucinations.
"""

from .client import Gen3Client
from .config import Gen3Config, setup_logging
from .data import Gen3Service
from .exceptions import (
    Gen3ClientError,
    Gen3MCPError,
    Gen3SchemaError,
    QueryValidationError,
)
from .graphql_parser import extract_query_fields, validate_graphql
from .query import QueryService

__version__ = "1.0.1"

__all__ = [
    "__version__",
    "Gen3Config",
    "setup_logging",
    "Gen3Client",
    "Gen3Service",
    "QueryService",
    "Gen3MCPError",
    "Gen3ClientError",
    "Gen3SchemaError",
    "QueryValidationError",
    "extract_query_fields",
    "validate_graphql",
]
