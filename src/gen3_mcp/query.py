"""GraphQL Query service for validation, building, and execution."""

import logging
from functools import cache
from typing import Any

from .graphql_validator import validate_graphql
from .models import ErrorCategory, QueryValidationResult, SchemaExtract
from .schema import SchemaManager

logger = logging.getLogger("gen3-mcp.query")


class QueryService:
    """Query operations: validation, building, and execution."""

    def __init__(self, schema_manager: SchemaManager):
        """Initialize QueryService.

        Args:
            schema_manager: SchemaManager instance for schema operations.
        """
        self.schema_manager = schema_manager
        # Access client and config through schema_manager
        self.client = schema_manager.client
        self.config = schema_manager.client.config

    async def execute_graphql(self, query: str) -> dict[str, Any]:
        """Execute GraphQL query.

        Args:
            query: GraphQL query string.

        Returns:
            Query results dict. May include errors and suggestions for fixing them.
            Structure varies based on success/failure and error type.
        """
        logger.info("Executing GraphQL query")
        logger.debug(f"Query: {query[:200]}{'...' if len(query) > 200 else ''}")

        response = await self.client.post_json(
            self.config.graphql_url,
            json={"query": query},
        )

        if not response.success:
            logger.error(f"GraphQL query execution failed: {response.error_message}")

            # Network errors
            if response.error_category == ErrorCategory.NETWORK:
                return {
                    "errors": [f"Network error: {response.error_message}"],
                    "suggestion": "Check your internet connection and Gen3 server availability",
                }

            # HTTP client errors (4xx) - usually bad query
            elif response.error_category == ErrorCategory.HTTP_CLIENT:
                result = response.data if response.data else {}
                if "errors" not in result:
                    result["errors"] = [
                        f"HTTP {response.status_code} error: {response.error_message}"
                    ]

                result["suggestion"] = {
                    "recommended_workflow": [
                        "1. Inspect errors key to understand the cause of the bad query",
                        "2. Use validate_query() to check your query syntax and field names",
                        "3. If validation fails, use the suggestions to fix errors",
                        "4. Use execute_graphql() to run the validated query",
                    ],
                }
                return result

            # HTTP server errors (5xx) or other errors
            else:
                return {
                    "errors": [f"Server error: {response.error_message}"],
                    "suggestion": "The Gen3 server encountered an error. Try again later.",
                }

        # Success case - response.data contains the GraphQL response
        result = response.data
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

        # Get schema extract from schema manager
        schema_extract = await self.schema_manager.get_schema_extract()

        if entity_name not in schema_extract:
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
        entity = schema_extract[entity_name]

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

    async def validate_query(self, query: str) -> QueryValidationResult:
        """Validate GraphQL query.

        Args:
            query: GraphQL query string to validate.

        Returns:
            QueryValidationResult including validity status, errors,
            and suggestions for fixing any issues.
        """
        logger.info("Validating GraphQL query")

        schema_extract = await self.schema_manager.get_schema_extract()
        return validate_graphql(query, schema_extract)

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
        for available_entity in schema_extract:
            similarity = SequenceMatcher(
                None, entity_name.lower(), available_entity.lower()
            ).ratio()
            if similarity > 0.5:
                suggestions.append({"name": available_entity, "similarity": similarity})

        return sorted(suggestions, key=lambda x: x["similarity"], reverse=True)


@cache
def get_query_service() -> QueryService:
    """Get a cached QueryService instance using the default schema manager.

    Returns:
        QueryService instance with default dependencies.
    """
    from .schema import get_schema_manager

    return QueryService(get_schema_manager())
