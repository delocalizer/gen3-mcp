"""Custom exceptions for the Gen3 MCP package"""


# Base exceptions
class Gen3MCPError(Exception):
    """Base exception for all Gen3 MCP errors"""
    pass


class Gen3ClientError(Gen3MCPError):
    """Client-related errors"""
    pass


class Gen3SchemaError(Gen3MCPError):
    """Schema-related errors"""
    pass


class QueryValidationError(Gen3MCPError):
    """Query validation errors"""
    pass
