"""GraphQL query parsing utilities using graphql-core for robust parsing"""

import logging

from graphql import FieldNode, Visitor, parse, visit
from graphql.error import GraphQLSyntaxError

from .exceptions import QueryValidationError

logger = logging.getLogger("gen3-mcp.graphql_parser")


class FieldExtractorVisitor(Visitor):
    """Visitor to extract field names and entity types from GraphQL AST"""

    def __init__(self):
        super().__init__()
        self.extracted_fields: dict[str, list[str]] = {}
        self.entity_stack: list[str] = []

    def enter_field(self, node: FieldNode, *_) -> None:
        """Called when entering a field node"""
        field_name = node.name.value

        # Check if this field has a selection set (indicates it's an entity)
        if node.selection_set:
            # This is an entity field, not a scalar field
            self.entity_stack.append(field_name)

            # Initialize the entity in our results if not present
            if field_name not in self.extracted_fields:
                self.extracted_fields[field_name] = []
        else:
            # This is a scalar field - add to current entity if we have one
            if self.entity_stack:
                current_entity = self.entity_stack[-1]
                self.extracted_fields[current_entity].append(field_name)

    def leave_field(self, node: FieldNode, *_) -> None:
        """Called when leaving a field node"""
        # If this field had a selection set, we're leaving an entity
        if node.selection_set and self.entity_stack:
            self.entity_stack.pop()


def extract_query_fields(query: str) -> dict[str, list[str]]:
    """
    Extract entity names and their fields from a GraphQL query.

    Args:
        query: GraphQL query string

    Returns:
        Dictionary mapping entity names to lists of field names

    Raises:
        QueryValidationError: If the GraphQL query has syntax errors

    Examples:
        >>> extract_query_fields('{ subject { id name } }')
        {'subject': ['id', 'name']}

        >>> extract_query_fields('{ subject { id samples { type } } }')
        {'subject': ['id'], 'samples': ['type']}
    """
    try:
        # Parse the GraphQL query into an AST
        ast = parse(query)

        # Create visitor to extract fields
        visitor = FieldExtractorVisitor()

        # Visit the AST to extract field information
        visit(ast, visitor)

        # Remove duplicates from field lists while preserving order
        result = {}
        for entity, fields in visitor.extracted_fields.items():
            # Use dict.fromkeys() to remove duplicates while preserving order
            result[entity] = list(dict.fromkeys(fields))

        logger.debug(f"Extracted fields from query: {result}")
        return result

    except GraphQLSyntaxError as e:
        logger.error(f"GraphQL syntax error in query: {e}")
        raise QueryValidationError(f"Invalid GraphQL syntax: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error parsing GraphQL query: {e}")
        raise QueryValidationError(f"Failed to parse GraphQL query: {e}") from e


def validate_graphql(query: str) -> tuple[bool, str | None]:
    """
    Validate that a GraphQL query has correct syntax.

    Args:
        query: GraphQL query string

    Returns:
        Tuple of (is_valid, error_message)

    Examples:
        >>> validate_graphql('{ subject { id } }')
        (True, None)

        >>> validate_graphql('{ subject { id }')  # Missing closing brace
        (False, 'Syntax Error: Expected Name, found EOF.')
    """
    try:
        parse(query)
        return True, None
    except GraphQLSyntaxError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Unexpected parsing error: {e}"
