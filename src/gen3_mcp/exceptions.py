"""Gen3 MCP custom exceptions."""


class Gen3MCPError(Exception):
    """Base exception for all Gen3 MCP errors.

    Provides rich context and actionable suggestions beyond standard exceptions.
    All Gen3 MCP custom exceptions inherit from this base class and use the
    same four core attributes for consistent error handling.
    """

    def __init__(
        self,
        message: str,  # the error message
        *,
        errors: list[str] = None,  # detailed list of errors (if available)
        suggestions: list[str] = None,  # remedial actions
        context: dict = None,  # additional detailed context
    ):
        """Initialize Gen3MCPError.

        Args:
            message: Primary error message for users
            errors: List of specific error details
            suggestions: List of actionable suggestions for resolution
            context: Additional context information as key-value pairs
        """
        super().__init__(message)
        self.message = message
        self.errors = errors or []
        self.suggestions = suggestions or []
        self.context = context or {}


class ClientError(Gen3MCPError):
    """Client setup, configuration, and authentication errors.

    Covers all errors that prevent the client from being properly configured
    or authenticated, including:
    - Credentials file issues (missing, malformed JSON)
    - Configuration validation failures (invalid URLs, timeouts)
    - Token acquisition failures (HTTP errors during auth)
    - Auth server response issues (missing access_token)

    These are all "fix your setup before you can use the application" errors.
    """

    pass


class GraphQLError(Gen3MCPError):
    """GraphQL query execution and validation errors.

    Captures GraphQL-specific error details and provides domain-specific
    suggestions for query problems, including:
    - Invalid GraphQL syntax
    - Field names that don't exist in the schema
    - Malformed query structure
    - Server-side GraphQL execution errors

    Provides context about the original query and specific GraphQL error details.
    """

    pass


class SchemaError(Gen3MCPError):
    """Schema processing and validation errors.

    Captures schema parsing context and provides remediation advice for:
    - Malformed Gen3 schema format
    - Unknown property types during schema processing
    - Missing required schema elements
    - Schema version compatibility issues

    Provides context about which entity or property caused the failure.
    """

    pass


class EntityError(Gen3MCPError):
    """Entity or field not found errors with suggestions.

    Business logic errors when requested entities or fields don't exist
    in the schema, including:
    - Unknown entity names in query templates
    - Invalid field names for specific entities
    - Missing relationships between entities

    Provides similarity-based suggestions for correct entity/field names.
    """

    pass
