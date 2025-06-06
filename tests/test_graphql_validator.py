"""Tests for GraphQL validation against Gen3 schema"""

from pathlib import Path

import pytest

from gen3_mcp.graphql_validator import validate_graphql


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


class TestValidationWithTestQueries:
    """Test validation using the provided test queries"""

    @pytest.mark.asyncio
    async def test_passing_query_1(self, schema_extract, test_queries):
        """Test that passing_test_1.graphql validates successfully"""
        query = test_queries["passing_1"]
        result = validate_graphql(query, schema_extract)

        assert result.is_valid is True
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_passing_query_2(self, schema_extract, test_queries):
        """Test that passing_test_2.graphql validates successfully"""
        query = test_queries["passing_2"]
        result = validate_graphql(query, schema_extract)

        assert result.is_valid is True
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_passing_query_3(self, schema_extract, test_queries):
        """Test that passing_test_3.graphql validates successfully"""
        query = test_queries["passing_3"]
        result = validate_graphql(query, schema_extract)

        assert result.is_valid is True
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_failing_query_1_syntax_error(self, schema_extract, test_queries):
        """Test that failing_test_1.graphql fails due to syntax error"""
        query = test_queries["failing_1"]
        result = validate_graphql(query, schema_extract)

        assert result.is_valid is False
        assert len(result.errors) == 1
        error = result.errors[0]
        assert error.error_type == "syntax_error"
        assert "syntax error" in error.message.lower()

    @pytest.mark.asyncio
    async def test_failing_query_2_unknown_field(self, schema_extract, test_queries):
        """Test that failing_test_2.graphql fails due to unknown field"""
        query = test_queries["failing_2"]
        result = validate_graphql(query, schema_extract)

        assert result.is_valid is False
        assert len(result.errors) == 1

        # Should have error about unknown field 'study_name'
        error = result.errors[0]
        assert error.error_type == "unknown_field"
        assert error.field == "study_name"

        # Should provide suggestions
        assert error.suggestions is not None
        assert len(error.suggestions) > 0

    @pytest.mark.asyncio
    async def test_failing_query_3_invalid_relation(self, schema_extract, test_queries):
        """Test that failing_test_3.graphql fails due to invalid relationship"""
        query = test_queries["failing_3"]
        result = validate_graphql(query, schema_extract)

        assert result.is_valid is False
        assert len(result.errors) > 0

        # Should have error about invalid relationship
        error = result.errors[0]
        assert error.error_type == "unknown_entity"
        assert (
            error.message
            == "Relationship 'samples' does not exist in entity 'aligned_reads_file'"
        )


class TestValidationErrorHandling:
    """Test error handling and suggestions"""

    @pytest.mark.asyncio
    async def test_unknown_entity_error(self, schema_extract):
        """Test validation of query with unknown entity"""
        query = "{ unknown_entity { id } }"
        result = validate_graphql(query, schema_extract)

        assert result.is_valid is False
        assert len(result.errors) == 1
        assert result.errors[0].error_type == "unknown_entity"
        assert "unknown_entity" in result.errors[0].message

        # Should provide entity suggestions
        assert result.errors[0].suggestions is not None

    @pytest.mark.asyncio
    async def test_unknown_field_error(self, schema_extract):
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

    @pytest.mark.asyncio
    async def test_similar_field_suggestions(self, schema_extract):
        """Test that similar field suggestions are provided"""
        query = "{ subject { id gendr } }"  # Typo in 'gender'
        result = validate_graphql(query, schema_extract)

        assert result.is_valid is False
        field_error = result.errors[0]
        assert field_error.field == "gendr"

        # Should suggest 'gender' as similar field
        assert "gender" in field_error.suggestions

    @pytest.mark.asyncio
    async def test_multiple_errors(self, schema_extract):
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

    @pytest.mark.asyncio
    async def test_valid_direct_relationship(self, schema_extract):
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

    @pytest.mark.asyncio
    async def test_valid_backref_relationship(self, schema_extract):
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

    @pytest.mark.asyncio
    async def test_valid_multi_level_relationship(self, schema_extract):
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

    @pytest.mark.asyncio
    async def test_invalid_relationship_field(self, schema_extract):
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

    @pytest.mark.asyncio
    async def test_valid_complex_query_all_entities(self, schema_extract):
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

    @pytest.mark.asyncio
    async def test_mixed_valid_invalid_fields(self, schema_extract):
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

    @pytest.mark.asyncio
    async def test_query_with_arguments_and_aliases(self, schema_extract):
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
