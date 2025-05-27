"""
GraphQL Query Validator against a Gen3 Schema

Takes a GraphQL query and minimal schema structure to validate field names and relationships.
"""

from dataclasses import dataclass
from typing import Dict, List, Set, Any, Optional, Tuple
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

class GraphQLFieldExtractor(Visitor):
    """Extract field information from GraphQL AST"""
    
    def __init__(self):
        super().__init__()
        self.extracted_fields: Dict[str, List[str]] = {}
        self.entity_stack: List[str] = []

    def enter_field(self, node: FieldNode, *_) -> None:
        field_name = node.name.value

        if node.selection_set:
            # This field has sub-selections - it's an entity/relationship
            self.entity_stack.append(field_name)
            if field_name not in self.extracted_fields:
                self.extracted_fields[field_name] = []
        else:
            # Scalar field - add to current entity
            if self.entity_stack:
                current_entity = self.entity_stack[-1]
                self.extracted_fields[current_entity].append(field_name)

    def leave_field(self, node: FieldNode, *_) -> None:
        if node.selection_set and self.entity_stack:
            self.entity_stack.pop()

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
        
        # Remove duplicates while preserving order
        result = {}
        for entity, fields in extractor.extracted_fields.items():
            result[entity] = list(dict.fromkeys(fields))
            
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

def validate_graphql_query(query: str, schema: SchemaExtract) -> ValidationResult:
    """
    Validate a GraphQL query against the minimal schema
    
    Args:
        query: GraphQL query string to validate
        schema: SchemaExtract containing entity and field definitions
        
    Returns:
        ValidationResult with validation status and any errors found
    """
    # First check GraphQL syntax
    try:
        extracted_fields = extract_fields(query)
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
    
    # Validate each entity and its fields
    for entity_name, field_names in extracted_fields.items():
        entity_errors = _validate_entity_fields(entity_name, field_names, schema, extracted_fields)
        errors.extend(entity_errors)
    
    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        extracted_fields=extracted_fields
    )

def _validate_entity_fields(
    entity_name: str, 
    field_names: List[str], 
    schema: SchemaExtract,
    all_extracted_fields: Dict[str, List[str]]
) -> List[ValidationError]:
    """Validate fields for a single entity"""
    errors = []
    
    # Check if this is a direct entity
    if entity_name in schema.entities:
        entity_schema = schema.entities[entity_name]
        errors.extend(_validate_direct_entity_fields(entity_schema, field_names))
        return errors
    
    # Check if this is a relationship field from another entity
    parent_entity, relationship = _find_parent_relationship(entity_name, schema, all_extracted_fields)
    
    if parent_entity and relationship:
        # Validate against the target entity's fields
        target_entity = schema.entities.get(relationship.target_type)
        if target_entity:
            errors.extend(_validate_direct_entity_fields(target_entity, field_names))
        else:
            errors.append(ValidationError(
                entity=entity_name,
                field="",
                error_type="unknown_entity",
                message=f"Target entity '{relationship.target_type}' for relationship '{entity_name}' does not exist",
                suggestions=[]
            ))
        return errors
    
    # Entity not found anywhere
    entity_suggestions = suggest_similar_strings(entity_name, set(schema.entities.keys()))
    errors.append(ValidationError(
        entity=entity_name,
        field="",
        error_type="unknown_entity", 
        message=f"Entity '{entity_name}' does not exist",
        suggestions=entity_suggestions
    ))
    
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

def _find_parent_relationship(
    relationship_name: str,
    schema: SchemaExtract, 
    all_extracted_fields: Dict[str, List[str]]
) -> Tuple[Optional[str], Optional[Relationship]]:
    """Find which entity this relationship belongs to"""
    
    # Look through all entities that appear in the query
    for potential_parent in all_extracted_fields.keys():
        if potential_parent in schema.entities:
            entity_schema = schema.entities[potential_parent]
            
            # Check direct relationship name match
            if relationship_name in entity_schema.relationships:
                return potential_parent, entity_schema.relationships[relationship_name]
            
            # Check for plural form of target type
            for rel in entity_schema.relationships.values():
                if relationship_name == f"{rel.target_type}s":
                    return potential_parent, rel
    
    return None, None
