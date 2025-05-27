"""
GraphQL Query Validator against a Gen3 Schema

Takes a GraphQL query and minimal schema structure to validate field names and relationships.
"""

from dataclasses import dataclass
from typing import Optional

from graphql import FieldNode, Visitor, parse, visit
from graphql.error import GraphQLSyntaxError

from .schema_extract import EntitySchema, SchemaExtract


@dataclass
class ValidationError:
    """Represents a validation error"""

    entity: str
    field: str
    error_type: str  # "syntax error", "unknown_entity", "unknown_field"
    message: str
    suggestions: list[str] = None


@dataclass
class QueryNode:
    """Represents a node in the validated GraphQL query tree"""

    entity_name: str  # The name used in the query ("samples")
    resolved_entity: str  # The schema entity it resolves to ("sample")
    fields: list[str]  # Scalar fields selected
    children: dict[str, "QueryNode"]  # Nested selections


@dataclass
class ValidationResult:
    """Result of GraphQL query validation"""

    is_valid: bool
    errors: list[ValidationError]
    query_tree: Optional["QueryNode"]  # Hierarchical query structure


@dataclass
class EntityPath:
    """Represents a path to an entity in the GraphQL query"""

    entity_name: str
    path: list[str]  # Full path from root to this entity
    fields: list[str]  # Scalar fields for this entity


class GraphQLFieldExtractor(Visitor):
    """Extract field information with path context from GraphQL AST"""

    def __init__(self):
        super().__init__()
        self.entity_paths: dict[str, EntityPath] = {}  # entity_name -> EntityPath
        self.path_stack: list[str] = []  # Current path from root

    def enter_field(self, node: FieldNode, *_) -> None:
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
        if node.selection_set and self.path_stack:
            self.path_stack.pop()


def suggest_similar_strings(
    target: str, candidates: set[str], threshold: float = 0.6
) -> list[str]:
    """Suggest similar strings using basic similarity scoring"""
    from difflib import SequenceMatcher

    suggestions = []
    for candidate in candidates:
        similarity = SequenceMatcher(None, target.lower(), candidate.lower()).ratio()
        if similarity >= threshold:
            suggestions.append((candidate, similarity))

    # Sort by similarity (descending) and return just the strings
    suggestions.sort(key=lambda x: x[1], reverse=True)
    return [s[0] for s in suggestions[:3]]  # Top 3 suggestions


def validate_graphql(query: str, schema: SchemaExtract) -> ValidationResult:
    """
    Validate a GraphQL query against the minimal schema using path-based validation

    Args:
        query: GraphQL query string to validate
        schema: SchemaExtract containing entity and field definitions

    Returns:
        ValidationResult with validation status and any errors found
    """
    # First check GraphQL syntax and extract paths
    try:
        ast = parse(query)
        extractor = GraphQLFieldExtractor()
        visit(ast, extractor)
    except GraphQLSyntaxError as e:
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
            query_tree=None,
        )

    errors = []

    # Validate each entity path
    for entity_path in extractor.entity_paths.values():
        path_errors = _validate_entity_path(entity_path, schema)
        errors.extend(path_errors)

    # Build query tree from validated paths
    query_tree = (
        _build_query_tree(extractor.entity_paths, schema)
        if extractor.entity_paths
        else None
    )

    return ValidationResult(
        is_valid=len(errors) == 0, errors=errors, query_tree=query_tree
    )


def _validate_entity_path(
    entity_path: EntityPath, schema: SchemaExtract
) -> list[ValidationError]:
    """Validate an entity using its path context"""
    errors = []

    # Walk through the path to validate each step
    current_entity_schema = None

    for i, entity_name in enumerate(entity_path.path):
        if i == 0:
            # Root entity - must exist directly in schema
            if entity_name not in schema.entities:
                entity_suggestions = suggest_similar_strings(
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
                target_entity_schema = schema.entities.get(relationship.target_type)

                if target_entity_schema:
                    current_entity_schema = target_entity_schema
                else:
                    errors.append(
                        ValidationError(
                            entity=entity_name,
                            field="",
                            error_type="unknown_entity",
                            message=f"Target entity '{relationship.target_type}' for relationship '{entity_name}' does not exist",
                            suggestions=[],
                        )
                    )
                    current_entity_schema = None
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
                        suggestions=relationship_suggestions,
                    )
                )
                current_entity_schema = None

    # Validate scalar fields if we have a valid entity schema
    if current_entity_schema and entity_path.entity_name == entity_path.path[-1]:
        errors.extend(
            _validate_direct_entity_fields(current_entity_schema, entity_path.fields)
        )

    return errors


def _validate_direct_entity_fields(
    entity_schema: EntitySchema, field_names: list[str]
) -> list[ValidationError]:
    """Validate fields against a specific entity schema"""
    errors = []
    all_valid_fields = entity_schema.fields | set(entity_schema.relationships.keys())

    for field_name in field_names:
        if field_name not in all_valid_fields:
            suggestions = suggest_similar_strings(field_name, all_valid_fields)
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


def _build_query_tree(
    entity_paths: dict[str, EntityPath], schema: SchemaExtract
) -> QueryNode | None:
    """Build a hierarchical query tree from entity paths"""
    if not entity_paths:
        return None

    # Find the root entity (path length 1)
    root_path = None
    for entity_path in entity_paths.values():
        if len(entity_path.path) == 1:
            root_path = entity_path
            break

    if not root_path:
        return None

    def build_node(current_path: list[str]) -> QueryNode:
        # Find the entity_path that matches this path
        matching_entity_path = None
        for entity_path in entity_paths.values():
            if entity_path.path == current_path:
                matching_entity_path = entity_path
                break

        if not matching_entity_path:
            # Create a node with minimal info if path not found
            entity_name = current_path[-1]
            return QueryNode(
                entity_name=entity_name,
                resolved_entity=entity_name,  # Fallback
                fields=[],
                children={},
            )

        # Determine resolved entity type
        resolved_entity = _resolve_entity_type(current_path, schema)

        # Build children for paths that extend this one
        children = {}
        current_path_str = "/".join(current_path)

        for entity_path in entity_paths.values():
            path_str = "/".join(entity_path.path)
            # If this path extends current path by exactly one level
            if (
                path_str.startswith(current_path_str + "/")
                and len(entity_path.path) == len(current_path) + 1
            ):
                child_name = entity_path.path[-1]
                children[child_name] = build_node(entity_path.path)

        return QueryNode(
            entity_name=matching_entity_path.entity_name,
            resolved_entity=resolved_entity,
            fields=matching_entity_path.fields.copy(),
            children=children,
        )

    return build_node(root_path.path)


def _resolve_entity_type(path: list[str], schema: SchemaExtract) -> str:
    """Resolve what schema entity type a path resolves to"""
    if not path:
        return "unknown"

    # Start with root entity
    if path[0] not in schema.entities:
        return path[-1]  # Fallback to entity name

    current_schema = schema.entities[path[0]]

    # Walk through relationships
    for i in range(1, len(path)):
        relationship_name = path[i]
        if relationship_name in current_schema.relationships:
            relationship = current_schema.relationships[relationship_name]
            target_schema = schema.entities.get(relationship.target_type)
            if target_schema:
                current_schema = target_schema
            else:
                return path[-1]  # Fallback
        else:
            return path[-1]  # Fallback

    return current_schema.name
