"""Tests for GraphQL validation against Gen3 schema"""

import json
import pytest
from pathlib import Path

from gen3_mcp.schema_extract import SchemaExtract
from gen3_mcp.graphql_validator import (
    validate_graphql,
    extract_fields,
    ValidationResult,
    ValidationError,
)


@pytest.fixture(scope="session")
def test_schema():
    """Load the test schema from ex_schema.json"""
    schema_path = Path(__file__).parent / "ex_schema.json"
    with open(schema_path) as f:
        return json.load(f)


@pytest.fixture(scope="session")
def schema_extract(test_schema):
    """Create SchemaExtract from test schema"""
    return SchemaExtract.from_full_schema(test_schema)


@pytest.fixture(scope="session") 
def test_queries():
    """Load all test GraphQL queries"""
    test_dir = Path(__file__).parent
    queries = {}
    
    # Load passing queries
    for i in range(1, 4):
        path = test_dir / f"passing_test_{i}.graphql"
        with open(path) as f:
            queries[f"passing_{i}"] = f.read()
    
    # Load failing queries
    for i in range(1, 4):
        path = test_dir / f"failing_test_{i}.graphql"
        with open(path) as f:
            queries[f"failing_{i}"] = f.read()
    
    return queries


class TestSchemaExtract:
    """Test SchemaExtract functionality"""
    
    def test_schema_extract_creation(self, test_schema, schema_extract):
        """Test that SchemaExtract is created correctly from test schema"""
        assert len(schema_extract.entities) == 5  # subject, sample, study, aliquot, aligned_reads_file
        
        # Check that expected entities are present
        expected_entities = {"subject", "sample", "study", "aliquot", "aligned_reads_file"}
        assert set(schema_extract.entities.keys()) == expected_entities
    
    def test_entity_fields_extraction(self, schema_extract):
        """Test that entity fields are extracted correctly"""
        subject = schema_extract.entities["subject"]
        
        # Should have standard GraphQL fields
        assert "id" in subject.fields
        assert "submitter_id" in subject.fields
        assert "type" in subject.fields
        
        # Should have entity-specific fields
        assert "gender" in subject.fields
        assert "race" in subject.fields
        assert "ethnicity" in subject.fields
        assert "age_at_enrollment" in subject.fields
    
    def test_entity_relationships_extraction(self, schema_extract):
        """Test that relationships are extracted correctly"""
        subject = schema_extract.entities["subject"]
        
        # Subject should have relationship to studies
        assert "studies" in subject.relationships
        studies_rel = subject.relationships["studies"]
        assert studies_rel.target_type == "study"
        assert studies_rel.backref == "subjects"
    
    def test_backref_relationships_added(self, schema_extract):
        """Test that backref relationships are added correctly"""
        study = schema_extract.entities["study"]
        
        # Study should have backref relationship from subject
        assert "subjects" in study.relationships
        subjects_rel = study.relationships["subjects"]
        assert subjects_rel.target_type == "subject"
        assert subjects_rel.backref == "studies"


class TestFieldExtraction:
    """Test GraphQL field extraction functionality"""
    
    def test_simple_field_extraction(self):
        """Test extraction from simple query"""
        query = "{ subject { id submitter_id gender } }"
        result = extract_fields(query)
        
        expected = {"subject": ["id", "submitter_id", "gender"]}
        assert result == expected
    
    def test_nested_field_extraction(self):
        """Test extraction from nested query"""
        query = """
        {
            subject {
                id
                gender
                samples {
                    id
                    sample_type
                }
            }
        }
        """
        result = extract_fields(query)
        
        expected = {
            "subject": ["id", "gender"],
            "samples": ["id", "sample_type"]
        }
        assert result == expected
    
    def test_deeply_nested_extraction(self):
        """Test extraction from deeply nested query"""
        query = """
        {
            subject {
                id
                samples {
                    id
                    aliquots {
                        id
                        aligned_reads_files {
                            submitter_id
                        }
                    }
                }
            }
        }
        """
        result = extract_fields(query)
        
        expected = {
            "subject": ["id"],
            "samples": ["id"],
            "aliquots": ["id"],
            "aligned_reads_files": ["submitter_id"]
        }
        assert result == expected
    
    def test_syntax_error_handling(self):
        """Test that syntax errors are handled properly"""
        invalid_query = "{ subject { id }"  # Missing closing brace
        
        with pytest.raises(Exception):  # Should raise GraphQLSyntaxError
            extract_fields(invalid_query)


