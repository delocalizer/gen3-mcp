"""Service providing Gen3 schema operations and caching"""

import logging
import time
from typing import Any

from .client import Gen3Client
from .config import Gen3Config
from .exceptions import Gen3SchemaError

logger = logging.getLogger("gen3-mcp.schema")


class SchemaService:
    """
    Service for cached schema operations and data access.

    Requires a client and a config instance.
    """

    def __init__(self, client: Gen3Client, config: Gen3Config):
        self.client = client
        self.config = config
        self._cache = {}
        self._cache_timestamps = {}
        self.cache_ttl = config.schema_cache_ttl

    async def get_schema_full(self) -> dict[str, Any]:
        """
        Get full schema using config.schema_url.

        Top level keys may include common elements identified with a leading
        underscore, such as:
          "_definitions"
          "_settings"
          "_terms"
        as well as the individual entity schemas, for example:
            "sample"
            "study"
            "subject"
            etc.

        Within an entity there is information about what parent entities it
        links to, contained in the "links" array. For example in the "subject"
        entity, there may be a required link labelled 'member_of' to one or
        more study entities:

        "links": [
          {
            "backref": "subjects",
            "label": "member_of",
            "multiplicity": "many_to_many",
            "name": "studies",
            "required": true,
            "target_type": "study"
          }
        ]

        Within an entity there is information about the properties an instance
        may have, contained in the "properties" object. For example in the
        "sample" entity properties there may be a property about the sample
        preservation method, in this case an enum type:

        "preservation_method": {
          "description": "The text term that describes the method used to preserve the biospecimen after collection.",
          "enum": [
            "Cryopreserved",
            "FFPE",
            "Fresh",
            "Frozen",
            "Not Reported",
            "OCT",
            "Snap Frozen",
            "Unknown"
          ]
        }
        """
        cache_key = "full_schema"

        if self._is_cache_valid(cache_key):
            logger.debug("Using cached full schema")
            return self._cache[cache_key]

        logger.info("Fetching full schema from Gen3")
        schema = await self.client.get_json(self.config.schema_url, authenticated=False)

        if schema is None:
            raise Gen3SchemaError("Failed to fetch schema from Gen3")

        logger.info(f"Fetched schema with {len(schema)} entities")
        self._update_cache(cache_key, schema)
        return schema

    async def get_schema_summary(self) -> dict[str, Any]:
        """
        Generate schema summary using SchemaExtract
        """
        from .schema_extract import SchemaExtract

        cache_key = "schema_summary"

        if self._is_cache_valid(cache_key):
            logger.debug("Using cached schema summary")
            return self._cache[cache_key]

        full_schema = await self.get_schema_full()
        schema_extract = SchemaExtract.from_full_schema(full_schema)

        summary = {
            "total_entities": len(schema_extract.entities),
            "entities": {
                name: {
                    "fields_count": len(entity.fields),
                    "relationships_count": len(entity.relationships),
                    "fields": list(entity.fields),
                    "relationships": {
                        rel_name: rel.target_type
                        for rel_name, rel in entity.relationships.items()
                    },
                }
                for name, entity in schema_extract.entities.items()
            },
        }

        self._update_cache(cache_key, summary)
        return summary

    async def get_entity_context(self, entity_name: str) -> dict[str, Any]:
        """
        Get comprehensive context about an entity including its hierarchical position.

        Returns:
        - Entity schema details
        - Entities that link TO this entity (children/downstream)
        - Entities that this entity links TO (parents/upstream)
        - Backref names for GraphQL queries
        - Common query patterns
        """
        cache_key = f"{entity_name}_context"

        if self._is_cache_valid(cache_key):
            logger.debug(f"Using cached {entity_name} context")
            return self._cache[cache_key]

        full_schema = await self.get_schema_full()
        entity_schema = full_schema[entity_name]

        # entities this entity links TO (parents/upstream)
        parents = []
        # entities that link TO this entity (children/downstream)
        children = []
        available_as_backref = []

        for other_entity_name, schema in full_schema.items():
            links = [link for link in schema.get("links", []) if "subgroup" not in link]
            # Handle subgroup links (common in Gen3)
            links.extend(
                [
                    sublink
                    for link in schema.get("links",[])
                    for sublink in link.get("subgroup", [])
                ]
            )

            for link in links:
                # this entity links to ours (child)
                if link["target_type"] == entity_name:
                    children.append(
                        {
                            "entity": other_entity_name,
                            "link_name": link["backref"],
                            "relationship": link["label"],
                            "multiplicity": link["multiplicity"],
                        }
                    )
                    available_as_backref.append(link["backref"])
                # this is our entity; links are to parents
                elif other_entity_name == entity_name:
                    parents.append(
                        {
                            "entity": link["target_type"],
                            "link_name": link["name"],
                            "relationship": link["label"],
                            "multiplicity": link["multiplicity"],
                        }
                    )

        # Generate common query patterns
        query_patterns = self._generate_query_patterns(entity_name, parents, children)

        context = {
            "entity_name": entity_name,
            "exists": True,
            "schema_summary": {
                "title": entity_schema.get("title", ""),
                "description": entity_schema.get("description", ""),
                "category": entity_schema.get("category", ""),
                "total_properties": len(entity_schema.get("properties", {})),
                "required_fields": entity_schema.get("required", []),
            },
            "relationships": {
                "parents": sorted(
                    parents, key=lambda x: x["entity"]
                ),  # Entities that link to this one
                "children": sorted(
                    children, key=lambda x: x["entity"]
                ),  # Entities this one links to
                "parent_count": len(parents),
                "child_count": len(children),
                "position_description": self._get_position_description(
                    parents, children
                ),
            },
            "graphql_fields": {
                "available_as_backref": sorted(
                    set(available_as_backref)
                ),  # This entity available as backref field
                "direct_fields": sorted(entity_schema.get("properties", {}).keys()),
                "system_fields": [
                    "id",
                    "submitter_id",
                    "type",
                    "created_datetime",
                    "updated_datetime",
                ],
            },
            "query_patterns": query_patterns,
        }

        self._update_cache(cache_key, context)
        return context

    def _is_cache_valid(self, key: str) -> bool:
        """Check if cache entry is still valid"""
        if key not in self._cache:
            return False
        age = time.time() - self._cache_timestamps.get(key, 0)
        return age < self.cache_ttl

    def _update_cache(self, key: str, value: Any):
        """Update cache with new value and timestamp"""
        self._cache[key] = value
        self._cache_timestamps[key] = time.time()
        logger.debug(f"Cached {key}")

    def _generate_query_patterns(
        self, entity_name: str, parents: list, children: list
    ) -> dict[str, Any]:
        """Generate common GraphQL query patterns for this entity"""
        patterns = {
            "basic_query": f"""{{
    {entity_name}(first: 10) {{
        id
        submitter_id
        type
    }}
}}""",
            "with_relationships": [],
            "usage_examples": [],
        }

        # Generate query patterns with relationships for parents and children

        # 1. Generate patterns for parent relationships (entities this entity links TO)
        if parents:
            for _i, parent in enumerate(parents[:2]):  # Limit to 2 examples
                link_name = parent.get("link_name")
                if link_name:
                    example = f"""{{
    {entity_name}(first: 5) {{
        id
        submitter_id
        {link_name} {{
            id
            submitter_id
        }}
    }}
}}"""
                    pattern_info = {
                        "description": f"Get {entity_name} with linked {parent['entity']} data",
                        "query": example,
                        "target_entity": parent["entity"],
                    }
                    patterns["with_relationships"].append(pattern_info)

        # 2. Generate patterns for child relationships (entities that link TO this entity)
        if children:
            for child in children[:2]:  # Limit to 2 examples
                if child.get("link_name"):
                    example = f"""{{
    {entity_name}(first: 5) {{
        id
        submitter_id
        {child['link_name']} {{
            id
            submitter_id
        }}
    }}
}}"""
                    pattern_info = {
                        "description": f"Get {entity_name} with linked {child['entity']} data",
                        "query": example,
                        "target_entity": child["entity"],
                    }
                    patterns["with_relationships"].append(pattern_info)

        # Generate usage examples
        patterns["usage_examples"] = [
            f"Use {entity_name} as starting point for data exploration",
            f"Query {entity_name} fields: id, submitter_id, type",
        ]

        # Include relationship fields in usage examples
        relationship_fields = []
        if parents:
            parent_fields = [p.get("link_name") for p in parents if p.get("link_name")]
            relationship_fields.extend(parent_fields)
        if children:
            child_fields = [c.get("link_name") for c in children if c.get("link_name")]
            relationship_fields.extend(child_fields)

        if relationship_fields:
            patterns["usage_examples"].append(
                f"Access linked data via: {', '.join(relationship_fields[:3])}"
            )

        return patterns

    def _get_position_description(
        self, parents: list, children: list
    ) -> dict[str, Any]:
        """Determine the entity's position in the typical data flow"""
        # Determine position
        position = "intermediate"
        description = (
            "Intermediate entity in the data hierarchy - connects other entities"
        )
        if not parents:
            position = "root"
            description = (
                "Top-level entity (no parents) - likely administrative or entry point"
            )
        elif not children:
            position = "leaf"
            description = (
                "End-point entity (no children) - likely data files or final results"
            )

        return {
            "position": position,
            "description": description,
        }
