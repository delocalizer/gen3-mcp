"""Custom exceptions for the Gen3 MCP package"""


# Base exceptions
class Gen3MCPError(Exception):
    """Base exception for all Gen3 MCP errors"""

    pass


class Gen3ClientError(Gen3MCPError):
    """Base exception for client-related errors"""

    pass


class Gen3SchemaError(Gen3MCPError):
    """Base exception for schema-related errors"""

    pass


class Gen3ValidationError(Gen3MCPError):
    """Base exception for validation-related errors"""

    pass


# Specific exceptions
class EntityNotFoundError(Gen3SchemaError):
    """Raised when an entity is not found in the schema"""

    pass


class SchemaFetchError(Gen3SchemaError):
    """Raised when schema cannot be fetched from Gen3"""

    pass


class FieldNotFoundError(Gen3ValidationError):
    """Raised when a field is not found in an entity"""

    pass


class QueryValidationError(Gen3ValidationError):
    """Raised when GraphQL query validation fails"""

    pass


class AuthenticationError(Gen3ClientError):
    """Raised when authentication fails"""

    pass


class TokenRefreshError(Gen3ClientError):
    """Raised when token refresh fails"""

    pass
