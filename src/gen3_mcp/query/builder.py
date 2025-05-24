"""GraphQL query building service"""

import logging
from typing import List, Dict, Any
from ..schema.service import SchemaService

logger = logging.getLogger("gen3-mcp.query")


class QueryBuilder:
    """Intelligent GraphQL query construction"""

    def __init__(self, schema_service: SchemaService):
        self.schema_service = schema_service

    async def build_safe_query(
        self, entity_name: str, field_count: int = 15, record_limit: int = 10
    ) -> str:
        """Build a safe query with validated fields"""
        schema = await self.schema_service.get_entity_schema(entity_name)
        fields = await self._select_optimal_fields(schema, field_count)

        query = f"""
        {{
            {entity_name}(first: {record_limit}) {{
{self._format_fields(fields)}
            }}
        }}
        """

        logger.debug(f"Built safe query for {entity_name} with {len(fields)} fields")
        return query.strip()

    async def build_field_sampling_query(
        self, entity_name: str, field_name: str, limit: int = 100
    ) -> str:
        """Build query for sampling field values"""
        # Validate field exists
        schema = await self.schema_service.get_entity_schema(entity_name)
        properties = schema.get("properties", {})

        if field_name not in properties:
            # Check if it's a relationship field
            valid_fields = self._get_all_valid_fields(schema)
            if field_name not in valid_fields:
                from ..exceptions import FieldNotFoundError

                raise FieldNotFoundError(
                    f"Field '{field_name}' not found in '{entity_name}'"
                )

        query = f"""
        {{
            {entity_name}(first: {limit}) {{
                {field_name}
            }}
        }}
        """

        logger.debug(f"Built field sampling query for {entity_name}.{field_name}")
        return query.strip()

    async def _select_optimal_fields(
        self, schema: Dict[str, Any], max_count: int
    ) -> List[str]:
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

    def _get_all_valid_fields(self, schema: Dict[str, Any]) -> set[str]:
        """Get all valid field names including relationships"""
        valid_fields = set(schema.get("properties", {}).keys())

        # Add common GraphQL fields
        valid_fields.update(
            ["id", "type", "submitter_id", "created_datetime", "updated_datetime"]
        )

        # Add relationship fields from links
        links = schema.get("links", [])
        for link in links:
            if isinstance(link, dict):
                if "name" in link:
                    valid_fields.add(link["name"])
                elif "subgroup" in link:
                    for sublink in link["subgroup"]:
                        if isinstance(sublink, dict) and "name" in sublink:
                            valid_fields.add(sublink["name"])

        return valid_fields

    def _format_fields(self, fields: List[str], indent: str = "        ") -> str:
        """Format fields for GraphQL query"""
        return "\n".join(f"{indent}{field}" for field in fields)
