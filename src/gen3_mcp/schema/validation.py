"""Validation service consolidating all validation logic"""

import re
import logging
from typing import Dict, List, Any, Optional
from difflib import SequenceMatcher
from ..schema.service import SchemaService
from ..exceptions import FieldNotFoundError, QueryValidationError

logger = logging.getLogger("gen3-mcp.validation")


class ValidationService:
    """Consolidated validation logic with intelligent suggestions"""

    def __init__(self, schema_service: SchemaService):
        self.schema_service = schema_service

    async def validate_query_fields(self, query: str) -> Dict[str, Any]:
        """Validate all fields in a GraphQL query against the Gen3 schema"""
        logger.info("Validating GraphQL query fields")

        try:
            extracted_fields = self._extract_graphql_fields(query)
        except Exception as e:
            return {
                "valid": False,
                "error": f"Failed to parse GraphQL query: {e}",
                "extracted_fields": {},
                "validation_results": {},
            }

        validation_results = {}
        all_valid = True

        # Get list of valid entities
        try:
            valid_entities = set(await self.schema_service.get_entity_names())
        except Exception as e:
            return {
                "valid": False,
                "error": f"Failed to fetch entity list: {e}",
                "extracted_fields": extracted_fields,
                "validation_results": {},
            }

        for entity_name, fields in extracted_fields.items():
            entity_result = {
                "entity_exists": entity_name in valid_entities,
                "field_validation": {},
                "errors": [],
                "warnings": [],
            }

            if not entity_result["entity_exists"]:
                entity_result["errors"].append(f"Entity '{entity_name}' does not exist")
                all_valid = False

                # Suggest similar entity names
                suggestions = self._suggest_similar_entities(
                    entity_name, valid_entities
                )
                if suggestions:
                    entity_result["entity_suggestions"] = suggestions
            else:
                # Validate fields for this entity
                try:
                    schema = await self.schema_service.get_entity_schema(entity_name)
                    valid_fields = self._get_all_valid_fields(schema)

                    for field in fields:
                        field_valid = field in valid_fields
                        entity_result["field_validation"][field] = {
                            "valid": field_valid,
                            "suggestions": [],
                        }

                        if not field_valid:
                            entity_result["errors"].append(
                                f"Field '{field}' does not exist in entity '{entity_name}'"
                            )
                            all_valid = False

                            # Generate suggestions for invalid fields
                            suggestions = await self.suggest_similar_fields(
                                field, entity_name
                            )
                            entity_result["field_validation"][field]["suggestions"] = (
                                suggestions.get("suggestions", [])
                            )

                except Exception as e:
                    entity_result["errors"].append(
                        f"Failed to validate fields for entity '{entity_name}': {e}"
                    )
                    all_valid = False

            validation_results[entity_name] = entity_result

        return {
            "valid": all_valid,
            "extracted_fields": extracted_fields,
            "validation_results": validation_results,
            "summary": self._generate_validation_summary(validation_results),
        }

    async def suggest_similar_fields(
        self, field_name: str, entity_name: str
    ) -> Dict[str, Any]:
        """Suggest similar field names for a given field in an entity"""
        logger.debug(f"Suggesting similar fields for {field_name} in {entity_name}")

        try:
            # Check if entity exists
            valid_entities = set(await self.schema_service.get_entity_names())

            if entity_name not in valid_entities:
                # Suggest similar entity names
                entity_suggestions = self._suggest_similar_entities(
                    entity_name, valid_entities
                )

                return {
                    "field_name": field_name,
                    "entity_name": entity_name,
                    "entity_exists": False,
                    "suggestions": [],
                    "entity_suggestions": entity_suggestions,
                    "message": f"Entity '{entity_name}' does not exist. Consider these similar entities.",
                }

            # Get schema for the entity
            schema = await self.schema_service.get_entity_schema(entity_name)
            valid_fields = self._get_all_valid_fields(schema)

            # Calculate similarities
            suggestions = []
            for valid_field in valid_fields:
                similarity = self._similarity(field_name, valid_field)
                if similarity > 0.4:  # Threshold for suggestions
                    suggestions.append(
                        {
                            "name": valid_field,
                            "similarity": similarity,
                            "type": self._get_field_type(schema, valid_field),
                        }
                    )

            # Sort by similarity
            suggestions.sort(key=lambda x: x["similarity"], reverse=True)

            # Also check for common patterns
            pattern_suggestions = self._get_pattern_suggestions(
                field_name, valid_fields
            )

            return {
                "field_name": field_name,
                "entity_name": entity_name,
                "entity_exists": True,
                "suggestions": suggestions[:10],  # Top 10 suggestions
                "pattern_suggestions": pattern_suggestions,
                "total_valid_fields": len(valid_fields),
                "message": f"Found {len(suggestions)} similar fields for '{field_name}' in '{entity_name}'",
            }

        except Exception as e:
            return {
                "field_name": field_name,
                "entity_name": entity_name,
                "error": f"Failed to generate suggestions: {e}",
                "suggestions": [],
            }

    async def generate_query_template(
        self, entity_name: str, include_relationships: bool = True, max_fields: int = 20
    ) -> Dict[str, Any]:
        """Generate a safe GraphQL query template with only confirmed valid fields"""
        logger.info(f"Generating query template for {entity_name}")

        try:
            # Check if entity exists
            valid_entities = set(await self.schema_service.get_entity_names())

            if entity_name not in valid_entities:
                suggestions = self._suggest_similar_entities(
                    entity_name, valid_entities
                )
                return {
                    "entity_name": entity_name,
                    "exists": False,
                    "template": None,
                    "error": f"Entity '{entity_name}' does not exist",
                    "suggestions": suggestions,
                }

            # Get schema
            schema = await self.schema_service.get_entity_schema(entity_name)

            # Collect basic fields
            basic_fields = ["id", "submitter_id", "type"]

            # Add schema properties
            properties = schema.get("properties", {})
            schema_fields = []

            # Prioritize common and useful fields
            priority_fields = ["created_datetime", "updated_datetime", "state"]
            for field in priority_fields:
                if field in properties:
                    schema_fields.append(field)

            # Add enum fields (they're usually important for filtering)
            enum_fields = []
            for field_name, field_def in properties.items():
                if isinstance(field_def, dict) and "enum" in field_def:
                    enum_fields.append(
                        {"field": field_name, "enum_values": field_def["enum"]}
                    )

            for enum_field in enum_fields:
                field_name = enum_field.get("field")
                if (
                    field_name
                    and field_name not in basic_fields
                    and field_name not in schema_fields
                ):
                    schema_fields.append(field_name)

            # Add other properties (limited by max_fields)
            remaining_slots = max_fields - len(basic_fields) - len(schema_fields)
            other_fields = [
                f
                for f in properties.keys()
                if f not in basic_fields
                and f not in schema_fields
                and not f.startswith("_")
            ][:remaining_slots]

            schema_fields.extend(other_fields)

            # Collect relationship fields
            relationship_fields = []
            if include_relationships:
                links = schema.get("links", [])
                for link in links:
                    if isinstance(link, dict):
                        if "name" in link:
                            relationship_fields.append(
                                {
                                    "name": link["name"],
                                    "target_type": link.get("target_type"),
                                    "multiplicity": link.get("multiplicity"),
                                    "required": link.get("required", False),
                                }
                            )
                        elif "subgroup" in link:
                            for sublink in link["subgroup"]:
                                if "name" in sublink:
                                    relationship_fields.append(
                                        {
                                            "name": sublink["name"],
                                            "target_type": sublink.get("target_type"),
                                            "multiplicity": sublink.get("multiplicity"),
                                            "required": sublink.get("required", False),
                                        }
                                    )

            # Generate the template
            template_fields = basic_fields + schema_fields

            template = f"{entity_name}(first: 10) {{\n"
            for field in template_fields:
                template += f"    {field}\n"

            # Add relationship examples
            if relationship_fields:
                template += "    \n    # Relationship fields (uncomment as needed):\n"
                for rel in relationship_fields[:5]:  # Limit to 5 examples
                    template += f"    # {rel['name']} {{\n"
                    template += f"    #     id\n"
                    template += f"    #     submitter_id\n"
                    template += f"    # }}\n"

            template += "}"

            # Generate full query wrapper
            full_template = "{\n    " + template.replace("\n", "\n    ") + "\n}"

            return {
                "entity_name": entity_name,
                "exists": True,
                "template": full_template,
                "basic_fields": basic_fields,
                "schema_fields": schema_fields,
                "relationship_fields": relationship_fields,
                "total_fields": len(template_fields),
                "enum_fields": [ef.get("field") for ef in enum_fields],
                "required_fields": schema.get("required", []),
                "description": schema.get("description", ""),
                "category": schema.get("category", ""),
                "usage_notes": self._generate_usage_notes(
                    entity_name, schema, enum_fields
                ),
            }

        except Exception as e:
            logger.error(f"Failed to generate template for {entity_name}: {e}")
            return {
                "entity_name": entity_name,
                "exists": False,
                "template": None,
                "error": f"Failed to generate template: {e}",
            }

    def _extract_graphql_fields(self, query: str) -> Dict[str, List[str]]:
        """Extract entity names and their requested fields from a GraphQL query"""
        # Remove comments and normalize whitespace
        query = re.sub(r"#.*$", "", query, flags=re.MULTILINE)
        query = re.sub(r"\s+", " ", query).strip()

        # Find all entity queries like "entity_name { field1 field2 { subfield } }"
        entity_pattern = r"(\w+)\s*(?:\([^)]*\))?\s*\{"
        matches = re.finditer(entity_pattern, query)

        result = {}

        for match in matches:
            entity_name = match.group(1)
            if entity_name in ["query", "mutation", "subscription"]:
                continue

            # Find the matching closing brace for this entity
            start_pos = match.end() - 1  # Position of opening brace
            brace_count = 1
            pos = start_pos + 1

            while pos < len(query) and brace_count > 0:
                if query[pos] == "{":
                    brace_count += 1
                elif query[pos] == "}":
                    brace_count -= 1
                pos += 1

            if brace_count == 0:
                # Extract fields within this entity block
                entity_content = query[start_pos + 1 : pos - 1]
                fields = self._extract_fields_from_content(entity_content)
                result[entity_name] = fields

        return result

    def _extract_fields_from_content(self, content: str) -> List[str]:
        """Extract field names from entity content, handling nested structures"""
        fields = []

        # Split by whitespace and filter for valid field names
        tokens = content.split()

        for token in tokens:
            # Remove common GraphQL syntax
            token = token.strip("{}(),")

            # Skip empty tokens, arguments, and comments
            if not token or token.startswith("(") or token.startswith("#"):
                continue

            # Extract field name (before any arguments or nested structures)
            field_match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)", token)
            if field_match:
                field_name = field_match.group(1)
                # Skip GraphQL keywords
                if field_name not in [
                    "query",
                    "mutation",
                    "subscription",
                    "fragment",
                    "on",
                ]:
                    fields.append(field_name)

        return list(set(fields))  # Remove duplicates

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

    def _similarity(self, a: str, b: str) -> float:
        """Calculate similarity between two strings"""
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    def _suggest_similar_entities(
        self, entity_name: str, valid_entities: set[str]
    ) -> List[Dict[str, Any]]:
        """Suggest similar entity names"""
        suggestions = []
        for valid_entity in valid_entities:
            similarity = self._similarity(entity_name, valid_entity)
            if similarity > 0.6:
                suggestions.append({"name": valid_entity, "similarity": similarity})

        suggestions.sort(key=lambda x: x["similarity"], reverse=True)
        return suggestions[:5]

    def _get_field_type(self, schema: Dict[str, Any], field_name: str) -> str:
        """Get the type of a field from schema"""
        properties = schema.get("properties", {})
        if field_name in properties:
            field_def = properties[field_name]
            if isinstance(field_def, dict):
                return field_def.get("type", "unknown")

        # Check if it's a relationship field
        links = schema.get("links", [])
        for link in links:
            if isinstance(link, dict):
                if link.get("name") == field_name:
                    return f"relationship -> {link.get('target_type', 'unknown')}"
                elif "subgroup" in link:
                    for sublink in link["subgroup"]:
                        if sublink.get("name") == field_name:
                            return f"relationship -> {sublink.get('target_type', 'unknown')}"

        return "unknown"

    def _get_pattern_suggestions(
        self, field_name: str, valid_fields: set[str]
    ) -> List[str]:
        """Get suggestions based on common naming patterns"""
        patterns = []

        # Common field patterns
        if "name" in field_name.lower():
            patterns.extend(
                [f for f in valid_fields if "name" in f.lower() or f.endswith("_name")]
            )

        if "type" in field_name.lower():
            patterns.extend(
                [f for f in valid_fields if "type" in f.lower() or f.endswith("_type")]
            )

        if "id" in field_name.lower():
            patterns.extend(
                [f for f in valid_fields if "id" in f.lower() or f.endswith("_id")]
            )

        if "date" in field_name.lower() or "time" in field_name.lower():
            patterns.extend(
                [
                    f
                    for f in valid_fields
                    if any(x in f.lower() for x in ["date", "time", "datetime"])
                ]
            )

        return list(set(patterns))[:5]  # Remove duplicates and limit

    def _generate_validation_summary(
        self, validation_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate a summary of validation results"""
        total_entities = len(validation_results)
        valid_entities = sum(
            1 for result in validation_results.values() if result["entity_exists"]
        )

        total_fields = sum(
            len(result["field_validation"]) for result in validation_results.values()
        )
        valid_fields = sum(
            sum(
                1
                for field_result in result["field_validation"].values()
                if field_result["valid"]
            )
            for result in validation_results.values()
        )

        all_errors = []
        for entity_name, result in validation_results.items():
            all_errors.extend(result["errors"])

        return {
            "total_entities": total_entities,
            "valid_entities": valid_entities,
            "total_fields": total_fields,
            "valid_fields": valid_fields,
            "total_errors": len(all_errors),
            "errors": all_errors,
        }

    def _generate_usage_notes(
        self,
        entity_name: str,
        schema: Dict[str, Any],
        enum_fields: List[Dict[str, Any]],
    ) -> List[str]:
        """Generate helpful usage notes for the entity"""
        notes = []

        # Required fields note
        required = schema.get("required", [])
        if required:
            notes.append(f"Required fields: {', '.join(required)}")

        # Enum fields note
        if enum_fields:
            enum_names = [ef.get("field") for ef in enum_fields]
            notes.append(f"Fields with predefined values: {', '.join(enum_names)}")

        # Category note
        category = schema.get("category", "")
        if category:
            notes.append(f"Entity category: {category}")

        # Common patterns
        properties = schema.get("properties", {})
        if any("date" in prop or "time" in prop for prop in properties):
            notes.append("Contains datetime fields - useful for temporal queries")

        if any("file" in prop for prop in properties):
            notes.append(
                "Contains file-related fields - check file_size, file_name, etc."
            )

        return notes
