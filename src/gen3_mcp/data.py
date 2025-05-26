"""Service providing Gen3 data and schema operations"""

import logging
import time
from typing import Any

from .client import Gen3Client
from .config import Gen3Config
from .exceptions import Gen3SchemaError

logger = logging.getLogger("gen3-mcp.data")


class Gen3Service:
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

    async def get_full_schema(self) -> dict[str, Any]:
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

    async def get_entity_schema(self, entity_name: str) -> dict[str, Any]:
        """Get single entity schema (a top-level key in full schema)"""
        full_schema = await self.get_full_schema()
        try:
            return full_schema[entity_name]
        except KeyError as ke:
            raise Gen3SchemaError from ke

#    async def get_entity_names(self) -> list[str]:
#        """Get list of all entity names"""
#        full_schema = await self.get_full_schema()
#        return list(full_schema.keys())
#
#    async def get_schema_summary(self) -> dict[str, Any]:
#        """Generate schema summary from cached data"""
#        entities = await self.get_entity_names()
#        full_schema = await self.get_full_schema()
#
#        # Group by category
#        by_category = {}
#        total_relationships = 0
#
#        for name, schema in full_schema.items():
#            category = schema.get("category", "uncategorized")
#            if category not in by_category:
#                by_category[category] = []
#            by_category[category].append(name)
#
#            # Count relationships
#            links = schema.get("links", [])
#            for link in links:
#                if isinstance(link, dict):
#                    if "subgroup" in link:
#                        total_relationships += len(link.get("subgroup", []))
#                    else:
#                        total_relationships += 1
#
#        return {
#            "endpoint": self.config.base_url,
#            "total_entities": len(entities),
#            "entity_names": entities,
#            "entities_by_category": by_category,
#            "total_relationships": total_relationships,
#            "schema_url": self.config.schema_url,
#        }

    async def get_detailed_entities(self) -> dict[str, Any]:
        """Get detailed entity list with relationships"""
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

    async def get_entity_context(self, entity_name: str) -> dict[str, Any]:
        """
        Get comprehensive context about an entity including its hierarchical position.
        
        Returns:
        - Entity schema details
        - Entities that link TO this entity (parents/upstream)
        - Entities that this entity links TO (children/downstream)  
        - Backref names for GraphQL queries
        - Common query patterns
        """
        try:
            schema = await self.get_entity_schema(entity_name)
        except Gen3SchemaError:
            # Entity doesn't exist
            full_schema = await self.get_full_schema()
            return {
                "entity_name": entity_name,
                "exists": False,
                "error": f"Entity '{entity_name}' does not exist",
                "available_entities": list(full_schema.keys()),
                "suggestions": self._get_entity_name_suggestions(entity_name, full_schema)
            }
        
        full_schema = await self.get_full_schema()
        
        # Find entities this entity links TO (children/downstream)
        children = []
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
                                "link_name": sublink.get("name")
                            }
                            children.append(child_info)
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
                        "link_name": link.get("name")
                    }
                    children.append(child_info)
                    if link.get("backref"):
                        backref_fields.append(link.get("backref"))
        
        # Find entities that link TO this entity (parents/upstream)
        parents = []
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
                            if isinstance(sublink, dict) and sublink.get("target_type") == entity_name:
                                parent_info = {
                                    "entity": other_entity_name,
                                    "relationship": sublink.get("label", "related_to"),
                                    "multiplicity": sublink.get("multiplicity", "unknown"),
                                    "required": sublink.get("required", False),
                                    "backref_field": sublink.get("backref"),
                                    "link_name": sublink.get("name")
                                }
                                parents.append(parent_info)
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
                                "link_name": link.get("name")
                            }
                            parents.append(parent_info)
                            if link.get("backref"):
                                available_as_backref.append(link.get("backref"))
        
        # Generate common query patterns
        query_patterns = self._generate_query_patterns(entity_name, parents, children)
        
        return {
            "entity_name": entity_name,
            "exists": True,
            "schema_summary": {
                "title": schema.get("title", ""),
                "description": schema.get("description", ""),
                "category": schema.get("category", ""),
                "total_properties": len(schema.get("properties", {})),
                "required_fields": schema.get("required", [])
            },
            "hierarchical_position": {
                "parents": parents,  # Entities that link to this one
                "children": children,  # Entities this one links to
                "parent_count": len(parents),
                "child_count": len(children)
            },
            "graphql_fields": {
                "backref_fields": list(set(backref_fields)),  # Fields available when linking FROM this entity
                "available_as_backref": list(set(available_as_backref)),  # This entity available as backref field
                "direct_fields": list(schema.get("properties", {}).keys()),
                "system_fields": ["id", "submitter_id", "type", "created_datetime", "updated_datetime"]
            },
            "query_patterns": query_patterns,
            "data_flow_position": self._determine_data_flow_position(parents, children)
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
        self, entity_name: str, limit: int = 5, max_fields: int = 15
    ) -> dict[str, Any]:
        """Get sample records for entity"""
        # Get schema to select fields intelligently
        schema = await self.get_entity_schema(entity_name)
        fields = self._select_optimal_fields(schema, max_fields)

        # Build query
        fields_str = "\n        ".join(fields)
        query = f"""
        {{
            {entity_name}(first: {limit}) {{
                {fields_str}
            }}
        }}
        """

        # NOTE: as a one-time thing here we use the client.post_json directly
        # rather than query.QueryService to avoid a circular dependency. If
        # this service class ends up with more of these types of data methods
        # a redesign should be considered.
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

    def clear_cache(self):
        """Clear all cached data"""
        self._cache.clear()
        self._cache_timestamps.clear()
        logger.info("Schema cache cleared")

    def _select_optimal_fields(
        self, schema: dict[str, Any], max_count: int
    ) -> list[str]:
        """Intelligent field selection prioritizing useful fields"""
        properties = schema.get("properties", {})

        # Start with essential fields
        fields = ["id", "submitter_id", "type"]

        # Build final field list 
        remaining_slots = max_count - len(fields)

        # Add enum fields (good for filtering)
        enum_fields = [
            name
            for name, prop in properties.items()
            if isinstance(prop, dict) and "enum" in prop
        ]
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

    def _get_entity_name_suggestions(self, entity_name: str, full_schema: dict[str, Any]) -> list[dict[str, Any]]:
        """Get suggestions for similar entity names using fuzzy matching"""
        from difflib import SequenceMatcher
        
        suggestions = []
        for available_entity in full_schema.keys():
            if not isinstance(full_schema[available_entity], dict):
                continue
                
            similarity = SequenceMatcher(
                None, entity_name.lower(), available_entity.lower()
            ).ratio()
            
            if similarity > 0.4:  # Threshold for suggestions
                suggestions.append({
                    "name": available_entity,
                    "similarity": similarity,
                    "category": full_schema[available_entity].get("category", "unknown")
                })
        
        # Sort by similarity, return top 5
        return sorted(suggestions, key=lambda x: x["similarity"], reverse=True)[:5]

    def _generate_query_patterns(self, entity_name: str, parents: list, children: list) -> dict[str, Any]:
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
            "usage_examples": []
        }
        
        # Generate patterns with relationships
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
                    patterns["with_relationships"].append({
                        "description": f"Get {entity_name} with linked {child['entity']} data",
                        "query": example,
                        "target_entity": child["entity"]
                    })
        
        # Generate usage examples
        patterns["usage_examples"] = [
            f"Use {entity_name} as starting point for data exploration",
            f"Query {entity_name} fields: id, submitter_id, type"
        ]
        
        if children:
            patterns["usage_examples"].append(
                f"Access linked data via: {', '.join([c.get('backref_field', 'unknown') for c in children[:3] if c.get('backref_field')])}"
            )
        
        return patterns

    def _determine_data_flow_position(self, parents: list, children: list) -> dict[str, Any]:
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
            "description": self._get_position_description(position)
        }

    def _get_position_description(self, position: str) -> str:
        """Get a human-readable description of the entity's position"""
        descriptions = {
            "root": "Top-level entity (no parents) - likely administrative or entry point",
            "leaf": "End-point entity (no children) - likely data files or final results",
            "intermediate": "Intermediate entity in the data hierarchy - connects other entities"
        }
        return descriptions.get(position, "Unknown position")
