"""GraphQL Query service for validation, building, and execution"""

import logging
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from .client import Gen3Client
from .config import Gen3Config
from .data import Gen3Service
from .exceptions import QueryValidationError
from .graphql_parser import extract_query_fields, validate_graphql

logger = logging.getLogger("gen3-mcp.query")


@dataclass
class ValidationResult:
    """Result of field validation for an entity"""

    valid: bool
    field_validation: dict[str, Any]
    errors: list[str]
    warnings: list[str]
    entity_suggestions: list[dict[str, Any]] | None = None


@dataclass
class RelationshipInfo:
    """Information about an entity relationship"""

    name: str
    target_type: str
    multiplicity: str
    required: bool
    backref: str


class QueryService:
    """Query operations: validation, building, and execution"""

    def __init__(
        self, client: Gen3Client, config: Gen3Config, gen3_service: Gen3Service
    ):
        self.client = client
        self.config = config
        self.gen3_service = gen3_service

    async def execute_graphql(self, query: str) -> dict[str, Any] | None:
        """Execute GraphQL query using config.graphql_url"""
        logger.info("Executing GraphQL query")
        logger.debug(f"Query: {query[:200]}{'...' if len(query) > 200 else ''}")

        result = await self.client.post_json(
            self.config.graphql_url,
            json={"query": query},
        )

        if result is None:
            logger.error("GraphQL query execution failed")
            return {
                "error": "Query execution failed - network or server error",
                "suggestion": "Check your connection and try validate_query() to verify syntax before retrying",
            }

        # Check for GraphQL errors and provide enhanced guidance
        if "errors" in result:
            logger.warning(f"GraphQL query returned errors: {result['errors']}")

            # Analyze error types for better suggestions
            error_messages = [error.get("message", "") for error in result["errors"]]
            suggestions = []

            for error_msg in error_messages:
                if "field" in error_msg.lower() and "exist" in error_msg.lower():
                    suggestions.append(
                        "Use validate_query() to check field names, or suggest_fields() to find correct field names"
                    )
                elif "syntax" in error_msg.lower():
                    suggestions.append(
                        "Use query_template() to generate a syntactically correct starting template"
                    )
                elif "type" in error_msg.lower():
                    suggestions.append(
                        "Check entity names with schema_entities() or schema_describe_entities()"
                    )

            if suggestions:
                result["execution_guidance"] = {
                    "suggestions": list(set(suggestions)),  # Remove duplicates
                    "recommended_workflow": [
                        "1. Use validate_query() to check your query syntax and field names",
                        "2. If validation fails, use suggest_fields() to fix field name errors",
                        "3. If entity doesn't exist, use schema_entities() to see available entities",
                        "4. Consider starting with query_template() for a guaranteed valid template",
                    ],
                }

        return result

    async def field_sample(
        self, entity_name: str, field_name: str, limit: int = 100
    ) -> dict[str, Any]:
        """Execute query for field value sampling with processing"""
        query = f"""
        {{
            {entity_name}(first: {limit}) {{
                {field_name}
            }}
        }}
        """

        logger.info(f"Sampling field values for {entity_name}.{field_name}")
        result = await self.execute_graphql(query)

        if not result or "data" not in result:
            return {
                "error": f"Failed to fetch field values for {entity_name}.{field_name}",
                "query": query.strip(),
            }

        # Process field values
        entity_data = result["data"].get(entity_name, [])
        value_counts = {}

        for record in entity_data:
            value = record.get(field_name)
            if value is not None:
                value_str = str(value)
                value_counts[value_str] = value_counts.get(value_str, 0) + 1

        # Sort by frequency
        sorted_values = dict(
            sorted(value_counts.items(), key=lambda x: x[1], reverse=True)
        )

        logger.debug(f"Found {len(value_counts)} unique values for {field_name}")

        return {
            "entity": entity_name,
            "field": field_name,
            "total_records": len(entity_data),
            "unique_values": len(value_counts),
            "values": sorted_values,
            "query_used": query.strip(),
        }

    async def validate_query(self, query: str) -> dict[str, Any]:
        """Validate query syntax, then semantics of a GraphQL query against the Gen3 schema"""
        logger.info("Validating GraphQL query fields")

        # Validate GraphQL syntax
        is_valid_syntax, syntax_error = validate_graphql(query)
        if not is_valid_syntax:
            return {
                "valid": False,
                "error": f"GraphQL syntax error: {syntax_error}",
                "extracted_fields": {},
                "validation_results": {},
                "suggestion": "Use query_template() to generate a syntactically correct starting template",
                "workflow_tip": "Syntax errors often occur when manually writing queries. Templates prevent these issues.",
            }

        # Extract fields from query
        try:
            extracted_fields = extract_query_fields(query)
        except QueryValidationError as e:
            return self._error_response(str(e), {})
        except Exception as e:
            return self._error_response(f"Failed to parse GraphQL query: {e}", {})

        # Validate extracted fields
        try:
            validation_results = await self._validate_extracted_fields(extracted_fields)
        except Exception as e:
            return self._error_response(f"Validation failed: {e}", extracted_fields)

        return self._format_validation_response(extracted_fields, validation_results)

    async def suggest_similar_fields(
        self, field_name: str, entity_name: str
    ) -> dict[str, Any]:
        """Suggest similar field names for a given field in an entity"""
        logger.debug(f"Suggesting similar fields for {field_name} in {entity_name}")

        try:
            # Check if entity exists
            schema_data = await self._load_schema_data()
            all_entities = schema_data["entities"]

            if entity_name not in all_entities:
                # Suggest similar entity names
                entity_suggestions = self._get_entity_suggestions(
                    entity_name, all_entities
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
            schema = all_entities[entity_name]
            valid_fields = self._get_entity_fields(schema)

            # Calculate similarities
            suggestions = []
            for valid_field in valid_fields:
                similarity = SequenceMatcher(
                    None, field_name.lower(), valid_field.lower()
                ).ratio()
                if similarity > 0.4:  # Threshold for suggestions
                    suggestions.append(
                        {
                            "name": valid_field,
                            "similarity": similarity,
                            "type": "string",  # Simplified type info
                        }
                    )

            # Sort by similarity
            suggestions.sort(key=lambda x: x["similarity"], reverse=True)

            return {
                "field_name": field_name,
                "entity_name": entity_name,
                "entity_exists": True,
                "suggestions": suggestions[:10],  # Top 10 suggestions
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
    ) -> dict[str, Any]:
        """Generate a safe GraphQL query template with only confirmed valid fields"""
        logger.info(f"Generating query template for {entity_name}")

        try:
            # Load schema data
            schema_data = await self._load_schema_data()
            all_entities = schema_data["entities"]
            all_relationships = schema_data["relationships"]

            if entity_name not in all_entities:
                suggestions = self._get_entity_suggestions(entity_name, all_entities)
                return {
                    "entity_name": entity_name,
                    "exists": False,
                    "template": None,
                    "error": f"Entity '{entity_name}' does not exist",
                    "suggestions": suggestions,
                }

            # Get schema
            schema = all_entities[entity_name]

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
            if include_relationships and entity_name in all_relationships:
                relationships = all_relationships[entity_name]
                for rel in relationships[:5]:  # Limit to 5 examples
                    relationship_fields.append(
                        {
                            "name": rel.name,
                            "target_type": rel.target_type,
                            "multiplicity": rel.multiplicity,
                            "required": rel.required,
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
                for rel in relationship_fields:
                    template += f"    # {rel['name']} {{\n"
                    template += "    #     id\n"
                    template += "    #     submitter_id\n"
                    template += "    # }\n"

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
            }

        except Exception as e:
            logger.error(f"Failed to generate template for {entity_name}: {e}")
            return {
                "entity_name": entity_name,
                "exists": False,
                "template": None,
                "error": f"Failed to generate template: {e}",
            }

    # Helper methods
    def _generate_validation_summary(
        self, validation_results: dict[str, Any]
    ) -> dict[str, Any]:
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
        for _entity_name, result in validation_results.items():
            all_errors.extend(result["errors"])

        return {
            "total_entities": total_entities,
            "valid_entities": valid_entities,
            "total_fields": total_fields,
            "valid_fields": valid_fields,
            "total_errors": len(all_errors),
            "errors": all_errors,
        }

    def _error_response(self, error_msg: str, extracted_fields: dict) -> dict[str, Any]:
        """Create error response"""
        return {
            "valid": False,
            "error": error_msg,
            "extracted_fields": extracted_fields,
            "validation_results": {},
        }

    def _format_validation_response(
        self, extracted_fields: dict, validation_results: dict
    ) -> dict[str, Any]:
        """Format the final validation response"""
        formatted_results = self._convert_validation_results(validation_results)
        all_valid = all(result.valid for result in validation_results.values())

        response = {
            "valid": all_valid,
            "extracted_fields": extracted_fields,
            "validation_results": formatted_results,
            "summary": self._generate_validation_summary(formatted_results),
        }

        # Add workflow guidance based on validation results
        if not all_valid:
            suggestions = []
            has_field_errors = any(
                any(
                    not field_result.get("valid", True)
                    for field_result in result.get("field_validation", {}).values()
                )
                for result in formatted_results.values()
            )
            has_entity_errors = any(
                not result.get("entity_exists", True)
                for result in formatted_results.values()
            )

            if has_field_errors:
                suggestions.append(
                    "Use suggest_fields(field_name, entity_name) to find correct field names"
                )
            if has_entity_errors:
                suggestions.append(
                    "Use schema_entities() to see available entity names"
                )

            response["next_steps"] = {
                "suggestions": suggestions,
                "workflow": [
                    "1. Fix the validation errors using the suggestions above",
                    "2. Re-run validate_query() to confirm fixes",
                    "3. Use execute_graphql() to run the validated query",
                ],
                "alternative": "Start fresh with query_template() for a guaranteed valid query",
            }
        else:
            response["next_steps"] = {
                "ready_to_execute": True,
                "suggestion": "Query is valid! Use execute_graphql() to run it.",
            }

        return response

    def _convert_validation_results(
        self, validation_results: dict[str, ValidationResult]
    ) -> dict:
        """Convert ValidationResult objects to the expected API format"""
        formatted_results = {}

        for entity_name, result in validation_results.items():
            formatted_result = {
                "entity_exists": (
                    result.valid
                    or len(result.errors) == 0
                    or not any("does not exist" in error for error in result.errors)
                ),
                "field_validation": result.field_validation,
                "errors": result.errors,
                "warnings": result.warnings,
            }

            if result.entity_suggestions:
                formatted_result["entity_suggestions"] = result.entity_suggestions

            formatted_results[entity_name] = formatted_result

        return formatted_results

    # FIXME caching
    async def _load_schema_data(self) -> dict:
        """Load all necessary schema data for validation"""
        try:
            entities = await self.gen3_service.get_full_schema()
            relationships = {
                entity_name: self._extract_relationships(entity_schema)
                for entity_name, entity_schema in entities.items()
            }
            return {"entities": entities, "relationships": relationships}
        except Exception:
            return {"entities": {}, "relationships": {}}

    def _create_not_found_result(
        self, entity_name: str, all_entities: dict[str, Any]
    ) -> ValidationResult:
        """Create validation result for entity not found"""
        return ValidationResult(
            valid=False,
            field_validation={},
            errors=[f"Entity '{entity_name}' does not exist"],
            warnings=[],
            entity_suggestions=self._get_entity_suggestions(entity_name, all_entities),
        )

    def _find_relationship_parent(
        self,
        relationship_name: str,
        all_extracted_fields: dict[str, list[str]],
        entity_relationships: dict[str, list[RelationshipInfo]],
    ) -> tuple[str | None, RelationshipInfo | None]:
        """Find which entity this relationship_name belongs to"""
        for potential_parent in all_extracted_fields.keys():
            if potential_parent in entity_relationships:
                for relationship in entity_relationships[potential_parent]:
                    if self._is_relationship_match(relationship_name, relationship):
                        return potential_parent, relationship
        return None, None

    def _is_relationship_match(
        self, relationship_name: str, relationship: RelationshipInfo
    ) -> bool:
        """Check if a relationship name matches using various naming patterns"""
        # Exact match
        if relationship_name == relationship.name:
            return True

        # Plural of target type
        if relationship_name == f"{relationship.target_type}s":
            return True

        # Backref match
        if relationship_name == relationship.backref:
            return True

        # Handle irregular plurals FIXME a bit arbitrary atm
        irregular_plurals = {
            "child": "children",
            "person": "people",
            "datum": "data",
            "analysis": "analyses",
            "diagnosis": "diagnoses",
        }

        target_type = relationship.target_type
        if (
            target_type in irregular_plurals
            and relationship_name == irregular_plurals[target_type]
        ):
            return True

        return False

    def _extract_relationships(
        self, entity_schema: dict[str, Any]
    ) -> list[RelationshipInfo]:
        """Extract relationships from entity schema links"""
        relationships = []
        links = entity_schema.get("links", [])

        for link in links:
            if isinstance(link, dict):
                if "subgroup" in link:
                    relationships.extend(self._process_subgroup_links(link["subgroup"]))
                else:
                    relationships.append(self._create_relationship_info(link))

        return relationships

    def _process_subgroup_links(
        self, subgroup: list[dict[str, Any]]
    ) -> list[RelationshipInfo]:
        """Process subgroup links from schema"""
        return [
            self._create_relationship_info(sublink)
            for sublink in subgroup
            if isinstance(sublink, dict)
        ]

    def _create_relationship_info(self, link: dict[str, Any]) -> RelationshipInfo:
        """Create RelationshipInfo from link definition"""
        return RelationshipInfo(
            name=link.get("name", ""),
            target_type=link.get("target_type", ""),
            multiplicity=link.get("multiplicity", ""),
            required=link.get("required", False),
            backref=link.get("backref", ""),
        )

    def _get_entity_fields(self, entity_schema: dict[str, Any]) -> set:
        """Extract all valid fields from entity schema"""
        fields = set()

        # Add properties
        properties = entity_schema.get("properties", {})
        fields.update(properties.keys())

        # Add system properties
        system_properties = entity_schema.get("systemProperties", [])
        fields.update(system_properties)

        # Add common GraphQL fields
        fields.update(
            ["id", "type", "submitter_id", "created_datetime", "updated_datetime"]
        )

        return fields

    def _get_field_suggestions(
        self, field_name: str, available_fields: set
    ) -> list[str]:
        """Get field suggestions using fuzzy matching"""
        suggestions = []
        for available_field in available_fields:
            similarity = SequenceMatcher(
                None, field_name.lower(), available_field.lower()
            ).ratio()
            if similarity > 0.6:
                suggestions.append(available_field)

        return sorted(
            suggestions,
            key=lambda x: SequenceMatcher(None, field_name.lower(), x.lower()).ratio(),
            reverse=True,
        )[:3]

    def _get_entity_suggestions(
        self, entity_name: str, all_entities: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Get entity suggestions using fuzzy matching"""
        suggestions = []
        for available_entity in all_entities.keys():
            similarity = SequenceMatcher(
                None, entity_name.lower(), available_entity.lower()
            ).ratio()
            if similarity > 0.5:
                suggestions.append({"name": available_entity, "similarity": similarity})

        return sorted(suggestions, key=lambda x: x["similarity"], reverse=True)[:3]

    async def _validate_extracted_fields(
        self, extracted_fields: dict[str, list[str]]
    ) -> dict[str, ValidationResult]:
        """Main validation orchestration for extracted fields"""
        schema_data = await self._load_schema_data()
        results = {}

        for entity_name, fields in extracted_fields.items():
            results[entity_name] = await self._validate_single_entity(
                entity_name, fields, schema_data, extracted_fields
            )

        return results

    async def _validate_single_entity(
        self,
        entity_name: str,
        fields: list[str],
        schema_data: dict,
        all_extracted_fields: dict[str, list[str]],
    ) -> ValidationResult:
        """Validate a single entity and its fields"""
        entities = schema_data["entities"]
        relationships = schema_data["relationships"]

        # Check if this is a direct entity
        if entity_name in entities:
            return await self._validate_direct_entity(
                entity_name, fields, entities, relationships
            )

        # Check if this is a relationship field
        parent_entity, relationship = self._find_relationship_parent(
            entity_name, all_extracted_fields, relationships
        )

        if parent_entity and relationship:
            return await self._validate_relationship_fields(
                entity_name, fields, relationship, entities
            )

        # Entity not found
        return self._create_not_found_result(entity_name, entities)

    async def _validate_direct_entity(
        self,
        entity_name: str,
        fields: list[str],
        all_entities: dict[str, Any],
        entity_relationships: dict[str, list[RelationshipInfo]],
    ) -> ValidationResult:
        """Validate fields for a direct entity"""
        entity_schema = all_entities[entity_name]
        available_fields = self._get_entity_fields(entity_schema)
        relationship_fields = {
            rel.name for rel in entity_relationships.get(entity_name, [])
        }

        field_validation = {}
        errors = []

        for field in fields:
            if field in available_fields:
                field_validation[field] = {"valid": True, "suggestions": []}
            elif field in relationship_fields:
                field_validation[field] = {
                    "valid": True,
                    "suggestions": [],
                    "type": "relationship",
                }
            else:
                suggestions = self._get_field_suggestions(field, available_fields)
                field_validation[field] = {"valid": False, "suggestions": suggestions}
                errors.append(
                    f"Field '{field}' does not exist in entity '{entity_name}'"
                )

        return ValidationResult(
            valid=len(errors) == 0,
            field_validation=field_validation,
            errors=errors,
            warnings=[],
        )

    async def _validate_relationship_fields(
        self,
        relationship_name: str,
        fields: list[str],
        relationship: RelationshipInfo,
        all_entities: dict[str, Any],
    ) -> ValidationResult:
        """Validate fields for an entity accessed through a relationship"""
        target_entity_name = relationship.target_type

        if target_entity_name not in all_entities:
            return ValidationResult(
                valid=False,
                field_validation={},
                errors=[
                    f"Target entity '{target_entity_name}' for relationship '{relationship_name}' does not exist"
                ],
                warnings=[],
            )

        target_entity_schema = all_entities[target_entity_name]
        available_fields = self._get_entity_fields(target_entity_schema)

        field_validation = {}
        errors = []

        for field in fields:
            if field in available_fields:
                field_validation[field] = {"valid": True, "suggestions": []}
            else:
                suggestions = self._get_field_suggestions(field, available_fields)
                field_validation[field] = {"valid": False, "suggestions": suggestions}
                errors.append(
                    f"Field '{field}' does not exist in target entity '{target_entity_name}'"
                )

        return ValidationResult(
            valid=len(errors) == 0,
            field_validation=field_validation,
            errors=errors,
            warnings=[],
        )