class TestValidationWithTestQueries:
    """Test validation using the provided test queries"""
    
    def test_passing_query_1(self, schema_extract, test_queries):
        """Test that passing_test_1.graphql validates successfully"""
        query = test_queries["passing_1"]
        result = validate_graphql(query, schema_extract)
        
        assert result.is_valid is True
        assert len(result.errors) == 0
        
        # Check that fields were extracted correctly
        assert "subject" in result.extracted_fields
        assert "studies" in result.extracted_fields
        assert "samples" in result.extracted_fields
    
    def test_passing_query_2(self, schema_extract, test_queries):
        """Test that passing_test_2.graphql validates successfully"""
        query = test_queries["passing_2"]
        result = validate_graphql(query, schema_extract)
        
        assert result.is_valid is True
        assert len(result.errors) == 0
        
        # Check nested relationship validation
        assert "subject" in result.extracted_fields
        assert "samples" in result.extracted_fields
        assert "aliquots" in result.extracted_fields
        assert "aligned_reads_files" in result.extracted_fields
    
    def test_passing_query_3(self, schema_extract, test_queries):
        """Test that passing_test_3.graphql validates successfully"""
        query = test_queries["passing_3"]
        result = validate_graphql(query, schema_extract)
        
        assert result.is_valid is True
        assert len(result.errors) == 0
        
        # Check that aligned_reads_file relationships are validated
        assert "aligned_reads_file" in result.extracted_fields
        assert "subjects" in result.extracted_fields
        assert "aliquots" in result.extracted_fields
    
    def test_failing_query_1_syntax_error(self, schema_extract, test_queries):
        """Test that failing_test_1.graphql fails due to syntax error"""
        query = test_queries["failing_1"]
        result = validate_graphql(query, schema_extract)
        
        assert result.is_valid is False
        assert len(result.errors) > 0
        assert result.errors[0].error_type == "syntax_error"
        assert "syntax error" in result.errors[0].message.lower()
    
    def test_failing_query_2_unknown_field(self, schema_extract, test_queries):
        """Test that failing_test_2.graphql fails due to unknown field"""
        query = test_queries["failing_2"]
        result = validate_graphql(query, schema_extract)
        
        assert result.is_valid is False
        assert len(result.errors) > 0
        
        # Should have error about unknown field 'study_name'
        field_errors = [e for e in result.errors if e.error_type == "unknown_field" and e.field == "study_name"]
        assert len(field_errors) > 0
        
        # Should provide suggestions
        error = field_errors[0]
        assert error.suggestions is not None
        assert len(error.suggestions) > 0
    
    def test_failing_query_3_unknown_entity(self, schema_extract, test_queries):
        """Test that failing_test_3.graphql fails due to unknown entity or invalid relationship"""
        query = test_queries["failing_3"]
        result = validate_graphql(query, schema_extract)
        
        assert result.is_valid is False
        assert len(result.errors) > 0
        
        # Should have error about unknown entity or invalid relationship
        assert any(error.error_type in ["unknown_entity", "unknown_field"] for error in result.errors)


