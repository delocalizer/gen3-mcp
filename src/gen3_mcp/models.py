from enum import StrEnum
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field, computed_field

from .exceptions import Gen3MCPError

# =============================================================================
# UNIFIED RESPONSE MODEL
# =============================================================================
# Single response type for all service operations and MCP tools


class Response(BaseModel):
    """Unified response type for all service operations and MCP tools."""

    status: Literal["success", "error"] = Field(
        ..., description="Response status indicating outcome"
    )
    message: str = Field(..., description="Human-readable summary of the response")
    data: Any | None = Field(
        None,
        description="Response payload - can be dict, pydantic model, or any serializable type",
    )
    errors: list[str] = Field(
        default_factory=list, description="List of error messages"
    )
    suggestions: list[str] = Field(
        default_factory=list, description="Actionable suggestions for the user"
    )
    metadata: dict[str, Any] | None = Field(
        None, description="Additional context and domain-specific information"
    )

    @classmethod
    def from_error(cls, error: Exception) -> "Response":
        """Create Response from any Exception, with potentially helpful info for recovery.

        Args:
            error: Any Exception instance

        Returns:
            Response object with error details
        """
        if isinstance(error, Gen3MCPError):
            # Use rich context from Gen3MCPError
            return cls(
                status="error",
                message=error.message,
                errors=error.errors,
                suggestions=error.suggestions,
                metadata={**error.context, "exception_type": type(error).__name__},
            )
        else:
            # Handle specific library exceptions
            if isinstance(error, httpx.HTTPStatusError):
                # HTTP errors get user-friendly messaging
                status_code = error.response.status_code
                if status_code >= 500:
                    message = f"Gen3 server error ({status_code}): {str(error)}"
                    suggestions = []
                elif status_code == 401:
                    message = f"Authentication failed ({status_code}): {str(error)}"
                    suggestions = [
                        "Verify your credentials file is correct",
                    ]
                elif status_code == 404:
                    message = f"Resource not found ({status_code}): {str(error)}"
                    suggestions = [
                        "Check your Gen3 endpoint configuration",
                    ]
                else:
                    message = f"HTTP error ({status_code}): {str(error)}"
                    suggestions = ["Check the request and try again"]

                return cls(
                    status="error",
                    message=message,
                    errors=[str(error)],
                    suggestions=suggestions,
                    metadata={
                        "exception_type": type(error).__name__,
                        "status_code": status_code,
                        "url": str(error.response.url),
                    },
                )
            elif isinstance(error, httpx.RequestError):
                # Network/connection errors
                metadata = {"exception_type": type(error).__name__}
                if hasattr(error, "request") and hasattr(error.request, "url"):
                    metadata["url"] = str(error.request.url)

                return cls(
                    status="error",
                    message=f"Network error: {str(error)}",
                    errors=[str(error)],
                    suggestions=[
                        "Check your internet connection",
                        "Verify the Gen3 endpoint URL is correct",
                        "Try again - this may be a temporary network issue",
                    ],
                    metadata=metadata,
                )
            else:
                # Generic exception handling
                return cls(
                    status="error",
                    message=f"Unexpected error: {str(error)}",
                    errors=[str(error)],
                    suggestions=[
                        "Check server logs for detailed information",
                        "Try again - this may be a temporary issue",
                    ],
                    metadata={"exception_type": type(error).__name__},
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

    def to_summary_json(self) -> dict[str, dict]:
        """Convert to JSON-serializable dict without field details for conciseness.

        Fields are omitted from the summary to keep the response size manageable
        for MCP transport. Use get_schema_entity() to retrieve detailed field
        information for specific entities.
        """
        result = {}
        for k, v in self.items():
            entity_data = v.model_dump()
            entity_data.pop("fields", None)  # Remove fields key entirely
            result[k] = entity_data
        return result
