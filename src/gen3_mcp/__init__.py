"""Gen3 MCP Server Package

A Model Context Protocol (MCP) server for interacting with Gen3 data commons,
with comprehensive GraphQL query validation to prevent field name hallucinations.
"""

__version__ = "0.2.0"

from .config import Gen3Config, setup_logging
from .client import Gen3Client, Gen3ClientProtocol
from .schema import SchemaService
from .query import QueryBuilder, QueryExecutor
from .tools import UnifiedTools
from .resources import Gen3Resources
from .exceptions import (
    Gen3MCPError,
    Gen3ClientError,
    Gen3SchemaError,
    Gen3ValidationError,
    EntityNotFoundError,
    SchemaFetchError,
    FieldNotFoundError,
    QueryValidationError,
    AuthenticationError,
    TokenRefreshError,
)

__all__ = [
    # Version
    "__version__",
    # Configuration
    "Gen3Config",
    "setup_logging",
    # Client
    "Gen3Client",
    "Gen3ClientProtocol",
    # Services
    "SchemaService",
    "QueryBuilder",
    "QueryExecutor",
    # Tools and Resources
    "UnifiedTools",
    "Gen3Resources",
    # Exceptions
    "Gen3MCPError",
    "Gen3ClientError",
    "Gen3SchemaError",
    "Gen3ValidationError",
    "EntityNotFoundError",
    "SchemaFetchError",
    "FieldNotFoundError",
    "QueryValidationError",
    "AuthenticationError",
    "TokenRefreshError",
]