class TestValidationErrorHandling:
    """Test error handling and suggestions"""
    
    def test_unknown_entity_error(self, schema_extract):
        """Test validation of query with unknown entity"""
        query = "{ unknown_entity { id } }"
        result = validate_graphql(query, schema_extract)
        
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert result.errors[0].error_type == "unknown_entity"
        assert "unknown_entity" in result.errors[0].message
        
        # Should provide entity suggestions
        assert result.errors[0].suggestions is not None
    
    def test_unknown_field_error(self, schema_extract):
        """Test validation of query with unknown field"""
        query = "{ subject { id unknown_field } }"
        result = validate_graphql(query, schema_extract)
        
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert result.errors[0].error_type == "unknown_field"
        assert result.errors[0].field == "unknown_field"
        assert result.errors[0].entity == "subject"
        
        # Should provide field suggestions
        assert result.errors[0].suggestions is not None
    
    def test_similar_field_suggestions(self, schema_extract):
        """Test that similar field suggestions are provided"""
        query = "{ subject { id gendr } }"  # Typo in 'gender'
        result = validate_graphql(query, schema_extract)
        
        assert result.is_valid is False
        field_error = result.errors[0]
        assert field_error.field == "gendr"
        
        # Should suggest 'gender' as similar field
        assert "gender" in field_error.suggestions
    
    def test_multiple_errors(self, schema_extract):
        """Test handling of multiple validation errors"""
        query = """
        {
            subject {
                id
                unknown_field1
                unknown_field2
            }
        }
        """
        result = validate_graphql(query, schema_extract)
        
        assert result.is_valid is False
        assert len(result.errors) == 2
        
        # Both errors should be for unknown fields
        error_fields = {error.field for error in result.errors}
        assert error_fields == {"unknown_field1", "unknown_field2"}


class TestRelationshipValidation:
    """Test validation of entity relationships"""
    
    def test_valid_direct_relationship(self, schema_extract):
        """Test validation of valid direct relationship"""
        query = """
        {
            subject {
                id
                studies {
                    id
                    study_description
                }
            }
        }
        """
        result = validate_graphql(query, schema_extract)
        
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    def test_valid_backref_relationship(self, schema_extract):
        """Test validation of valid backref relationship"""
        query = """
        {
            study {
                id
                subjects {
                    id
                    gender
                }
            }
        }
        """
        result = validate_graphql(query, schema_extract)
        
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    def test_valid_multi_level_relationship(self, schema_extract):
        """Test validation of multi-level relationships"""
        query = """
        {
            subject {
                id
                samples {
                    id
                    aliquots {
                        id
                        aligned_reads_files {
                            submitter_id
                        }
                    }
                }
            }
        }
        """
        result = validate_graphql(query, schema_extract)
        
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    def test_invalid_relationship_field(self, schema_extract):
        """Test validation fails for invalid field in relationship"""
        query = """
        {
            subject {
                id
                studies {
                    id
                    invalid_study_field
                }
            }
        }
        """
        result = validate_graphql(query, schema_extract)
        
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert result.errors[0].error_type == "unknown_field"
        assert result.errors[0].field == "invalid_study_field"


class TestComplexScenarios:
    """Test complex validation scenarios"""
    
    def test_valid_complex_query_all_entities(self, schema_extract):
        """Test validation of complex query involving all entities"""
        query = """
        {
            subject(first: 2) {
                id
                submitter_id
                gender
                age_at_enrollment
                studies {
                    id
                    study_description
                }
                samples {
                    id
                    sample_type
                    anatomic_site
                    aliquots {
                        id
                        concentration
                        aligned_reads_files {
                            submitter_id
                            file_name
                            file_size
                        }
                    }
                }
            }
        }
        """
        result = validate_graphql(query, schema_extract)
        
        assert result.is_valid is True
        assert len(result.errors) == 0
        
        # All entities should be in extracted fields
        expected_entities = {"subject", "studies", "samples", "aliquots", "aligned_reads_files"}
        assert set(result.extracted_fields.keys()) == expected_entities
    
    def test_mixed_valid_invalid_fields(self, schema_extract):
        """Test query with mix of valid and invalid fields"""
        query = """
        {
            subject {
                id
                gender          # valid
                invalid_field1  # invalid
                age_at_enrollment # valid
                invalid_field2  # invalid
            }
        }
        """
        result = validate_graphql(query, schema_extract)
        
        assert result.is_valid is False
        assert len(result.errors) == 2
        
        invalid_fields = {error.field for error in result.errors}
        assert invalid_fields == {"invalid_field1", "invalid_field2"}
    
    def test_query_with_arguments_and_aliases(self, schema_extract):
        """Test that queries with arguments and aliases validate correctly"""
        query = """
        {
            subject(first: 10, orderBy: "created_datetime") {
                identifier: id
                sub_id: submitter_id
                sex: gender
                samples(first: 5) {
                    sample_id: id
                    type: sample_type
                }
            }
        }
        """
        result = validate_graphql(query, schema_extract)
        
        assert result.is_valid is True
        assert len(result.errors) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
