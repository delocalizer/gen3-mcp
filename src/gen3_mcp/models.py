from enum import StrEnum

from pydantic import BaseModel, Field, computed_field


class PositionDescription(StrEnum):
    """Describes the entity node location in the data model graph"""

    INTERMEDIATE = "intermediate"
    LEAF = "leaf"
    ROOT = "root"


class RelType(StrEnum):
    """Describes a relationship between source and target entity."""

    CHILD_OF = "child_of"
    PARENT_OF = "parent_of"


class Type(StrEnum):
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


class Property(BaseModel):
    """
    Describes a property of an entity in the Gen3 data model.
    """

    name: str = Field(..., description="Name of the property")
    type_: Type = Field(..., description="Type of the property")
    enum_vals: list[str] | None = Field(
        None, description="Allowed values when type_ is Type.ENUM"
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
    def position_description(self) -> PositionDescription:
        if self.parent_count == 0:
            return PositionDescription.ROOT
        elif self.child_count == 0:
            return PositionDescription.LEAF
        else:
            return PositionDescription.INTERMEDIATE


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
