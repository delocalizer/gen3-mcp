"""Gen3 MCP Server Package

A Model Context Protocol (MCP) server for interacting with Gen3 data commons,
with comprehensive GraphQL query validation to prevent field name hallucinations.
"""

__version__ = "1.0"

from .client import Gen3Client
from .config import Gen3Config, setup_logging
from .exceptions import (
    Gen3ClientError,
    Gen3MCPError,
    Gen3SchemaError,
    QueryValidationError,
)
from .graphql_parser import extract_fields_from_query, validate_graphql_syntax
from .query import QueryService
from .service import Gen3Service
from .tools import Tools
from .utils import parse_kwargs_string

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
    "extract_fields_from_query",
    "validate_graphql_syntax",
    "parse_kwargs_string",
]
