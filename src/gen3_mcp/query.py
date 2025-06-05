"""GraphQL Query service for validation, building, and execution."""

import logging
from typing import Any

from .client import Gen3Client
from .config import Config
from .graphql_validator import validate_graphql
from .schema import SchemaManager
from .schema_extract import SchemaExtract

logger = logging.getLogger("gen3-mcp.query")


class QueryService:
    """Query operations: validation, building, and execution."""

    def __init__(
        self, client: Gen3Client, config: Config, schema_manager: SchemaManager
    ):
        """Initialize QueryService.

        Args:
            client: Gen3Client instance for API calls.
            config: Config instance with settings.
            schema_manager: SchemaManager instance for schema operations.
        """
        self.client = client
        self.config = config
        self.schema_manager = schema_manager
        self._schema_extract: SchemaExtract | None = None

    async def execute_graphql(self, query: str) -> dict[str, Any] | None:
        """Execute GraphQL query.

        Args:
            query: GraphQL query string.

        Returns:
            Query results dict or None if execution fails. May include errors
            and suggestions for fixing them.
        """
        logger.info("Executing GraphQL query")
        logger.debug(f"Query: {query[:200]}{'...' if len(query) > 200 else ''}")

        result = await self.client.post_json(
            self.config.graphql_url,
            json={"query": query},
        )

        if result is None:
            logger.error("GraphQL query execution failed - network error")
            return {
                "errors": ["Network error - unable to connect to Gen3 server"],
                "suggestion": "Check your internet connection and Gen3 server availability",
            }

        # Extract HTTP error context if present
        http_error_context = result.pop("_http_error_context", None)

        if http_error_context:
            logger.warning("GraphQL query returned an error")
            # 400 error = bad query
            if http_error_context["error_category"] == "BAD_REQUEST":
                result["suggestion"] = {
                    "recommended_workflow": [
                        "1. Inspect errors key to understand the cause of the bad query",
                        "2. Use validate_query() to check your query syntax and field names",
                        "3. If validation fails, use the suggestions to fix errors",
                        "4. Use execute_graphql() to run the validated query",
                    ],
                }

            return result

        # Success case
        logger.info("GraphQL query executed successfully")
        return result

    async def generate_query_template(
        self, entity_name: str, include_relationships: bool = True, max_fields: int = 20
    ) -> dict[str, Any]:
        """Generate a safe GraphQL query template with only confirmed valid fields.

        Args:
            entity_name: Name of the entity to generate template for.
            include_relationships: Whether to include relationship examples.
            max_fields: Maximum number of fields to include.

        Returns:
            Dict with template info including the query template string,
            or error info if entity doesn't exist.
        """
        logger.info(f"Generating query template for {entity_name}")

        # Get schema extract to check entity exists
        schema_extract = await self._get_schema_extract()

        if entity_name not in schema_extract.entities:
            # Suggest similar entity names
            suggestions = self._find_similar_entities(entity_name, schema_extract)

            logger.warning(f"Entity '{entity_name}' not found")
            return {
                "entity_name": entity_name,
                "exists": False,
                "template": None,
                "error": f"Entity '{entity_name}' does not exist",
                "suggestions": suggestions[:3],
            }

        # Get entity schema
        entity = schema_extract.entities[entity_name]

        # Build template fields
        required = entity.schema_summary.required_fields
        relations = list(entity.relationships)
        basic_fields = ["id"] + [f for f in required if f not in relations]
        entity_fields = [
            f for f in entity.schema_summary.enum_fields if f not in basic_fields
        ][: max_fields - len(basic_fields)]
        template_fields = basic_fields + entity_fields

        # Generate the template
        template_lines = [f"{entity_name}(first: 10) {{"]
        template_lines.extend(f"    {field}" for field in template_fields)

        # Add relationship examples
        if include_relationships:
            for rel_name, _rel in list(entity.relationships.items())[:5]:
                template_lines.extend(
                    [
                        f"    {rel_name} {{",
                        "        id",
                        "        submitter_id",
                        "    }",
                    ]
                )

        template_lines.append("}")

        # Create full query
        full_template = "{\n    " + "\n    ".join(template_lines) + "\n}"

        logger.info(
            f"Template generated for {entity_name} with {len(template_fields)} fields"
        )
        return {
            "entity_name": entity_name,
            "exists": True,
            "template": full_template,
        }

    async def validate_query(self, query: str) -> dict[str, Any]:
        """Validate GraphQL query.

        Args:
            query: GraphQL query string to validate.

        Returns:
            Dict with validation results including validity status, errors,
            and suggestions for fixing any issues.
        """
        logger.info("Validating GraphQL query")

        schema_extract = await self._get_schema_extract()
        result = validate_graphql(query, schema_extract)

        # Convert to expected MCP response format
        response = {
            "valid": result.is_valid,
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
            logger.warning(f"Query validation failed with {len(result.errors)} errors")
            response["next_steps"] = {
                "suggestions": [
                    "Fix the validation errors using the suggestions above",
                    "Use annotated_schema_structure() to see available entities and fields",
                ],
                "workflow": [
                    "1. Fix the validation errors using the suggestions above",
                    "2. Re-run validate_query() to confirm fixes",
                    "3. Use execute_graphql() to run the validated query",
                ],
                "alternative": "Start fresh with query_template() for a guaranteed valid query",
            }
        else:
            logger.info("Query validation successful")
            response["next_steps"] = {
                "ready_to_execute": True,
                "suggestion": "Query is valid! Use execute_graphql() to run it.",
            }

        return response

    async def _get_schema_extract(self) -> SchemaExtract:
        """Get or create SchemaExtract from full schema.

        Returns:
            SchemaExtract instance.

        Raises:
            Gen3SchemaError: If schema fetch fails.
        """
        if self._schema_extract is None:
            logger.debug("Creating SchemaExtract")
            full_schema = await self.schema_manager.get_schema_full()
            self._schema_extract = SchemaExtract.from_full_schema(full_schema)
            logger.debug("SchemaExtract created")

        return self._schema_extract

    def _find_similar_entities(
        self, entity_name: str, schema_extract: SchemaExtract
    ) -> list[dict[str, Any]]:
        """Find entities with similar names.

        Args:
            entity_name: Entity name to match against.
            schema_extract: SchemaExtract with available entities.

        Returns:
            List of dicts with entity name and similarity score.
        """
        from difflib import SequenceMatcher

        suggestions = []
        for available_entity in schema_extract.entities:
            similarity = SequenceMatcher(
                None, entity_name.lower(), available_entity.lower()
            ).ratio()
            if similarity > 0.5:
                suggestions.append({"name": available_entity, "similarity": similarity})

        return sorted(suggestions, key=lambda x: x["similarity"], reverse=True)
