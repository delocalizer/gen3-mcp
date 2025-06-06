"""Manager providing Gen3 schema operations and caching."""

import logging
from functools import cache
from typing import Any

from .client import Gen3Client, get_client
from .models import (
    EntitySchema,
    EntitySummary,
    FieldType,
    Property,
    Relationship,
    RelType,
    Response,
    SchemaExtract,
)

logger = logging.getLogger("gen3-mcp.schema")


class SchemaManager:
    """Manager for cached schema operations and data access.

    Requires a client instance.
    """

    def __init__(self, client: Gen3Client):
        """Initialize SchemaManager.

        Args:
            client: Gen3Client instance for API calls.
        """
        self.client = client
        # Access config through client
        self.config = client.config
        self._cache = {}

    async def get_schema_full(self) -> Response:
        """Get full schema using config.schema_url.

        Returns:
            Response containing full schema dict with entity definitions,
            or error response if schema fetch fails.
        """
        cache_key = "full_schema"

        if cache_key in self._cache:
            logger.debug("Using cached full schema")
            return Response(
                status="success",
                message="Schema retrieved from cache",
                data=self._cache[cache_key],
            )

        logger.info(f"Fetching full schema from {self.config.schema_url}")
        response = await self.client.get_json(
            self.config.schema_url, authenticated=False
        )

        if not response.is_success:
            logger.error(f"Failed to fetch full schema: {response.message}")
            # Enhance error message for schema context and add schema-specific suggestions
            response.message = "Failed to fetch schema from Gen3 data commons"
            response.suggestions.extend(
                [
                    "Check that the Gen3 data commons URL is accessible",
                    "Verify your network connection",
                ]
            )
            return response

        # Success case - enhance message and cache the data
        schema = response.data
        logger.info("Fetched full schema")
        self._cache[cache_key] = schema
        response.message = "Schema fetched successfully from Gen3 data commons"
        return response

    async def get_schema_extract(self) -> Response:
        """Get processed schema extract with relationships and annotations.

        Returns:
            Response containing SchemaExtract instance with entity definitions,
            relationships, and schema summary information.
        """
        cache_key = "extract"

        if cache_key in self._cache:
            logger.debug("Using cached schema extract")
            return Response(
                status="success",
                message="Schema extract retrieved from cache",
                data=self._cache[cache_key],
            )

        logger.info("Creating new schema extract")

        # Get the full schema (returns Response)
        schema_response = await self.get_schema_full()
        if not schema_response.is_success:
            # Forward the error from get_schema_full
            schema_response.message = (
                "Failed to create schema extract - " + schema_response.message
            )
            return schema_response

        # Process it
        extract = self._create_extract(schema_response.data)

        logger.info("Created new schema extract")
        self._cache[cache_key] = extract

        return Response(
            status="success",
            message="Schema extract created successfully",
            data=extract,
        )

    def _create_extract(self, full_schema: dict[str, Any]) -> SchemaExtract:
        """Create SchemaExtract from full schema dict.

        Args:
            full_schema: Full Gen3 schema dict.

        Returns:
            SchemaExtract instance.
        """
        # Create new extract
        extract = SchemaExtract()
        relationships = []

        for entity_name, entity_def in full_schema.items():
            # Skip special keys
            if entity_name.startswith("_") or entity_name == "metaschema":
                continue

            # Extract relationships from links - combine direct and subgroup links
            links = [
                link for link in entity_def.get("links", []) if "subgroup" not in link
            ] + [
                sublink
                for link in entity_def.get("links", [])
                for sublink in link.get("subgroup", [])
            ]

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
            link_names = {link["name"] for link in links}

            # Extract scalar fields from properties
            fields = {}
            for prop_name, prop_def in entity_def.get("properties", {}).items():
                # skip relationship fields
                if prop_name in link_names:
                    continue
                prop = None
                if "type" in prop_def:
                    prop = Property(name=prop_name, type_=FieldType(prop_def["type"]))
                elif "anyOf" in prop_def:
                    prop = Property(name=prop_name, type_=FieldType.ANYOF)
                elif "oneOf" in prop_def:
                    prop = Property(name=prop_name, type_=FieldType.ONEOF)
                elif "enum" in prop_def:
                    prop = Property(
                        name=prop_name, type_=FieldType.ENUM, enum_vals=prop_def["enum"]
                    )
                else:
                    logger.error(f"Unhandled type of {prop_name} in {entity_name}")
                if prop:
                    fields[prop_name] = prop

            extract[entity_name] = EntitySchema(
                name=entity_name, fields=fields, relationships={}
            )

        # Add the collected relationships
        for rel in relationships:
            # Links might possibly reference types not actually defined in the
            # schema; these relationships are omitted so the result is closed.
            source = extract.get(rel.source_type)
            target = extract.get(rel.target_type)
            if not source:
                logger.info(f"Entity {rel.source_type} not found")
                continue
            elif not target:
                logger.info(f"Entity {rel.target_type} not found")
                continue
            source.relationships[rel.name] = rel

        # Add schema summary information and query patterns
        for entity_name, entity in extract.items():
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
                field.name
                for field in entity.fields.values()
                if field.type_ == FieldType.ENUM
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

    def clear_cache(self):
        """Clear all cached data. Useful for testing."""
        self._cache.clear()


@cache
def get_schema_manager() -> SchemaManager:
    """Get a cached SchemaManager instance."""
    return SchemaManager(get_client())
