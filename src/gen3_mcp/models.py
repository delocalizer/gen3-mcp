from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field

# =============================================================================
# HTTP CLIENT MODELS
# =============================================================================
# Models for HTTP client operations and error handling.
# These models standardize responses from HTTP requests to Gen3 APIs,
# providing consistent error categorization and response formatting.


class ErrorCategory(StrEnum):
    """Categories of errors that can occur during HTTP requests."""

    NETWORK = "NETWORK"  # Connection errors, timeouts, DNS failures
    HTTP_CLIENT = "HTTP_CLIENT"  # 4xx errors (client errors)
    HTTP_SERVER = "HTTP_SERVER"  # 5xx errors (server errors)
    JSON_PARSE = "JSON_PARSE"  # Response isn't valid JSON
    OTHER = "OTHER"  # Any other unexpected errors


class ClientResponse(BaseModel):
    """Standardized response from Gen3Client HTTP operations."""

    success: bool
    status_code: int | None = None
    data: Any | None = None
    error_category: ErrorCategory | None = None
    errors: list[str] = Field(
        default_factory=list, description="List of error messages"
    )


# =============================================================================
# GEN3 SCHEMA MODELS
# =============================================================================
# Models representing the Gen3 data model schema structure.
# These models capture entity definitions, field types, relationships,
# and metadata extracted from Gen3 schema files. They form a complete
# representation of the data model for query building and validation.


class FieldType(StrEnum):
    """JSON simple types, plus compound types and enum"""

    ARRAY = "array"
    BOOLEAN = "boolean"
    INTEGER = "integer"
    NUMBER = "number"
    OBJECT = "object"
    STRING = "string"
    ANYOF = "anyOf"
    ONEOF = "oneOf"
    ENUM = "enum"


class RelType(StrEnum):
    """Describes a relationship between source and target entity."""

    CHILD_OF = "child_of"
    PARENT_OF = "parent_of"


class Property(BaseModel):
    """
    Describes a property of an entity in the Gen3 data model.
    """

    name: str = Field(..., description="Name of the property")
    type_: FieldType = Field(..., description="Type of the property")
    enum_vals: list[str] | None = Field(
        None, description="Allowed values when type_ is FieldType.ENUM"
    )


class Relationship(BaseModel):
    """
    Describes a relationship between entities in the Gen3 data model. Captures
    info explicitly defined in schema entity links, and inferred from backrefs.
    """

    name: str = Field(..., description="Field name used in GraphQL (e.g., 'studies')")
    source_type: str = Field(..., description="Source entity type (e.g., 'subject')")
    target_type: str = Field(..., description="Target entity type (e.g., 'study')")
    link_type: RelType = Field(
        ..., description="Relationship between source and target"
    )


class EntitySummary(BaseModel):
    """Schema summary information for an entity."""

    title: str = Field(..., description="Title of the entity in the schema")
    description: str = Field(..., description="Description of the entity in the schema")
    category: str = Field(..., description="Category of the entity in the schema")
    required_fields: list[str] = Field([], description="Required fields from schema")
    enum_fields: list[str] = Field([], description="Fields that have enum constraints")
    field_count: int = Field(0, description="Number of scalar fields on the entity")
    parent_count: int = Field(0, description="Number of parents")
    child_count: int = Field(0, description="Number of children")

    @computed_field
    @property
    def position_description(self) -> Literal["intermediate", "leaf", "root"]:
        """Describes the entity node location in the data model graph."""
        if self.parent_count == 0:
            return "root"
        elif self.child_count == 0:
            return "leaf"
        else:
            return "intermediate"


class EntitySchema(BaseModel):
    """
    Describes an entity in the Gen3 data model.
    """

    name: str = Field(..., description="Name of the entity")
    fields: dict[str, Property] = Field({}, description="Scalar fields on the entity")
    relationships: dict[str, Relationship] = Field(
        {}, description="Relationships to other entities"
    )
    schema_summary: EntitySummary | None = Field(
        None, description="Schema summary information"
    )


class SchemaExtract(dict[str, EntitySchema]):
    """Schema extract containing entity definitions keyed by entity name."""

    def to_json(self) -> dict[str, dict]:
        """Convert to JSON-serializable dict."""
        return {k: v.model_dump() for k, v in self.items()}


