"""
Extract from full Gen3 schema. The two main purposes are to:
1. make relationships explicit to facilitate GraphQL query validation.
2. add schema annotations for consumption as context by MCP tools.
"""

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
class RelationshipQueryExample:
    """Example GraphQL query showing how to query a relationship."""

    description: str  # Human-readable description of the query
    query: str  # The actual GraphQL query string


@dataclass
class QueryPatterns:
    """GraphQL query patterns and examples for an entity."""

    basic_query: str  # Basic query with core fields
    with_relationships: list[RelationshipQueryExample]  # Relationship query examples


@dataclass
class SchemaSummary:
    """Schema summary information for an entity."""

    title: str  # Entity title from schema
    description: str  # Entity description from schema
    category: str  # Entity category from schema
    required_fields: list[str]  # Required fields from schema
    field_count: int  # Number of fields
    parent_count: int  # Number of parent relationships
    child_count: int  # Number of child relationships
    position_description: dict[
        str, str
    ]  # Hierarchical position info with "position" and "description" keys


@dataclass
class EntitySchema:
    """Annotated entity schema for GraphQL validation."""

    name: str  # Entity name (e.g., "subject")
    fields: set[str]  # All valid scalar fields
    relationships: dict[str, Relationship]  # Field name -> Relationship
    schema_summary: SchemaSummary | None = None  # Schema summary information
    query_patterns: QueryPatterns | None = None  # GraphQL query patterns and examples


class SchemaExtract:
    """Annotated schema structure for efficient GraphQL validation."""

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
        """Extract annotated validation schema from full Gen3 schema.

        Args:
            full_schema: Full Gen3 schema dict.

        Returns:
            SchemaExtract instance.
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

        # Add schema summary information and query patterns
        for entity_name, entity in extract.entities.items():
            entity_def = full_schema.get(entity_name)
            if entity_def:
                entity.schema_summary = _create_schema_summary(entity, entity_def)
                entity.query_patterns = _create_query_patterns(entity)

        # Cache the result
        cls._cached_extract = extract
        logger.info(f"Schema extract created with {len(extract.entities)} entities")

        return extract


def _create_schema_summary(
    entity: EntitySchema, entity_def: dict[str, Any]
) -> SchemaSummary:
    """Create schema summary information for an entity.

    Args:
        entity: The EntitySchema instance.
        entity_def: The entity definition from the full schema.

    Returns:
        SchemaSummary instance with all summary information.
    """
    # Count parent and child relationships
    parent_count = sum(
        1 for rel in entity.relationships.values() if rel.link_type == RelType.CHILD_OF
    )
    child_count = sum(
        1 for rel in entity.relationships.values() if rel.link_type == RelType.PARENT_OF
    )

    # Determine position description
    position_desc = _get_position_description(parent_count, child_count)

    return SchemaSummary(
        title=entity_def.get("title", ""),
        description=entity_def.get("description", ""),
        category=entity_def.get("category", ""),
        required_fields=entity_def.get("required", []),
        field_count=len(entity.fields),
        parent_count=parent_count,
        child_count=child_count,
        position_description=position_desc,
    )


def _create_query_patterns(entity: EntitySchema) -> QueryPatterns:
    """Create GraphQL query patterns for an entity.

    Args:
        entity: The EntitySchema instance.

    Returns:
        QueryPatterns instance with query examples.
    """
    entity_name = entity.name

    # Basic query with core fields
    basic_query = f"""{{
    {entity_name}(first: 10) {{
        id
        submitter_id
        type
    }}
}}"""

    # Relationship query examples
    relationship_examples = []

    # Get parent relationships (CHILD_OF means this entity links TO parents)
    parent_rels = [
        rel
        for rel in entity.relationships.values()
        if rel.link_type == RelType.CHILD_OF
    ]

    # Get child relationships (PARENT_OF means children link TO this entity)
    child_rels = [
        rel
        for rel in entity.relationships.values()
        if rel.link_type == RelType.PARENT_OF
    ]

    # Add parent relationship examples (limit to 2)
    for rel in sorted(parent_rels, key=lambda r: r.target_type)[:2]:
        relationship_examples.append(
            RelationshipQueryExample(
                description=f"Get {entity_name} with linked parent {rel.target_type} data",
                query=f"""{{
    {entity_name}(first: 5) {{
        id
        submitter_id
        {rel.name} {{
            id
            submitter_id
        }}
    }}
}}""",
            )
        )

    # Add child relationship examples (limit to 2)
    for rel in sorted(child_rels, key=lambda r: r.target_type)[:2]:
        relationship_examples.append(
            RelationshipQueryExample(
                description=f"Get {entity_name} with linked child {rel.target_type} data",
                query=f"""{{
    {entity_name}(first: 5) {{
        id
        submitter_id
        {rel.name} {{
            id
            submitter_id
        }}
    }}
}}""",
            )
        )

    # Add parent + child query if entity has both parents and children
    if parent_rels and child_rels:
        # Take the first parent and first child for the combined query
        parent_rel = parent_rels[0]
        child_rel = child_rels[0]
        
        combined_query = f"""{{
    {entity_name}(first: 5) {{
        id
        submitter_id
        {parent_rel.name} {{
            id
            submitter_id
        }}
        {child_rel.name} {{
            id
            submitter_id
        }}
    }}
}}"""
        relationship_examples.append(
            RelationshipQueryExample(
                description=f"Get {entity_name} with parent {parent_rel.target_type} and child {child_rel.target_type} data",
                query=combined_query,
            )
        )

    return QueryPatterns(
        basic_query=basic_query,
        with_relationships=relationship_examples
    )


def _get_position_description(parent_count: int, child_count: int) -> dict[str, str]:
    """Determine the entity's position in the typical data flow.

    Args:
        parent_count: Number of parent relationships.
        child_count: Number of child relationships.

    Returns:
        Dict with "position" and "description" keys.
    """
    if parent_count == 0:
        return {
            "position": "root",
            "description": "Top-level entity (no parents) - likely administrative or entry point",
        }
    elif child_count == 0:
        return {
            "position": "leaf",
            "description": "End-point entity (no children) - likely data files or final results",
        }
    else:
        return {
            "position": "intermediate",
            "description": "Intermediate entity in the data hierarchy - connects other entities",
        }


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
