"""Data structure extracted from full Gen3 schema for GraphQL validation."""

import json
import logging
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

logger = logging.getLogger("gen3-mcp.schema_extract")


class RelType(StrEnum):
    CHILD_OF = "child_of"
    PARENT_OF = "parent_of"


@dataclass
class Relationship:
    """
    A relationship between entities. Captures info explicitly defined in
    schema entity links, and inferred from backrefs.
    """

    name: str  # The field name used in GraphQL (e.g., "studies")
    source_type: str  # The source entity type (e.g., "subject")
    target_type: str  # The target entity type (e.g., "study")
    link_type: RelType  # The relationship between source and target
    link_multiplicity: str  # The cardinality of the relation
    # link_label is the name of the relationship between source and target,
    # e.g. "derived_from" between aliquot and sample. It is Optional because
    # it is explicit in the schema only for 'child_of' relationships and
    # unlike multiplicity, can't safely be inferred for backrefs.
    link_label: str | None = None


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

    def __repr__(self) -> str:
        """String representation."""
        return json.dumps(
            {k: asdict(v) for k, v in self.entities.items()},
            default=custom_handler,
            indent=2,
        )

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
        relationships = []

        for entity_name, entity_def in full_schema.items():
            # Skip special keys
            if entity_name.startswith("_"):
                continue

            # Extract relationships from links
            links = [
                link for link in entity_def.get("links", []) if "subgroup" not in link
            ]
            links.extend(
                # Handle subgroup links (common in Gen3)
                [
                    sublink
                    for link in entity_def.get("links", [])
                    for sublink in link.get("subgroup", [])
                ]
            )

            # Collect explicit and implied relationships
            for link in links:
                # All explicit schema links are 'child_of' relations.
                relationships.append(
                    Relationship(
                        name=link["name"],
                        source_type=entity_name,
                        target_type=link["target_type"],
                        link_type=RelType.CHILD_OF,
                        link_label=link["label"],
                        link_multiplicity=link["multiplicity"],
                    )
                )
                # If backref exists it defines the reverse relation
                if link.get("backref"):
                    relationships.append(
                        Relationship(
                            name=link["backref"],
                            source_type=link["target_type"],
                            target_type=entity_name,
                            link_type=RelType.PARENT_OF,
                            link_multiplicity=invert_multiplicity(link["multiplicity"]),
                        )
                    )

            # Extract scalar fields from properties
            fields = set(entity_def.get("properties", {})) - {
                link["name"] for link in links
            }

            extract.entities[entity_name] = EntitySchema(
                name=entity_name, fields=fields, relationships={}
            )

        # Add the collected relationships
        for rel in relationships:
            # Links might possibly reference types not actually defined in the
            # schema; these relationships are omitted so the result is closed.
            source = extract.entities.get(rel.source_type)
            target = extract.entities.get(rel.target_type)
            if not source:
                logger.info(f"Entity {rel.source_type} not found")
                continue
            elif not target:
                logger.info(f"Entity {rel.target_type} not found")
                continue
            source.relationships[rel.name] = rel

        # Cache the result
        cls._cached_extract = extract
        logger.info(f"Schema extract created with {len(extract.entities)} entities")

        return extract


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


def custom_handler(obj: Any) -> Any:
    """
    Handler for things that can't be normally be serialized as JSON.

    Currently supports:
        - set: returned as sorted(list(...))
    """
    if isinstance(obj, set):
        return sorted(obj)
    raise TypeError


def invert_multiplicity(mult: str) -> str:
    """
    Return the inverse of the given relationship multiplicity. For example:

    >>> invert_multiplicity("many_to_one")
    "one_to_many"
    >>> invert_multiplicity("many_to_many")
    "many_to_many"
    """
    inverse = {
        "one_to_many": "many_to_one",
        "one_to_one": "one_to_one",
        "many_to_one": "one_to_many",
        "many_to_many": "many_to_many",
    }
    try:
        return inverse[mult]
    except KeyError as e:
        raise ValueError(f"unrecognized cardinality: {mult}") from e
