"""GraphQL Query service for validation, building, and execution."""

import logging
from functools import cache

import httpx

from .exceptions import GraphQLError, NoSuchEntityError
from .graphql_validator import validate_graphql
from .schema import SchemaManager
from .utils import suggest_similar_strings

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

    async def execute_graphql(self, query: str) -> dict:
        """Execute GraphQL query.

        Args:
            query: GraphQL query string.

        Returns:
            Query results data from GraphQL endpoint.

        Raises:
            ConfigError: From auth if there is a config issue.
            httpx.HTTPError: For HTTP/network errors during GraphQL execution.
            GraphQLError: For GraphQL validation/execution failures.
        """
        logger.info("Executing GraphQL query")
        logger.debug(f"Query: {query[:200]}{'...' if len(query) > 200 else ''}")

        try:
            data = await self.client.post_json(
                self.config.graphql_url,
                json={"query": query},
            )
            logger.debug("GraphQL query executed successfully")
            return data

        except httpx.HTTPStatusError as e:
            # Check if this is a GraphQL validation error (HTTP 400 with GraphQL errors)
            # Gen3 GraphQL error response format:
            # {
            #   "data": null,
            #   "errors": [
            #     "Cannot query field \"demographic\" on type \"subject\"."
            #   ]
            # }
            if e.response.status_code == 400:
                response_data = e.response.json()
                if "errors" in response_data:
                    # Gen3 returns errors as a list of strings
                    graphql_errors = response_data["errors"]
                    raise GraphQLError(
                        "GraphQL query execution failed",
                        errors=graphql_errors,
                        suggestions=[
                            "Use validate_query() before executing",
                            "Check field names against schema",
                            "Verify entity relationships exist",
                        ],
                        context={
                            "query": query,
                            "status_code": e.response.status_code,
                            "method": e.request.method,
                            "url": str(e.response.url),
                        },
                    ) from e

            # Not a GraphQL error, re-raise HTTP error as-is
            raise

    async def generate_query_template(
        self, entity_name: str, include_relationships: bool = True, max_fields: int = 20
    ) -> dict:
        """Generate a safe GraphQL query template with only confirmed valid fields.

        Args:
            entity_name: Name of the entity to generate template for.
            include_relationships: Whether to include relationship examples.
            max_fields: Maximum number of fields to include.

        Returns:
            Template data with entity_name, template, and generation parameters.

        Raises:
            ConfigError: From auth if there is a config issue.
            httpx.HTTPError: For HTTP/network errors during API calls.
            ParseError: If schema processing fails.
            NoSuchEntityError: If entity doesn't exist in schema.
        """
        logger.info(f"Generating query template for {entity_name}")

        # Get schema extract (may raise ConfigError, httpx errors, or ParseError)
        schema_extract = await self.schema_manager.get_schema_extract()

        if entity_name not in schema_extract:
            # Suggest similar entity names
            suggestions = suggest_similar_strings(
                entity_name,
                set(schema_extract.keys()),
                threshold=0.5,
                max_results=3,
            )

            logger.warning(f"Entity '{entity_name}' not found")
            raise NoSuchEntityError(
                f"Entity '{entity_name}' not found in schema",
                suggestions=[
                    f"Try '{suggestion}' instead" for suggestion in suggestions
                ],
                context={
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

        return {
            "entity_name": entity_name,
            "template": full_template,
            "included_relationships": include_relationships,
            "max_fields_used": max_fields,
        }

    async def validate_query(self, query: str) -> None:
        """Validate GraphQL query.

        Args:
            query: GraphQL query string to validate.

        Returns:
            None: Validation functions follow the Pythonic pattern of returning None on
            success. The caller has the original query for context and can construct
            appropriate response objects as needed.

        Raises:
            ConfigError: From auth if there is a config issue.
            httpx.HTTPError: For HTTP/network errors during API calls.
            ParseError: If schema processing fails.
            GraphQLError: If query validation fails.
        """
        logger.info("Validating GraphQL query")

        # Get schema extract (may raise ConfigError, httpx errors, or ParseError)
        schema_extract = await self.schema_manager.get_schema_extract()

        # Validate using the graphql_validator function
        # validate_graphql returns None on success, raises GraphQLError on failure
        validate_graphql(query, schema_extract)


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
