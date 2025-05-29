"""Service providing Gen3 schema operations and caching."""

import logging
import time
from typing import Any

from .client import Gen3Client
from .config import Gen3Config
from .exceptions import Gen3SchemaError

logger = logging.getLogger("gen3-mcp.schema")


class SchemaService:
    """Service for cached schema operations and data access.

    Requires a client and a config instance.
    """

    def __init__(self, client: Gen3Client, config: Gen3Config):
        """Initialize SchemaService.

        Args:
            client: Gen3Client instance for API calls.
            config: Gen3Config instance with settings.
        """
        self.client = client
        self.config = config
        self._cache = {}
        self._cache_timestamps = {}
        self.cache_ttl = config.schema_cache_ttl

    async def get_entity_context(self, entity_name: str) -> dict[str, Any]:
        """Get comprehensive context about an entity including its hierarchical position.

        Args:
            entity_name: Name of the entity to get context for.

        Returns:
            Dict containing entity schema details, relationships, GraphQL fields,
            and common query patterns.

        Raises:
            Gen3SchemaError: If schema fetch fails.
        """
        logger.debug(f"Getting entity context for: {entity_name}")
        cache_key = f"{entity_name}_context"

        if self._is_cache_valid(cache_key):
            logger.debug(f"Using cached {entity_name} context")
            return self._cache[cache_key]

        full_schema = await self.get_schema_full()
        entity_schema = full_schema[entity_name]

        # Build relationship data
        parents = []  # entities this entity links TO
        children = []  # entities that link TO this entity
        available_as_backref = []

        for other_entity_name, schema in full_schema.items():
            links = [link for link in schema.get("links", []) if "subgroup" not in link]
            # Handle subgroup links (common in Gen3)
            links.extend(
                [
                    sublink
                    for link in schema.get("links", [])
                    for sublink in link.get("subgroup", [])
                ]
            )

            for link in links:
                if link["target_type"] == entity_name:
                    # This entity links to ours (child)
                    children.append(
                        {
                            "entity": other_entity_name,
                            "link_name": link["backref"],
                            "relationship": link["label"],
                            "multiplicity": link["multiplicity"],
                        }
                    )
                    available_as_backref.append(link["backref"])
                elif other_entity_name == entity_name:
                    # This is our entity; links are to parents
                    parents.append(
                        {
                            "entity": link["target_type"],
                            "link_name": link["name"],
                            "relationship": link["label"],
                            "multiplicity": link["multiplicity"],
                        }
                    )

        # Generate query patterns
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
                "parents": sorted(parents, key=lambda x: x["entity"]),
                "children": sorted(children, key=lambda x: x["entity"]),
                "parent_count": len(parents),
                "child_count": len(children),
                "position_description": self._get_position_description(
                    parents, children
                ),
            },
            "graphql_fields": {
                "available_as_backref": sorted(set(available_as_backref)),
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
        logger.info(f"Entity context generated for: {entity_name}")
        return context

    async def get_schema_full(self) -> dict[str, Any]:
        """Get full schema using config.schema_url.

        Returns:
            Full schema dict with entity definitions. Top level keys may include
            common elements identified with a leading underscore (_definitions,
            _settings, _terms) as well as individual entity schemas.

        Raises:
            Gen3SchemaError: If schema fetch fails.
        """
        cache_key = "full_schema"

        if self._is_cache_valid(cache_key):
            logger.debug("Using cached full schema")
            return self._cache[cache_key]

        logger.info("Fetching full schema from Gen3")
        schema = await self.client.get_json(self.config.schema_url, authenticated=False)

        if schema is None:
            logger.error("Failed to fetch schema from Gen3")
            raise Gen3SchemaError("Failed to fetch schema from Gen3")

        logger.info(f"Fetched schema with {len(schema)} entities")
        self._update_cache(cache_key, schema)
        return schema

    async def get_schema_summary(self) -> dict[str, Any]:
        """Generate schema summary using SchemaExtract.

        Returns:
            Dict with total entities count and per-entity field/relationship info.

        Raises:
            Gen3SchemaError: If schema fetch fails.
        """
        logger.debug("Generating schema summary")
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
        logger.info(
            f"Schema summary generated with {len(schema_extract.entities)} entities"
        )
        return summary

    def _generate_query_patterns(
        self, entity_name: str, parents: list, children: list
    ) -> dict[str, Any]:
        """Generate common GraphQL query patterns for this entity.

        Args:
            entity_name: Name of the entity.
            parents: List of parent relationships.
            children: List of child relationships.

        Returns:
            Dict with basic query, relationship queries, and usage examples.
        """
        logger.debug(f"Generating query patterns for {entity_name}")

        patterns = {
            "basic_query": f"""{{
    {entity_name}(first: 10) {{
        id
        submitter_id
        type
    }}
}}""",
            "with_relationships": [],
            "usage_examples": [
                f"Use {entity_name} as starting point for data exploration",
                f"Query {entity_name} fields: id, submitter_id, type",
            ],
        }

        # Add parent relationship examples
        for parent in parents[:2]:  # Limit to 2 examples
            link_name = parent.get("link_name")
            if link_name:
                patterns["with_relationships"].append(
                    {
                        "description": f"Get {entity_name} with linked parent {parent['entity']} data",
                        "query": f"""{{
    {entity_name}(first: 5) {{
        id
        submitter_id
        {link_name} {{
            id
            submitter_id
        }}
    }}
}}""",
                        "target_entity": parent["entity"],
                    }
                )

        # Add child relationship examples
        for child in children[:2]:  # Limit to 2 examples
            link_name = child.get("link_name")
            if link_name:
                patterns["with_relationships"].append(
                    {
                        "description": f"Get {entity_name} with linked child {child['entity']} data",
                        "query": f"""{{
    {entity_name}(first: 5) {{
        id
        submitter_id
        {link_name} {{
            id
            submitter_id
        }}
    }}
}}""",
                        "target_entity": child["entity"],
                    }
                )

        # Add relationship fields to usage examples
        relationship_fields = [
            p.get("link_name") for p in parents if p.get("link_name")
        ] + [c.get("link_name") for c in children if c.get("link_name")]

        if relationship_fields:
            patterns["usage_examples"].append(
                f"Access linked data via: {', '.join(relationship_fields[:3])}"
            )

        return patterns

    def _get_position_description(
        self, parents: list, children: list
    ) -> dict[str, str]:
        """Determine the entity's position in the typical data flow.

        Args:
            parents: List of parent relationships.
            children: List of child relationships.

        Returns:
            Dict with position type and description.
        """
        if not parents:
            return {
                "position": "root",
                "description": "Top-level entity (no parents) - likely administrative or entry point",
            }
        elif not children:
            return {
                "position": "leaf",
                "description": "End-point entity (no children) - likely data files or final results",
            }
        else:
            return {
                "position": "intermediate",
                "description": "Intermediate entity in the data hierarchy - connects other entities",
            }

    def _is_cache_valid(self, key: str) -> bool:
        """Check if cache entry is still valid.

        Args:
            key: Cache key to check.

        Returns:
            True if cache is valid, False otherwise.
        """
        if key not in self._cache:
            return False

        age = time.time() - self._cache_timestamps.get(key, 0)
        return age < self.cache_ttl

    def _update_cache(self, key: str, value: Any) -> None:
        """Update cache with new value and timestamp.

        Args:
            key: Cache key.
            value: Value to cache.
        """
        self._cache[key] = value
        self._cache_timestamps[key] = time.time()
        logger.debug(f"Cached {key}")
