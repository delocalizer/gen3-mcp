"""
Extract from full Gen3 schema. The two main purposes are to:
1. make relationships explicit to facilitate GraphQL query validation.
2. add schema annotations for consumption as context by MCP tools.
"""

import logging
from typing import Any

from .models import (
    EntitySchema,
    EntitySummary,
    Property,
    Relationship,
    RelType,
    SchemaExtract,
    Type,
)

logger = logging.getLogger("gen3-mcp.schema_extract")


async def get_schema_extract(full_schema: dict[str, Any]) -> SchemaExtract:
    """Extract annotated validation schema from full Gen3 schema.

    Args:
        full_schema: Full Gen3 schema dict.

    Returns:
        SchemaExtract instance.
    """
    logger.debug("Creating new schema extract")

    # Create new extract
    extract = SchemaExtract()
    relationships = []

    for entity_name, entity_def in full_schema.items():
        # Skip special keys
        if entity_name.startswith("_") or entity_name == "metaschema":
            continue

        # Extract relationships from links
        links = [link for link in entity_def.get("links", []) if "subgroup" not in link]
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
                    )
                )

        # Extract scalar fields from properties
        fields = {}
        for prop_name, prop_def in entity_def.get("properties", {}).items():
            # skip relationship fields
            if prop_name in links:
                continue
            prop = None
            if "type" in prop_def:
                prop = Property(name=prop_name, type_=Type(prop_def["type"]))
            elif "anyOf" in prop_def:
                prop = Property(name=prop_name, type_=Type.ANYOF)
            elif "oneOf" in prop_def:
                prop = Property(name=prop_name, type_=Type.ONEOF)
            elif "enum" in prop_def:
                prop = Property(
                    name=prop_name, type_=Type.ENUM, enum_vals=prop_def["enum"]
                )
            else:
                logger.error(f"Unhandled type of {prop_name} in {entity_name}")
            if prop:
                fields[prop_name] = prop

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
        parent_count = sum(
            1
            for rel in entity.relationships.values()
            if rel.link_type == RelType.CHILD_OF
        )
        child_count = sum(
            1
            for rel in entity.relationships.values()
            if rel.link_type == RelType.PARENT_OF
        )
        enum_fields = [
            field.name for field in entity.fields.values() if field.type_ == Type.ENUM
        ]

        entity_def = full_schema.get(entity_name)
        entity.schema_summary = EntitySummary(
            title=entity_def.get("title", ""),
            description=entity_def.get("description", ""),
            category=entity_def.get("category", ""),
            required_fields=entity_def.get("required", []),
            enum_fields=enum_fields,
            field_count=len(entity.fields),
            parent_count=parent_count,
            child_count=child_count,
        )

    return extract


# def _create_query_patterns(entity: EntitySchema) -> QueryPatterns:
#    """Create GraphQL query patterns for an entity.
#
#    Args:
#        entity: The EntitySchema instance.
#
#    Returns:
#        QueryPatterns instance with query examples.
#    """
#    entity_name = entity.name
#
#    # Basic query with core fields
#    basic_query = f"""{{
#    {entity_name}(first: 10) {{
#        id
#        submitter_id
#        type
#    }}
# }}"""
#
#    # Relationship query examples
#    relationship_examples = []
#
#    # Get parent relationships (CHILD_OF means this entity links TO parents)
#    parent_rels = [
#        rel
#        for rel in entity.relationships.values()
#        if rel.link_type == RelType.CHILD_OF
#    ]
#
#    # Get child relationships (PARENT_OF means children link TO this entity)
#    child_rels = [
#        rel
#        for rel in entity.relationships.values()
#        if rel.link_type == RelType.PARENT_OF
#    ]
#
#    # Add parent relationship examples (limit to 2)
#    for rel in sorted(parent_rels, key=lambda r: r.target_type)[:2]:
#        relationship_examples.append(
#            RelationshipQueryExample(
#                description=f"Get {entity_name} with linked parent {rel.target_type} data",
#                query=f"""{{
#    {entity_name}(first: 5) {{
#        id
#        submitter_id
#        {rel.name} {{
#            id
#            submitter_id
#        }}
#    }}
# }}""",
#            )
#        )
#
#    # Add child relationship examples (limit to 2)
#    for rel in sorted(child_rels, key=lambda r: r.target_type)[:2]:
#        relationship_examples.append(
#            RelationshipQueryExample(
#                description=f"Get {entity_name} with linked child {rel.target_type} data",
#                query=f"""{{
#    {entity_name}(first: 5) {{
#        id
#        submitter_id
#        {rel.name} {{
#            id
#            submitter_id
#        }}
#    }}
# }}""",
#            )
#        )
#
#    # Add parent + child query if entity has both parents and children
#    if parent_rels and child_rels:
#        # Take the first parent and first child for the combined query
#        parent_rel = parent_rels[0]
#        child_rel = child_rels[0]
#
#        combined_query = f"""{{
#    {entity_name}(first: 5) {{
#        id
#        submitter_id
#        {parent_rel.name} {{
#            id
#            submitter_id
#        }}
#        {child_rel.name} {{
#            id
#            submitter_id
#        }}
#    }}
# }}"""
#        relationship_examples.append(
#            RelationshipQueryExample(
#                description=f"Get {entity_name} with parent {parent_rel.target_type} and child {child_rel.target_type} data",
#                query=combined_query,
#            )
#        )
#
#    return QueryPatterns(basic_query=basic_query, complex_queries=relationship_examples)
