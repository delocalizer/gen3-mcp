"""GraphQL Query service for validation, building, and execution."""

import logging
from functools import cache

from .graphql_validator import validate_graphql
from .models import Response
from .schema import SchemaManager
from .utils import suggest_similar_strings_with_scores

logger = logging.getLogger("gen3-mcp.query")


class QueryService:
    """Query operations: validation, building, and execution."""

    def __init__(self, schema_manager: SchemaManager):
        """Initialize QueryService.

        Args:
            schema_manager: SchemaManager instance for schema operations.

        Raises:
            No exceptions raised during initialization.
        """
        self.schema_manager = schema_manager
        # Access client and config through schema_manager
        self.client = schema_manager.client
        self.config = schema_manager.client.config

    async def execute_graphql(self, query: str) -> Response:
        """Execute GraphQL query.

        Args:
            query: GraphQL query string.

        Returns:
            Response with query results or error information.

        Raises:
            No exceptions raised - all errors are caught and returned as Response objects.
            Propagates errors from client.post_json() which may include:
            - Gen3ClientError: Authentication failures
            - Network/HTTP/GraphQL errors (converted to Response by client)
        """
        logger.info("Executing GraphQL query")
        logger.debug(f"Query: {query[:200]}{'...' if len(query) > 200 else ''}")

        response = await self.client.post_json(
            self.config.graphql_url,
            json={"query": query},
        )

        # Enhance success message for GraphQL context
        if response.is_success:
            response.message = "GraphQL query executed and data retrieved successfully"

        return response

    async def generate_query_template(
        self, entity_name: str, include_relationships: bool = True, max_fields: int = 20
    ) -> Response:
        """Generate a safe GraphQL query template with only confirmed valid fields.

        Args:
            entity_name: Name of the entity to generate template for.
            include_relationships: Whether to include relationship examples.
            max_fields: Maximum number of fields to include.

        Returns:
            Response with template info or error information if entity doesn't exist.

        Raises:
            No exceptions raised - all errors are caught and returned as Response objects.
            May propagate errors from schema_manager.get_schema_extract().
            Internal processing could theoretically raise:
            - KeyError: If entity schema structure is unexpected
            - IndexError: If list slicing operations fail unexpectedly
            - Exception: Any other unexpected error during template generation
        """
        logger.info(f"Generating query template for {entity_name}")

        # Get schema extract from schema manager
        extract_response = await self.schema_manager.get_schema_extract()
        if not extract_response.is_success:
            # Enhance the error message for template generation context
            extract_response.message = (
                "Failed to generate template - schema not available"
            )
            return extract_response

        schema_extract = extract_response.data

        if entity_name not in schema_extract:
            # Suggest similar entity names
            suggestions = suggest_similar_strings_with_scores(
                entity_name,
                set(schema_extract.keys()),
                threshold=0.5,
                max_results=3,
            )

            logger.warning(f"Entity '{entity_name}' not found")
            return Response(
                status="error",
                message=f"Entity '{entity_name}' not found in schema",
                errors=[f"Entity '{entity_name}' does not exist"],
                suggestions=[
                    f"Try '{suggestion['name']}' instead" for suggestion in suggestions
                ],
                metadata={
                    "attempted_entity": entity_name,
                    "available_suggestions": suggestions,
                },
            )

        # Get entity schema
        entity = schema_extract[entity_name]

        # Build template fields
        required = entity.schema_summary.required_fields
        relations = list(entity.relationships)
        basic_fields = ["id"] + [f for f in required if f not in relations]
        remaining_slots = max_fields - len(basic_fields)
        template_fields = (
            basic_fields
            + [f for f in entity.schema_summary.enum_fields if f not in basic_fields][
                :remaining_slots
            ]
        )

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
        return Response(
            status="success",
            message=f"GraphQL query template generated for entity '{entity_name}'",
            data={
                "entity_name": entity_name,
                "template": full_template,
                "included_relationships": include_relationships,
                "max_fields_used": max_fields,
            },
            suggestions=[
                "Copy the template and modify it for your specific needs",
                "Use validate_query() to check the template before execution",
                "Add or remove fields as needed for your use case",
            ],
            metadata={
                "generation_params": {
                    "include_relationships": include_relationships,
                    "max_fields": max_fields,
                }
            },
        )

    async def validate_query(self, query: str) -> Response:
        """Validate GraphQL query.

        Args:
            query: GraphQL query string to validate.

        Returns:
            Response with validation status, errors, and suggestions.

        Raises:
            No exceptions raised - all errors are caught and returned as Response objects.
            May propagate errors from:
            - schema_manager.get_schema_extract()
            - validate_graphql() function
        """
        logger.info("Validating GraphQL query")

        extract_response = await self.schema_manager.get_schema_extract()
        if not extract_response.is_success:
            # Enhance the error message for validation context
            extract_response.message = "Failed to validate query - schema not available"
            return extract_response

        schema_extract = extract_response.data
        return validate_graphql(query, schema_extract)


@cache
def get_query_service() -> QueryService:
    """Get a cached QueryService instance using the default schema manager.

    Returns:
        QueryService instance with default dependencies.

    Raises:
        May propagate exceptions from get_schema_manager() initialization chain.
    """
    from .schema import get_schema_manager

    return QueryService(get_schema_manager())
