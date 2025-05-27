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
        try:
            schema = full_schema[entity_name]
        except KeyError as ke:
            raise Gen3SchemaError from ke

        # Find entities this entity links TO (parents/upstream)
        parents = []
        backref_fields = []

        links = schema.get("links", [])
        for link in links:
            if isinstance(link, dict):
                # Handle subgroup links (common in Gen3)
                if "subgroup" in link:
                    for sublink in link.get("subgroup", []):
                        if isinstance(sublink, dict):
                            child_info = {
                                "entity": sublink.get("target_type"),
                                "relationship": sublink.get("label", "related_to"),
                                "multiplicity": sublink.get("multiplicity", "unknown"),
                                "required": sublink.get("required", False),
                                "backref_field": sublink.get("backref"),
                                "link_name": sublink.get("name"),
                            }
                            parents.append(child_info)
                            if sublink.get("backref"):
                                backref_fields.append(sublink.get("backref"))
                else:
                    # Direct link
                    child_info = {
                        "entity": link.get("target_type"),
                        "relationship": link.get("label", "related_to"),
                        "multiplicity": link.get("multiplicity", "unknown"),
                        "required": link.get("required", False),
                        "backref_field": link.get("backref"),
                        "link_name": link.get("name"),
                    }
                    parents.append(child_info)
                    if link.get("backref"):
                        backref_fields.append(link.get("backref"))

        # Find entities that link TO this entity (children/downstream)
        children = []
        available_as_backref = []

        for other_entity_name, other_schema in full_schema.items():
            if not isinstance(other_schema, dict):
                continue

            other_links = other_schema.get("links", [])
            for link in other_links:
                if isinstance(link, dict):
                    # Handle subgroup links
                    if "subgroup" in link:
                        for sublink in link.get("subgroup", []):
                            if (
                                isinstance(sublink, dict)
                                and sublink.get("target_type") == entity_name
                            ):
                                parent_info = {
                                    "entity": other_entity_name,
                                    "relationship": sublink.get("label", "related_to"),
                                    "multiplicity": sublink.get(
                                        "multiplicity", "unknown"
                                    ),
                                    "required": sublink.get("required", False),
                                    "backref_field": sublink.get("backref"),
                                    "link_name": sublink.get("name"),
                                }
                                children.append(parent_info)
                                if sublink.get("backref"):
                                    available_as_backref.append(sublink.get("backref"))
                    else:
                        # Direct link
                        if link.get("target_type") == entity_name:
                            parent_info = {
                                "entity": other_entity_name,
                                "relationship": link.get("label", "related_to"),
                                "multiplicity": link.get("multiplicity", "unknown"),
                                "required": link.get("required", False),
                                "backref_field": link.get("backref"),
                                "link_name": link.get("name"),
                            }
                            children.append(parent_info)
                            if link.get("backref"):
                                available_as_backref.append(link.get("backref"))

        # Generate common query patterns
        query_patterns = self._generate_query_patterns(entity_name, parents, children)

        context = {
            "entity_name": entity_name,
            "exists": True,
            "schema_summary": {
                "title": schema.get("title", ""),
                "description": schema.get("description", ""),
                "category": schema.get("category", ""),
                "total_properties": len(schema.get("properties", {})),
                "required_fields": schema.get("required", []),
            },
            "hierarchical_position": {
                "parents": sorted(
                    parents, key=lambda x: x["entity"]
                ),  # Entities that link to this one
                "children": sorted(
                    children, key=lambda x: x["entity"]
                ),  # Entities this one links to
                "parent_count": len(parents),
                "child_count": len(children),
            },
            "graphql_fields": {
                "backref_fields": sorted(
                    set(backref_fields)
                ),  # Fields available when linking FROM this entity
                "available_as_backref": sorted(
                    set(available_as_backref)
                ),  # This entity available as backref field
                "direct_fields": sorted(schema.get("properties", {}).keys()),
                "system_fields": [
                    "id",
                    "submitter_id",
                    "type",
                    "created_datetime",
                    "updated_datetime",
                ],
            },
            "query_patterns": query_patterns,
            "data_flow_position": self._determine_data_flow_position(parents, children),
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
                if child.get("backref_field"):
                    example = f"""{{
    {entity_name}(first: 5) {{
        id
        submitter_id
        {child['backref_field']} {{
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
            child_fields = [
                c.get("backref_field") for c in children if c.get("backref_field")
            ]
            relationship_fields.extend(child_fields)

        if relationship_fields:
            patterns["usage_examples"].append(
                f"Access linked data via: {', '.join(relationship_fields[:3])}"
            )

        return patterns

    def _determine_data_flow_position(
        self, parents: list, children: list
    ) -> dict[str, Any]:
        """Determine the entity's position in the typical data flow"""
        # Determine position
        position = "intermediate"
        if not parents:
            position = "root"
        elif not children:
            position = "leaf"

        return {
            "position": position,
            "parent_count": len(parents),
            "child_count": len(children),
            "description": self._get_position_description(position),
        }

    def _get_position_description(self, position: str) -> str:
        """Get a human-readable description of the entity's position"""
        descriptions = {
            "root": "Top-level entity (no parents) - likely administrative or entry point",
            "leaf": "End-point entity (no children) - likely data files or final results",
            "intermediate": "Intermediate entity in the data hierarchy - connects other entities",
        }
        return descriptions.get(position, "Unknown position")
