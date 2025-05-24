"""Gen3 service for schema and core operations"""

import logging
import time
from typing import Any

from .client import Gen3Client
from .config import Gen3Config
from .exceptions import Gen3SchemaError

logger = logging.getLogger("gen3-mcp.service")


class Gen3Service:
    """Service for cached schema operations and data access"""

    def __init__(self, client: Gen3Client, config: Gen3Config):
        self.client = client
        self.config = config
        self._cache = {}
        self._cache_timestamps = {}
        self.cache_ttl = config.schema_cache_ttl

    async def get_full_schema(self) -> dict[str, Any]:
        """Get full schema using config.schema_url"""
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

    async def get_entity_schema(self, entity_name: str) -> dict[str, Any]:
        """Get single entity schema using config.entity_schema_url()"""
        cache_key = f"entity_schema:{entity_name}"

        if self._is_cache_valid(cache_key):
            logger.debug(f"Using cached schema for entity '{entity_name}'")
            return self._cache[cache_key]

        logger.debug(f"Fetching schema for entity '{entity_name}'")
        entity_url = self.config.entity_schema_url(entity_name)
        schema = await self.client.get_json(entity_url, authenticated=False)

        if schema is None:
            raise Gen3SchemaError(f"Entity '{entity_name}' not found")

        self._update_cache(cache_key, schema)
        return schema

    async def get_entity_names(self) -> list[str]:
        """Get list of all entity names"""
        full_schema = await self.get_full_schema()
        return list(full_schema.keys())

    async def get_schema_summary(self) -> dict[str, Any]:
        """Generate schema summary from cached data"""
        entities = await self.get_entity_names()
        full_schema = await self.get_full_schema()

        # Group by category
        by_category = {}
        total_relationships = 0

        for name, schema in full_schema.items():
            category = schema.get("category", "uncategorized")
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(name)

            # Count relationships
            links = schema.get("links", [])
            for link in links:
                if isinstance(link, dict):
                    if "subgroup" in link:
                        total_relationships += len(link.get("subgroup", []))
                    else:
                        total_relationships += 1

        return {
            "endpoint": self.config.base_url,
            "total_entities": len(entities),
            "entity_names": entities,
            "entities_by_category": by_category,
            "total_relationships": total_relationships,
            "schema_url": self.config.schema_url,
        }

    async def get_detailed_entities(self) -> dict[str, Any]:
        """Get detailed entity list with relationships (backward compatibility)"""
        full_schema = await self.get_full_schema()

        entities = {}
        all_links = []

        for entity_name, entity_data in full_schema.items():
            if isinstance(entity_data, dict):
                # Extract link information
                links = entity_data.get("links", [])
                processed_links = []

                for link in links:
                    if isinstance(link, dict):
                        # Handle subgroup links (common in Gen3)
                        if "subgroup" in link:
                            for sublink in link.get("subgroup", []):
                                if isinstance(sublink, dict):
                                    link_info = {
                                        "target_entity": sublink.get("target_type"),
                                        "relationship": sublink.get(
                                            "label", "related_to"
                                        ),
                                        "multiplicity": sublink.get(
                                            "multiplicity", "unknown"
                                        ),
                                        "required": sublink.get("required", False),
                                        "backref": sublink.get("backref"),
                                    }
                                    processed_links.append(link_info)
                                    all_links.append(
                                        {
                                            "from": entity_name,
                                            "to": sublink.get("target_type"),
                                            "relationship": sublink.get(
                                                "label", "related_to"
                                            ),
                                            "multiplicity": sublink.get(
                                                "multiplicity", "unknown"
                                            ),
                                        }
                                    )
                        else:
                            # Direct link
                            link_info = {
                                "target_entity": link.get("target_type"),
                                "relationship": link.get("label", "related_to"),
                                "multiplicity": link.get("multiplicity", "unknown"),
                                "required": link.get("required", False),
                                "backref": link.get("backref"),
                            }
                            processed_links.append(link_info)
                            all_links.append(
                                {
                                    "from": entity_name,
                                    "to": link.get("target_type"),
                                    "relationship": link.get("label", "related_to"),
                                    "multiplicity": link.get("multiplicity", "unknown"),
                                }
                            )

                entities[entity_name] = {
                    "title": entity_data.get("title", ""),
                    "description": entity_data.get("description", ""),
                    "category": entity_data.get("category", ""),
                    "properties_count": len(entity_data.get("properties", {})),
                    "links": processed_links,
                    "links_count": len(processed_links),
                }

        # Build relationship summary
        relationship_summary = {}
        for link in all_links:
            rel_type = link["relationship"]
            if rel_type not in relationship_summary:
                relationship_summary[rel_type] = []
            relationship_summary[rel_type].append(f"{link['from']} -> {link['to']}")

        # Find entities by category
        entities_by_category = {}
        for entity_name, entity_info in entities.items():
            category = entity_info["category"] or "uncategorized"
            if category not in entities_by_category:
                entities_by_category[category] = []
            entities_by_category[category].append(entity_name)

        return {
            "total_entities": len(entities),
            "entities": entities,
            "entities_by_category": entities_by_category,
            "relationship_summary": relationship_summary,
            "total_relationships": len(all_links),
            "common_graphql_patterns": {
                "hierarchical_query": "project -> study -> subject -> sample -> files",
                "file_with_subject": "Use links to query: file { subjects { age_at_enrollment sex } }",
                "subject_with_samples": "Use links to query: subject { samples { sample_type anatomic_site } }",
            },
        }

    async def explore_entity_data(self, entity_name: str) -> dict[str, Any]:
        """Comprehensive entity exploration"""
        schema = await self.get_entity_schema(entity_name)

        # Get sample records
        sample_result = await self.get_sample_records(entity_name, limit=3)

        # Analyze schema for enum fields and important fields
        properties = schema.get("properties", {})
        enum_fields = []
        important_fields = []

        for field_name, field_def in properties.items():
            if isinstance(field_def, dict):
                if "enum" in field_def:
                    enum_fields.append(
                        {"field": field_name, "enum_values": field_def["enum"]}
                    )

                # Mark fields that are likely important for filtering
                if any(
                    keyword in field_name.lower()
                    for keyword in [
                        "type",
                        "format",
                        "category",
                        "sex",
                        "race",
                        "status",
                    ]
                ):
                    important_fields.append(field_name)

        return {
            "entity": entity_name,
            "schema_info": {
                "title": schema.get("title", ""),
                "description": schema.get("description", ""),
                "category": schema.get("category", ""),
                "total_properties": len(properties),
                "required_fields": schema.get("required", []),
            },
            "enum_fields": enum_fields,
            "important_filtering_fields": important_fields,
            "sample_records": sample_result.get("sample_records", []),
        }

    async def get_sample_records(
        self, entity_name: str, limit: int = 5
    ) -> dict[str, Any]:
        """Get sample records for entity"""
        # Get schema to select fields intelligently
        schema = await self.get_entity_schema(entity_name)
        fields = self._select_optimal_fields(schema, 15)

        # Build query
        fields_str = "\n        ".join(fields)
        query = f"""
        {{
            {entity_name}(first: {limit}) {{
                {fields_str}
            }}
        }}
        """

        logger.info(f"Getting sample records for {entity_name}")
        result = await self.client.post_json(
            self.config.graphql_url,
            json={"query": query},
        )

        if not result or "data" not in result:
            return {
                "error": f"Failed to get sample records for {entity_name}",
                "query": query.strip(),
            }

        entity_data = result["data"].get(entity_name, [])

        return {
            "entity": entity_name,
            "total_records_returned": len(entity_data),
            "fields_queried": fields,
            "sample_records": entity_data,
            "query_used": query.strip(),
        }

    def _select_optimal_fields(
        self, schema: dict[str, Any], max_count: int
    ) -> list[str]:
        """Intelligent field selection prioritizing useful fields"""
        properties = schema.get("properties", {})

        # Start with essential fields
        fields = ["id", "submitter_id", "type"]

        # Add enum fields (good for filtering)
        enum_fields = [
            name
            for name, prop in properties.items()
            if isinstance(prop, dict) and "enum" in prop
        ]

        # Add priority fields
        priority_fields = ["created_datetime", "updated_datetime", "state"]

        # Build final field list
        remaining_slots = max_count - len(fields)

        # Add priority fields first
        for field in priority_fields:
            if field in properties and field not in fields and remaining_slots > 0:
                fields.append(field)
                remaining_slots -= 1

        # Add enum fields
        for field in enum_fields:
            if field not in fields and remaining_slots > 0:
                fields.append(field)
                remaining_slots -= 1

        # Fill with other fields, avoiding internal fields
        other_fields = [
            f for f in properties.keys() if f not in fields and not f.startswith("_")
        ][:remaining_slots]
        fields.extend(other_fields)

        logger.debug(
            f"Selected {len(fields)} optimal fields from {len(properties)} available"
        )
        return fields

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

    def clear_cache(self):
        """Clear all cached data"""
        self._cache.clear()
        self._cache_timestamps.clear()
        logger.info("Schema cache cleared")
