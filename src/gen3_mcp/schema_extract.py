# Data structure extracted from full Gen3 schema for GraphQL validation

from dataclasses import dataclass
from typing import Dict, Set, List, Any
import json

@dataclass
class Relationship:
    """A relationship between entities"""
    name: str           # The field name used in GraphQL (e.g., "studies")  
    target_type: str    # The target entity type (e.g., "study")
    backref: str        # The reverse field name (e.g., "subjects")

@dataclass  
class EntitySchema:
    """Minimal entity schema for GraphQL validation"""
    name: str                               # Entity name (e.g., "subject")
    fields: Set[str]                        # All valid scalar fields
    relationships: Dict[str, Relationship]  # Field name -> Relationship

class SchemaExtract:
    """Minimal schema structure for efficient GraphQL validation"""
    
    def __init__(self):
        self.entities: Dict[str, EntitySchema] = {}
    
    @classmethod
    def from_full_schema(cls, full_schema: Dict[str, Any]) -> 'SchemaExtract':
        """Extract minimal validation schema from full Gen3 schema"""
        extract = cls()
        
        for entity_name, entity_def in full_schema.items():
            # Extract scalar fields from properties
            fields = set()
            properties = entity_def.get("properties", {})
            
            for prop_name, prop_def in properties.items():
                # Skip relationship fields (they have complex object structures)
                if isinstance(prop_def, dict):
                    # Simple heuristic: if it has 'anyOf' with object refs, it's a relationship
                    if "anyOf" in prop_def:
                        continue
                    # If it's a simple type, it's a scalar field
                    if "type" in prop_def or "enum" in prop_def:
                        fields.add(prop_name)
            
            # Add standard GraphQL fields always available
            fields.update(["id", "submitter_id", "type", "created_datetime", "updated_datetime"])
            
            # Extract relationships from links
            relationships = {}
            links = entity_def.get("links", [])
            
            for link in links:
                # Process direct relationship
                if link.get("name") and link.get("target_type"):
                    relationships[link["name"]] = Relationship(
                        name=link["name"],
                        target_type=link["target_type"], 
                        backref=link.get("backref", "")
                    )
                
                # Process subgroup relationships
                subgroup = link.get("subgroup", [])
                if subgroup:
                    for sublink in subgroup:
                        if sublink.get("name") and sublink.get("target_type"):
                            relationships[sublink["name"]] = Relationship(
                                name=sublink["name"],
                                target_type=sublink["target_type"],
                                backref=sublink.get("backref", "")
                            )
            
            extract.entities[entity_name] = EntitySchema(
                name=entity_name,
                fields=fields,
                relationships=relationships
            )
        
        # Add backref relationships (reverse lookups)
        cls._add_backref_relationships(extract)
        
        return extract
    
    @classmethod
    def _add_backref_relationships(cls, extract: 'SchemaExtract'):
        """Add backref relationships to entities"""
        # For each entity's relationships, add the backref to the target entity
        for entity_name, entity in extract.entities.items():
            for rel in entity.relationships.values():
                target_entity = extract.entities.get(rel.target_type)
                if target_entity and rel.backref:
                    # Add backref relationship to target entity
                    target_entity.relationships[rel.backref] = Relationship(
                        name=rel.backref,
                        target_type=entity_name,
                        backref=rel.name
                    )

# Example usage:
def extract_from_file(schema_file_path: str) -> SchemaExtract:
    """Return schema extract read from full schema in a JSON file"""
    with open(schema_file_path, 'r') as f:
        full_schema = json.load(f)
    return SchemaExtract.from_full_schema(full_schema)

# For our test case, this would produce:
# {
#   "subject": EntitySchema(
#       name="subject",
#       fields={"id", "submitter_id", "type", "gender", "race", "ethnicity", "age_at_enrollment", ...},
#       relationships={
#           "studies": Relationship(name="studies", target_type="study", backref="subjects"),
#           "samples": Relationship(name="samples", target_type="sample", backref="subjects")  # from backref
#       }
#   ),
#   "sample": EntitySchema(
#       name="sample", 
#       fields={"id", "submitter_id", "sample_type", "anatomic_site", "composition", ...},
#       relationships={
#           "subjects": Relationship(name="subjects", target_type="subject", backref="samples")
#       }
#   ),
#   "study": EntitySchema(
#       name="study",
#       fields={"id", "submitter_id", "study_description", "data_description", ...},
#       relationships={
#           "projects": Relationship(name="projects", target_type="project", backref="studies"),
#           "subjects": Relationship(name="subjects", target_type="subject", backref="studies")  # from backref
#       }
#   )
# }
