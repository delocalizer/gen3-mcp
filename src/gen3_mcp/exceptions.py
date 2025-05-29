"""Gen3 MCP custom exceptions."""


class Gen3MCPError(Exception):
    """Base exception for all Gen3 MCP errors."""

    pass


class Gen3ClientError(Gen3MCPError):
    """Client-related errors."""

    pass


class Gen3SchemaError(Gen3MCPError):
    """Schema-related errors."""

    pass
