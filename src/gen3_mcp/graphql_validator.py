"""GraphQL Query Validator against a Gen3 Schema.

Takes a GraphQL query and minimal schema structure to validate field names and relationships.
"""

import logging
from dataclasses import dataclass

from graphql import FieldNode, Visitor, parse, visit
from graphql.error import GraphQLSyntaxError

from .schema_extract import EntitySchema, SchemaExtract

logger = logging.getLogger("gen3-mcp.graphql_validator")


@dataclass
class EntityPath:
    """Represents a path to an entity in the GraphQL query."""

    entity_name: str
    path: list[str]  # Full path from root to this entity
    fields: list[str]  # Scalar fields for this entity


@dataclass
class ValidationError:
    """Represents a validation error."""

    entity: str
    field: str
    error_type: str  # "syntax error", "unknown_entity", "unknown_field"
    message: str
    suggestions: list[str] = None


@dataclass
class ValidationResult:
    """Result of GraphQL query validation."""

    is_valid: bool
    errors: list[ValidationError]


class GraphQLFieldExtractor(Visitor):
    """Extract field information with path context from GraphQL AST."""

    def __init__(self):
        """Initialize GraphQLFieldExtractor."""
        super().__init__()
        self.entity_paths: dict[str, EntityPath] = {}
        self.path_stack: list[str] = []

    def enter_field(self, node: FieldNode, *_) -> None:
        """Process field node on entry.

        Args:
            node: GraphQL field node.
            *_: Unused visitor arguments.
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
        """
        if node.selection_set and self.path_stack:
            self.path_stack.pop()


def validate_graphql(query: str, schema: SchemaExtract) -> ValidationResult:
    """Validate a GraphQL query against the minimal schema using path-based validation.

    Args:
        query: GraphQL query string to validate.
        schema: SchemaExtract containing entity and field definitions.

    Returns:
        ValidationResult with validation status and any errors found.
    """
    logger.debug("Starting GraphQL validation")

    # First check GraphQL syntax and extract paths
    try:
        ast = parse(query)
        extractor = GraphQLFieldExtractor()
        visit(ast, extractor)
    except GraphQLSyntaxError as e:
        logger.error(f"GraphQL syntax error: {e}")
        return ValidationResult(
            is_valid=False,
            errors=[
                ValidationError(
                    entity="",
                    field="",
                    error_type="syntax_error",
                    message=f"GraphQL syntax error: {e}",
                    suggestions=[],
                )
            ],
        )

    errors = []

    # Validate each entity path
    for entity_path in extractor.entity_paths.values():
        # NOTE this collects all errors; a more efficient but less informative
        # approach is to start at the shortest path and bail at the first error
        path_errors = _validate_entity_path(entity_path, schema)
        errors.extend(path_errors)

    is_valid = len(errors) == 0
    logger.info(f"Validation complete - valid: {is_valid}, errors: {len(errors)}")

    return ValidationResult(is_valid=is_valid, errors=errors)


def _suggest_similar_strings(
    target: str, candidates: set[str], threshold: float = 0.6, number=3
) -> list[str]:
    """Suggest similar strings using basic similarity scoring.

    Args:
        target: String to match against.
        candidates: Set of candidate strings.
        threshold: Minimum similarity threshold.
        number: Maximum number of suggestions

    Returns:
        List of similar strings.
    """
    from difflib import SequenceMatcher

    suggestions = []
    for candidate in candidates:
        similarity = SequenceMatcher(None, target.lower(), candidate.lower()).ratio()
        if similarity >= threshold:
            suggestions.append((candidate, similarity))

    # Sort by similarity (descending) and return just the strings
    suggestions.sort(key=lambda x: x[1], reverse=True)
    return [s[0] for s in suggestions[:number]]


def _validate_entity_path(
    entity_path: EntityPath, schema: SchemaExtract
) -> list[ValidationError]:
    """Validate an entity using its path context.

    Args:
        entity_path: EntityPath to validate.
        schema: SchemaExtract containing entity definitions.

    Returns:
        List of validation errors.
    """
    logger.debug(f"Validating entity path: {'/'.join(entity_path.path)}")
    errors = []

    # Walk through the path to validate each step
    current_entity_schema = None

    for i, entity_name in enumerate(entity_path.path):
        if i == 0:
            # Root entity - must exist directly in schema
            if entity_name not in schema.entities:
                entity_suggestions = _suggest_similar_strings(
                    entity_name, set(schema.entities.keys())
                )
                errors.append(
                    ValidationError(
                        entity=entity_name,
                        field="",
                        error_type="unknown_entity",
                        message=f"Root entity '{entity_name}' does not exist",
                        suggestions=entity_suggestions,
                    )
                )
                return errors  # Can't continue without valid root
            current_entity_schema = schema.entities[entity_name]
        else:
            # Relationship entity - must be accessible from parent
            parent_entity = entity_path.path[i - 1]

            if not current_entity_schema:
                continue  # Parent was invalid, skip

            # Check if this is a valid relationship from parent
            if entity_name in current_entity_schema.relationships:
                relationship = current_entity_schema.relationships[entity_name]
                # by schema extract construction, relationship.target_type is a valid key
                current_entity_schema = schema.entities[relationship.target_type]
            else:
                # Relationship not found
                relationship_suggestions = _suggest_similar_strings(
                    entity_name, set(current_entity_schema.relationships.keys())
                )
                errors.append(
                    ValidationError(
                        entity=entity_name,
                        field="",
                        error_type="unknown_entity",
                        message=f"Relationship '{entity_name}' does not exist in entity '{parent_entity}'",
                        suggestions=relationship_suggestions,
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
        List of validation errors.
    """
    errors = []
    all_valid_fields = entity_schema.fields | set(entity_schema.relationships.keys())

    for field_name in field_names:
        if field_name not in all_valid_fields:
            suggestions = _suggest_similar_strings(field_name, all_valid_fields)
            errors.append(
                ValidationError(
                    entity=entity_schema.name,
                    field=field_name,
                    error_type="unknown_field",
                    message=f"Field '{field_name}' does not exist in entity '{entity_schema.name}'",
                    suggestions=suggestions,
                )
            )

    return errors
