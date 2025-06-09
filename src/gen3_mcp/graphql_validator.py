"""GraphQL Query Validator against a Gen3 Schema.

Takes a GraphQL query and minimal schema structure to validate field names and relationships.
"""

import logging
from dataclasses import dataclass

from graphql import FieldNode, Visitor, parse, visit
from graphql.error import GraphQLSyntaxError

from .exceptions import GraphQLError
from .models import EntitySchema, SchemaExtract
from .utils import suggest_similar_strings

logger = logging.getLogger("gen3-mcp.graphql_validator")


@dataclass
class EntityPath:
    """Represents a path to an entity in the GraphQL query."""

    entity_name: str
    path: list[str]  # Full path from root to this entity
    fields: list[str]  # Scalar fields for this entity


@dataclass
class ValidationError:
    """Simple validation error for internal use."""

    entity: str
    field: str
    error_type: str
    message: str
    suggestions: list[str]


class GraphQLFieldExtractor(Visitor):
    """Extract field information with path context from GraphQL AST."""

    def __init__(self):
        """Initialize GraphQLFieldExtractor.

        Raises:
            No exceptions raised during initialization.
        """
        super().__init__()
        self.entity_paths: dict[str, EntityPath] = {}
        self.path_stack: list[str] = []

    def enter_field(self, node: FieldNode, *_) -> None:
        """Process field node on entry.

        Args:
            node: GraphQL field node.
            *_: Unused visitor arguments.

        Raises:
            AttributeError: If node structure is unexpected (defensive programming).
        """
        field_name = node.name.value

        if node.selection_set:
            # This field has sub-selections - it's an entity/relationship
            current_path = self.path_stack + [field_name]

            # Store the path for this entity
            self.entity_paths[field_name] = EntityPath(
                entity_name=field_name, path=current_path.copy(), fields=[]
            )

            self.path_stack.append(field_name)
        else:
            # Scalar field - add to current entity
            if self.path_stack:
                current_entity = self.path_stack[-1]
                if current_entity in self.entity_paths:
                    self.entity_paths[current_entity].fields.append(field_name)

    def leave_field(self, node: FieldNode, *_) -> None:
        """Process field node on exit.

        Args:
            node: GraphQL field node.
            *_: Unused visitor arguments.

        Raises:
            IndexError: If path_stack is empty when popping (defensive programming).
        """
        if node.selection_set and self.path_stack:
            self.path_stack.pop()


def validate_graphql(query: str, schema: SchemaExtract) -> None:
    """Validate a GraphQL query against the minimal schema using path-based validation.

    Args:
        query: GraphQL query string to validate.
        schema: SchemaExtract containing entity and field definitions.

    Returns:
        None: Validation functions follow the Pythonic pattern of returning None on
        success (similar to jsonschema.validate(), ast.parse()). Success is indicated
        by the absence of exceptions. This avoids creating artificial return values
        when the only meaningful outcome is "validation passed" vs "validation failed".

    Raises:
        GraphQLError: For GraphQL syntax errors or validation failures.
            - GraphQL syntax errors: Invalid query syntax
            - Validation errors: Unknown entities, fields, or relationships
    """
    logger.debug("Starting GraphQL validation")

    # Parse GraphQL and extract entity paths
    try:
        ast = parse(query)
        extractor = GraphQLFieldExtractor()
        visit(ast, extractor)
    except GraphQLSyntaxError as e:
        logger.error(f"GraphQL syntax error: {e}")
        raise GraphQLError(
            "GraphQL syntax error",
            errors=[f"GraphQL syntax error: {e}"],
            suggestions=[
                "Check query syntax",
                "Ensure all braces and quotes are properly closed",
            ],
            context={
                "query": query,
                "error_type": "syntax_error",
            },
        ) from e

    # Validate each entity path
    errors = []
    all_suggestions = set()

    for entity_path in extractor.entity_paths.values():
        path_errors = _validate_entity_path(entity_path, schema)
        errors.extend(path_errors)
        for error in path_errors:
            all_suggestions.update(error.suggestions)

    if errors:
        # Format error messages for the errors list
        error_messages = []
        for err in errors:
            if err.field:
                error_messages.append(f"{err.entity}.{err.field}: {err.message}")
            else:
                error_messages.append(f"{err.entity}: {err.message}")

        raise GraphQLError(
            f"GraphQL query validation failed with {len(errors)} errors",
            errors=error_messages,
            suggestions=list(all_suggestions)
            + [
                "Use get_schema_summary() to see available entities and fields",
            ],
            context={
                "query": query,
                "error_count": len(errors),
            },
        )

    logger.info("Validation successful")


