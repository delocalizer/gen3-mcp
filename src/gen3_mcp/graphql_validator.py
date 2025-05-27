"""
GraphQL Query Validator against a Gen3 Schema

Takes a GraphQL query and minimal schema structure to validate field names and relationships.
"""

from dataclasses import dataclass
from typing import Dict, List, Set, Any, Optional
from graphql import parse, FieldNode, Visitor, visit
from graphql.error import GraphQLSyntaxError

from .schema_extract import SchemaExtract, EntitySchema, Relationship

@dataclass
class ValidationError:
    """Represents a validation error"""
    entity: str
    field: str
    error_type: str  # "syntax error", "unknown_entity", "unknown_field"
    message: str
    suggestions: List[str] = None

@dataclass
class ValidationResult:
    """Result of GraphQL query validation"""
    is_valid: bool
    errors: List[ValidationError]
    extracted_fields: Dict[str, List[str]]  # entity -> field names

@dataclass
class EntityPath:
    """Represents a path to an entity in the GraphQL query"""
    entity_name: str
    path: List[str]  # Full path from root to this entity
    fields: List[str]  # Scalar fields for this entity

class GraphQLFieldExtractor(Visitor):
    """Extract field information with path context from GraphQL AST"""
    
    def __init__(self):
        super().__init__()
        self.entity_paths: Dict[str, EntityPath] = {}  # entity_name -> EntityPath
        self.path_stack: List[str] = []  # Current path from root

    def enter_field(self, node: FieldNode, *_) -> None:
        field_name = node.name.value

        if node.selection_set:
            # This field has sub-selections - it's an entity/relationship
            current_path = self.path_stack + [field_name]
            
            # Store the path for this entity
            self.entity_paths[field_name] = EntityPath(
                entity_name=field_name,
                path=current_path.copy(),
                fields=[]
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

def extract_fields(query: str) -> Dict[str, List[str]]:
    """
    Extract entity and field information from GraphQL query
    
    Args:
        query: GraphQL query string
        
    Returns:
        Dict mapping entity names to list of field names
        
    Raises:
        GraphQLSyntaxError: If query has syntax errors
    """
    try:
        ast = parse(query)
        extractor = GraphQLFieldExtractor()
        visit(ast, extractor)
        
        # Convert to legacy format for backwards compatibility
        result = {}
        for entity_path in extractor.entity_paths.values():
            result[entity_path.entity_name] = list(dict.fromkeys(entity_path.fields))
            
        return result
    except GraphQLSyntaxError as e:
        raise GraphQLSyntaxError(f"Invalid GraphQL syntax: {e}") from e

def suggest_similar_strings(target: str, candidates: Set[str], threshold: float = 0.6) -> List[str]:
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
            errors=[ValidationError(
                entity="",
                field="",
                error_type="syntax_error", 
                message=f"GraphQL syntax error: {e}",
                suggestions=[]
            )],
            extracted_fields={}
        )
    
    errors = []
    
    # Validate each entity path
    for entity_path in extractor.entity_paths.values():
        path_errors = _validate_entity_path(entity_path, schema)
        errors.extend(path_errors)
    
    # Convert to legacy format for return value
    extracted_fields = {}
    for entity_path in extractor.entity_paths.values():
        extracted_fields[entity_path.entity_name] = entity_path.fields
    
    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        extracted_fields=extracted_fields
    )

def _validate_entity_path(entity_path: EntityPath, schema: SchemaExtract) -> List[ValidationError]:
    """Validate an entity using its path context"""
    errors = []
    
    # Walk through the path to validate each step
    current_entity_schema = None
    
    for i, entity_name in enumerate(entity_path.path):
        if i == 0:
            # Root entity - must exist directly in schema
            if entity_name not in schema.entities:
                entity_suggestions = suggest_similar_strings(entity_name, set(schema.entities.keys()))
                errors.append(ValidationError(
                    entity=entity_name,
                    field="",
                    error_type="unknown_entity",
                    message=f"Root entity '{entity_name}' does not exist",
                    suggestions=entity_suggestions
                ))
                return errors  # Can't continue without valid root
            current_entity_schema = schema.entities[entity_name]
        else:
            # Relationship entity - must be accessible from parent
            parent_entity = entity_path.path[i-1]
            
            if not current_entity_schema:
                continue  # Parent was invalid, skip
                
            # Check if this is a valid relationship from parent
            if entity_name in current_entity_schema.relationships:
                relationship = current_entity_schema.relationships[entity_name]
                target_entity_schema = schema.entities.get(relationship.target_type)
                
                if target_entity_schema:
                    current_entity_schema = target_entity_schema
                else:
                    errors.append(ValidationError(
                        entity=entity_name,
                        field="",
                        error_type="unknown_entity",
                        message=f"Target entity '{relationship.target_type}' for relationship '{entity_name}' does not exist",
                        suggestions=[]
                    ))
                    current_entity_schema = None
            else:
                # Relationship not found
                relationship_suggestions = suggest_similar_strings(
                    entity_name, 
                    set(current_entity_schema.relationships.keys())
                )
                errors.append(ValidationError(
                    entity=entity_name,
                    field="",
                    error_type="unknown_entity",
                    message=f"Relationship '{entity_name}' does not exist in entity '{parent_entity}'",
                    suggestions=relationship_suggestions
                ))
                current_entity_schema = None
    
    # Validate scalar fields if we have a valid entity schema
    if current_entity_schema and entity_path.entity_name == entity_path.path[-1]:
        errors.extend(_validate_direct_entity_fields(current_entity_schema, entity_path.fields))
    
    return errors

def _validate_direct_entity_fields(entity_schema: EntitySchema, field_names: List[str]) -> List[ValidationError]:
    """Validate fields against a specific entity schema"""
    errors = []
    all_valid_fields = entity_schema.fields | set(entity_schema.relationships.keys())
    
    for field_name in field_names:
        if field_name not in all_valid_fields:
            suggestions = suggest_similar_strings(field_name, all_valid_fields)
            errors.append(ValidationError(
                entity=entity_schema.name,
                field=field_name,
                error_type="unknown_field",
                message=f"Field '{field_name}' does not exist in entity '{entity_schema.name}'",
                suggestions=suggestions
            ))
    
    return errors

# The old _find_parent_relationship function is no longer needed with path-based validation
