"""Gen3 MCP custom exceptions.

Exception Design Principles:
1. Use these custom exceptions only when additional useful context can be provided
2. Handle exceptions as late as possible (preserve details until domain context is available)
3. Split on domain of actionable information:
   - Unrecoverable except by code changes (ParseError)
   - Recoverable by user reconfiguration outside session (ConfigError)
   - Potentially recoverable by LLM action in-session (NoSuchEntityError, GraphQLError)
"""


class Gen3MCPError(Exception):
    """Base exception for all Gen3 MCP errors.

    Provides rich context and actionable suggestions beyond standard exceptions.
    All Gen3 MCP custom exceptions inherit from this base class.
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


class ParseError(Gen3MCPError):
    """Schema parsing and processing errors - unrecoverable without code changes.

    Used when Gen3 schema doesn't conform to expected structure, indicating
    either schema format evolution or bugs in parsing logic:
    - Unknown property types during schema processing
    - Missing required schema elements that code expects
    - Schema structure changes that break parsing assumptions

    These errors require developer intervention - either schema format changes
    or code updates to handle new schema patterns. Not user-actionable.
    """

    pass


class ConfigError(Gen3MCPError):
    """Application configuration errors - recoverable by user reconfiguration.

    Covers setup issues that prevent initialization but can be resolved by
    user action outside the current session:
    - Missing or malformed credentials files
    - Invalid endpoint URLs or base configuration
    - File system permission issues for config files

    Does NOT include runtime HTTP errors (401, 404, 5xx) - those should remain
    as httpx exceptions and be handled in Response.from_error() with appropriate
    user messaging. Only use ConfigError when we can add meaningful context
    beyond what the underlying exception provides.
    """

    pass


class NoSuchEntityError(Gen3MCPError):
    """Entity or field not found - recoverable by LLM schema exploration.

    Business logic errors when requested entities or fields don't exist
    in the schema, but the LLM can potentially recover by exploring
    available schema options:
    - Unknown entity names in query templates
    - Invalid field names for specific entities
    - Missing relationships between entities

    Provides similarity-based suggestions and schema exploration context
    to help the LLM make better subsequent attempts.
    """

    pass


class GraphQLError(Gen3MCPError):
    """GraphQL query errors - recoverable by LLM query refinement.

    GraphQL-specific errors that the LLM can potentially fix by modifying
    the query based on the provided error details and suggestions:
    - Invalid GraphQL syntax
    - Field validation failures from server
    - Query execution errors with specific field/type information
    - Malformed query structure

    Provides specific error details and actionable suggestions for query
    modification to help the LLM construct valid queries.
    """

    pass