def _validate_entity_path(
    entity_path: EntityPath, schema: SchemaExtract
) -> list[ValidationError]:
    """Validate an entity using its path context.

    Args:
        entity_path: EntityPath to validate.
        schema: SchemaExtract containing entity definitions.

    Returns:
        List of validation errors found. Empty list indicates no errors.

    Raises:
        KeyError: If schema structure is unexpected.
        IndexError: If path indexing fails.
        AttributeError: If entity schema structure is malformed.
        (In practice, these would indicate bugs in schema processing)
    """
    logger.debug(f"Validating entity path: {'/'.join(entity_path.path)}")
    errors = []

    # Walk through the path to validate each step
    current_entity_schema = None

    for i, entity_name in enumerate(entity_path.path):
        if i == 0:
            # Root entity - must exist directly in schema
            if entity_name not in schema:
                entity_suggestions = suggest_similar_strings(
                    entity_name, set(schema.keys())
                )
                errors.append(
                    ValidationError(
                        entity=entity_name,
                        field="",
                        error_type="unknown_entity",
                        message=f"Root entity '{entity_name}' does not exist",
                        suggestions=(
                            [f"Try '{s}' instead" for s in entity_suggestions]
                            if entity_suggestions
                            else []
                        ),
                    )
                )
                return errors  # Can't continue without valid root
            current_entity_schema = schema[entity_name]
        else:
            # Relationship entity - must be accessible from parent
            parent_entity = entity_path.path[i - 1]

            if not current_entity_schema:
                continue  # Parent was invalid, skip

            # Check if this is a valid relationship from parent
            if entity_name in current_entity_schema.relationships:
                relationship = current_entity_schema.relationships[entity_name]
                # by schema extract construction, relationship.target_type is a valid key
                current_entity_schema = schema[relationship.target_type]
            else:
                # Relationship not found
                relationship_suggestions = suggest_similar_strings(
                    entity_name, set(current_entity_schema.relationships.keys())
                )
                errors.append(
                    ValidationError(
                        entity=entity_name,
                        field="",
                        error_type="unknown_entity",
                        message=f"Relationship '{entity_name}' does not exist in entity '{parent_entity}'",
                        suggestions=(
                            [f"Try '{s}' instead" for s in relationship_suggestions]
                            if relationship_suggestions
                            else []
                        ),
                    )
                )
                current_entity_schema = None

    # Validate scalar fields if we have a valid entity schema
    if current_entity_schema and entity_path.entity_name == entity_path.path[-1]:
        field_errors = _validate_direct_entity_fields(
            current_entity_schema, entity_path.fields
        )
        errors.extend(field_errors)

    return errors


def _validate_direct_entity_fields(
    entity_schema: EntitySchema, field_names: list[str]
) -> list[ValidationError]:
    """Validate fields against a specific entity schema.

    Args:
        entity_schema: Entity schema to validate against.
        field_names: List of field names to validate.

    Returns:
        List of validation errors found. Empty list indicates all fields are valid.

    Raises:
        AttributeError: If entity_schema structure is unexpected.
        TypeError: If field operations fail unexpectedly.
        (In practice, these would indicate bugs in schema processing)
    """
    errors = []
    all_valid_fields = set(entity_schema.fields) | set(entity_schema.relationships)

    for field_name in field_names:
        if field_name not in all_valid_fields:
            suggestions = suggest_similar_strings(field_name, all_valid_fields)
            errors.append(
                ValidationError(
                    entity=entity_schema.name,
                    field=field_name,
                    error_type="unknown_field",
                    message=f"Field '{field_name}' does not exist in entity '{entity_schema.name}'",
                    suggestions=(
                        [f"Try '{s}' instead" for s in suggestions]
                        if suggestions
                        else []
                    ),
                )
            )

    return errors
