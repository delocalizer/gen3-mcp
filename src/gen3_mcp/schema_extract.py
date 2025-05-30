"""Data structure extracted from full Gen3 schema for GraphQL validation."""

import json
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("gen3-mcp.schema_extract")


@dataclass
class Relationship:
    """A relationship between entities."""

    name: str  # The field name used in GraphQL (e.g., "studies")
    target_type: str  # The target entity type (e.g., "study")
    backref: str  # The reverse field name (e.g., "subjects")


@dataclass
class EntitySchema:
    """Minimal entity schema for GraphQL validation."""

    name: str  # Entity name (e.g., "subject")
    fields: set[str]  # All valid scalar fields
    relationships: dict[str, Relationship]  # Field name -> Relationship


class SchemaExtract:
    """Minimal schema structure for efficient GraphQL validation."""

    # Simple static cache for schema extract (once per execution)
    _cached_extract: "SchemaExtract" = None

    def __init__(self):
        """Initialize SchemaExtract."""
        self.entities: dict[str, EntitySchema] = {}

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the cached schema extract (useful for testing)."""
        cls._cached_extract = None

    @classmethod
    def from_full_schema(cls, full_schema: dict[str, Any]) -> "SchemaExtract":
        """Extract minimal validation schema from full Gen3 schema.

        Args:
            full_schema: Full Gen3 schema dict.

        Returns:
            SchemaExtract instance with minimal schema for validation.
        """
        # Return cached version if available
        if cls._cached_extract is not None:
            logger.debug("Using cached schema extract")
            return cls._cached_extract

        logger.debug("Creating new schema extract")

        # Create new extract
        extract = cls()

        for entity_name, entity_def in full_schema.items():
            # Skip special keys
            if entity_name.startswith("_"):
                continue

            # Extract scalar fields from properties
            fields = set()
            properties = entity_def.get("properties", {})

            for prop_name, prop_def in properties.items():
                # Skip relationship fields (they have complex object structures)
                if isinstance(prop_def, dict):
                    # Simple heuristic: if it has 'anyOf' with object refs, it's a relationship
                    if "anyOf" in prop_def:
                        continue
                    # If it's a simple type, it's a scalar field
                    if "type" in prop_def or "enum" in prop_def:
                        fields.add(prop_name)

            # Add standard fields always available
            fields.update(["id", "submitter_id", "type"])

            # Extract relationships from links
            relationships = {}
            links = entity_def.get("links", [])

            for link in links:
                # Process direct relationship
                if link.get("name") and link.get("target_type"):
                    relationships[link["name"]] = Relationship(
                        name=link["name"],
                        target_type=link["target_type"],
                        backref=link.get("backref", ""),
                    )

                # Process subgroup relationships
                subgroup = link.get("subgroup", [])
                for sublink in subgroup:
                    if sublink.get("name") and sublink.get("target_type"):
                        relationships[sublink["name"]] = Relationship(
                            name=sublink["name"],
                            target_type=sublink["target_type"],
                            backref=sublink.get("backref", ""),
                        )

            extract.entities[entity_name] = EntitySchema(
                name=entity_name, fields=fields, relationships=relationships
            )

        # Add backref relationships (reverse lookups)
        cls._add_backref_relationships(extract)

        # Cache the result
        cls._cached_extract = extract
        logger.info(f"Schema extract created with {len(extract.entities)} entities")

        return extract

    @classmethod
    def _add_backref_relationships(cls, extract: "SchemaExtract") -> None:
        """Add backref relationships to entities.

        Args:
            extract: SchemaExtract to add backrefs to.
        """
        logger.debug("Adding backref relationships")

        # For each entity's relationships, add the backref to the target entity
        for entity_name, entity in extract.entities.items():
            for rel in entity.relationships.values():
                target_entity = extract.entities.get(rel.target_type)
                if target_entity and rel.backref:
                    # Add backref relationship to target entity
                    target_entity.relationships[rel.backref] = Relationship(
                        name=rel.backref, target_type=entity_name, backref=rel.name
                    )


def extract_from_file(schema_file_path: str) -> SchemaExtract:
    """Return schema extract read from full schema in a JSON file.

    Args:
        schema_file_path: Path to JSON file containing full Gen3 schema.

    Returns:
        SchemaExtract instance.

    Raises:
        FileNotFoundError: If schema file not found.
        json.JSONDecodeError: If schema file contains invalid JSON.
    """
    logger.debug(f"Extracting schema from file: {schema_file_path}")

    with open(schema_file_path) as f:
        full_schema = json.load(f)

    return SchemaExtract.from_full_schema(full_schema)