# =============================================================================
# GRAPHQL QUERY VALIDATION MODELS
# =============================================================================
# Models for validating GraphQL queries against the Gen3 schema.
# These models capture validation errors, provide suggestions for fixes,
# and format results for user consumption.


class QueryValidationError(BaseModel):
    """Validation error with context and suggestions."""

    entity: str = Field(..., description="Entity where error occurred")
    field: str = Field(..., description="Field where error occurred")
    error_type: str = Field(
        ..., description="Type of error (syntax_error, unknown_entity, unknown_field)"
    )
    message: str = Field(..., description="Human readable error message")
    suggestions: list[str] = Field(default_factory=list, description="Suggested fixes")


class QueryValidationResult(BaseModel):
    """GraphQL query validation result with essential context."""

    # Core validation results
    valid: bool = Field(..., description="Whether the query is valid")
    query: str = Field(..., description="Original query that was validated")

    # Error details
    errors: list[QueryValidationError] = Field(
        default_factory=list, description="Validation errors found"
    )

    @computed_field
    @property
    def error_count(self) -> int:
        """Total number of validation errors."""
        return len(self.errors)

    @computed_field
    @property
    def status(self) -> Literal["success", "error"]:
        """MCP-compatible status derived from validation result."""
        return "success" if self.valid else "error"

    @computed_field
    @property
    def summary(self) -> str:
        """Human-readable summary of validation result."""
        if self.valid:
            return "Query validation successful"
        else:
            return f"Query validation failed with {self.error_count} errors"

    def to_mcp_response(self) -> "MCPResponse":
        """Convert to MCP response format."""
        if self.valid:
            return MCPResponse.success(
                message=self.summary,
                data={"valid": self.valid, "query": self.query},
                next_steps={
                    "ready_to_execute": True,
                    "suggestion": "Query is valid! Use execute_graphql() to run it.",
                },
            )
        return MCPResponse.error(
            message=self.summary,
            errors=[f"{err.entity}.{err.field}: {err.message}" for err in self.errors],
            suggestions=[
                "Fix the validation errors using the suggestions above",
                "Use get_schema_summary() to see available entities and fields",
            ],
            next_steps={
                "workflow": [
                    "1. Fix the validation errors using the suggestions above",
                    "2. Re-run validate_query() to confirm fixes",
                    "3. Use execute_graphql() to run the validated query",
                ],
                "alternative": "Start fresh with generate_query_template() for a guaranteed valid query",
            },
            metadata={"query": self.query, "error_count": self.error_count},
        )


# =============================================================================
# MCP RESPONSE MODELS
# =============================================================================
# Models for standardized MCP (Model Context Protocol) tool responses.
# These models provide a consistent format for returning results from
# MCP tools, including success/error status, data, suggestions, and workflow guidance.


class MCPResponse(BaseModel):
    """Standardized MCP tool response format."""

    status: Literal["success", "error", "warning"] = Field(
        ..., description="Response status"
    )
    message: str = Field(..., description="Human-readable summary message")
    data: dict[str, Any] | None = Field(None, description="Response payload data")
    errors: list[str] = Field(
        default_factory=list, description="List of error messages"
    )
    suggestions: list[str] = Field(
        default_factory=list, description="Actionable suggestions"
    )
    next_steps: dict[str, Any] | None = Field(None, description="Workflow guidance")
    metadata: dict[str, Any] | None = Field(None, description="Additional context")

    def to_json(self) -> str:
        """Convert to JSON string for MCP tool response."""
        return self.model_dump_json(exclude_none=True, indent=2)

    # convenience methods
    @classmethod
    def success(
        cls,
        message: str,
        data: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
        next_steps: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "MCPResponse":
        """Create a success response."""
        return cls(
            status="success",
            message=message,
            data=data,
            suggestions=suggestions or [],
            next_steps=next_steps,
            metadata=metadata,
        )

    @classmethod
    def error(
        cls,
        message: str,
        errors: list[str] | None = None,
        suggestions: list[str] | None = None,
        next_steps: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "MCPResponse":
        """Create an error response."""
        return cls(
            status="error",
            message=message,
            errors=errors or [],
            suggestions=suggestions or [],
            next_steps=next_steps,
            metadata=metadata,
        )
