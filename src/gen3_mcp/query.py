"""GraphQL Query service for validation, building, and execution"""

import logging
from typing import Any

from .client import Gen3Client
from .config import Gen3Config
from .graphql_validator import validate_graphql
from .schema import SchemaService
from .schema_extract import SchemaExtract

logger = logging.getLogger("gen3-mcp.query")


class QueryService:
    """Query operations: validation, building, and execution"""

    def __init__(
        self, client: Gen3Client, config: Gen3Config, gen3_service: SchemaService
    ):
        self.client = client
        self.config = config
        self.gen3_service = gen3_service
        self._schema_extract: SchemaExtract | None = None

    async def _get_schema_extract(self) -> SchemaExtract:
        """Get or create SchemaExtract from full schema"""
        if self._schema_extract is None:
            full_schema = await self.gen3_service.get_schema_full()
            self._schema_extract = SchemaExtract.from_full_schema(full_schema)
        return self._schema_extract

    async def execute_graphql(self, query: str) -> dict[str, Any] | None:
        """Execute GraphQL query"""
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
                    suggestions.append("Use validate_query() to check field names")
                elif "syntax" in error_msg.lower():
                    suggestions.append(
                        "Use query_template() to generate a syntactically correct starting template"
                    )
                elif "type" in error_msg.lower():
                    suggestions.append(
                        "Check entity names with schema_summary() or schema_entity_context()"
                    )

            if suggestions:
                result["execution_guidance"] = {
                    "suggestions": list(set(suggestions)),  # Remove duplicates
                    "recommended_workflow": [
                        "1. Use validate_query() to check your query syntax and field names",
                        "2. If validation fails, use the suggestions to fix errors",
                        "3. Use execute_graphql() to run the validated query",
                    ],
                }

        return result

    async def validate_query(self, query: str) -> dict[str, Any]:
        """Validate GraphQL query"""
        logger.info("Validating GraphQL query")

        schema_extract = await self._get_schema_extract()
        result = validate_graphql(query, schema_extract)

        # Convert to expected MCP response format
        response = {
            "valid": result.is_valid,
            "query_tree": result.query_tree,
            "errors": [
                {
                    "entity": err.entity,
                    "field": err.field,
                    "message": err.message,
                    "suggestions": err.suggestions or [],
                }
                for err in result.errors
            ],
        }

        # Add workflow guidance
        if not result.is_valid:
            response["next_steps"] = {
                "suggestions": [
                    "Fix the validation errors using the suggestions above",
                    "Use schema_entity_context() to see available fields and relationships for an entity",
                    "Use schema_summary() to see available entities",
                ],
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

    async def generate_query_template(
        self, entity_name: str, include_relationships: bool = True, max_fields: int = 20
    ) -> dict[str, Any]:
        """Generate a safe GraphQL query template with only confirmed valid fields"""
        logger.info(f"Generating query template for {entity_name}")

        try:
            # Get schema extract to check entity exists
            schema_extract = await self._get_schema_extract()

            if entity_name not in schema_extract.entities:
                # Suggest similar entity names
                from difflib import SequenceMatcher

                suggestions = []
                for available_entity in schema_extract.entities.keys():
                    similarity = SequenceMatcher(
                        None, entity_name.lower(), available_entity.lower()
                    ).ratio()
                    if similarity > 0.5:
                        suggestions.append(
                            {"name": available_entity, "similarity": similarity}
                        )
                suggestions.sort(key=lambda x: x["similarity"], reverse=True)

                return {
                    "entity_name": entity_name,
                    "exists": False,
                    "template": None,
                    "error": f"Entity '{entity_name}' does not exist",
                    "suggestions": suggestions[:3],
                }

            # Get entity schema
            entity = schema_extract.entities[entity_name]

            # Get basic fields (first few from the entity)
            basic_fields = ["id", "submitter_id", "type"]
            available_fields = list(entity.fields)

            # Add some entity-specific fields
            entity_fields = [f for f in available_fields if f not in basic_fields][
                : max_fields - 3
            ]
            template_fields = basic_fields + entity_fields

            # Generate the template
            template = f"{entity_name}(first: 10) {{\n"
            for field in template_fields:
                template += f"    {field}\n"

            # Add relationship examples
            relationship_fields = []
            if include_relationships:
                for rel_name, rel in list(entity.relationships.items())[:3]:
                    relationship_fields.append(
                        {"name": rel_name, "target_type": rel.target_type}
                    )
                    template += f"    # {rel_name} {{\n"
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
                "entity_fields": entity_fields,
                "relationship_fields": relationship_fields,
                "total_fields": len(template_fields),
            }

        except Exception as e:
            logger.error(f"Failed to generate template for {entity_name}: {e}")
            return {
                "entity_name": entity_name,
                "exists": False,
                "template": None,
                "error": f"Failed to generate template: {e}",
            }
