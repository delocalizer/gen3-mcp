from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field

# =============================================================================
# ERROR CATEGORIZATION
# =============================================================================


class ErrorCategory(StrEnum):
    """Categories of errors that can occur during operations."""

    NETWORK = "NETWORK"  # Connection errors, timeouts, DNS failures
    HTTP_SERVER = "HTTP_SERVER"  # 5xx errors (server errors)
    HTTP_CLIENT = "HTTP_CLIENT"  # 4xx errors (client errors)
    JSON_PARSE = "JSON_PARSE"  # Response isn't valid JSON
    SCHEMA = "SCHEMA"  # Schema processing errors
    GRAPHQL = "GRAPHQL"  # GraphQL validation or execution errors
    OTHER = "OTHER"  # Any other unexpected errors


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

    # Utility properties
    @property
    def is_success(self) -> bool:
        """Check if response indicates success."""
        return self.status == "success"

    @property
    def is_error(self) -> bool:
        """Check if response indicates error."""
        return self.status == "error"


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
