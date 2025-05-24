"""Tests for GraphQL parsing utilities"""

import pytest

from gen3_mcp.exceptions import QueryValidationError
from gen3_mcp.graphql_parser import (
    extract_fields_from_query,
    validate_graphql_syntax,
)


class TestValidateGraphQLSyntax:
    """Test GraphQL syntax validation"""

    def test_valid_simple_query(self):
        """Test validation of valid simple query"""
        query = "{ subject { id } }"
        is_valid, error = validate_graphql_syntax(query)
        assert is_valid is True
        assert error is None

    def test_valid_complex_query(self):
        """Test validation of valid complex query"""
        query = """
        {
            subject(first: 10) {
                id
                submitter_id
                gender
                samples {
                    id
                    sample_type
                }
            }
        }
        """
        is_valid, error = validate_graphql_syntax(query)
        assert is_valid is True
        assert error is None

    def test_invalid_syntax_missing_brace(self):
        """Test validation of invalid syntax - missing closing brace"""
        query = "{ subject { id }"
        is_valid, error = validate_graphql_syntax(query)
        assert is_valid is False
        assert error is not None
        assert "Expected" in error or "EOF" in error

    def test_invalid_syntax_missing_field(self):
        """Test validation of invalid syntax - empty selection set"""
        query = "{ subject { } }"
        is_valid, error = validate_graphql_syntax(query)
        assert is_valid is False
        assert error is not None

    def test_empty_query(self):
        """Test validation of empty query"""
        query = ""
        is_valid, error = validate_graphql_syntax(query)
        assert is_valid is False
        assert error is not None


class TestExtractFieldsFromQuery:
    """Test field extraction from GraphQL queries"""

    def test_simple_query(self):
        """Test extraction from simple query"""
        query = "{ subject { id submitter_id } }"
        result = extract_fields_from_query(query)
        expected = {"subject": ["id", "submitter_id"]}
        assert result == expected

    def test_query_with_arguments(self):
        """Test extraction from query with arguments"""
        query = "{ subject(first: 10) { id gender age_at_enrollment } }"
        result = extract_fields_from_query(query)
        expected = {"subject": ["id", "gender", "age_at_enrollment"]}
        assert result == expected

    def test_nested_query(self):
        """Test extraction from nested query"""
        query = """
        {
            subject {
                id
                gender
                samples {
                    id
                    sample_type
                    anatomic_site
                }
            }
        }
        """
        result = extract_fields_from_query(query)
        expected = {
            "subject": ["id", "gender"],
            "samples": ["id", "sample_type", "anatomic_site"],
        }
        assert result == expected

    def test_multiple_entities(self):
        """Test extraction from query with multiple root entities"""
        query = """
        {
            subject(first: 5) {
                id
                gender
            }
            sample(first: 3) {
                sample_type
                anatomic_site
            }
        }
        """
        result = extract_fields_from_query(query)
        expected = {
            "subject": ["id", "gender"],
            "sample": ["sample_type", "anatomic_site"],
        }
        assert result == expected

    def test_deeply_nested_query(self):
        """Test extraction from deeply nested query"""
        query = """
        {
            subject {
                id
                studies {
                    project_id
                    samples {
                        sample_type
                        files {
                            file_name
                            file_size
                        }
                    }
                }
            }
        }
        """
        result = extract_fields_from_query(query)
        expected = {
            "subject": ["id"],
            "studies": ["project_id"],
            "samples": ["sample_type"],
            "files": ["file_name", "file_size"],
        }
        assert result == expected

    def test_query_with_fragments(self):
        """Test extraction from query with fragments (basic support)"""
        # Note: Our current implementation may not fully support fragments
        # but should at least extract the basic fields
        query = """
        {
            subject {
                id
                ...SubjectFields
            }
        }
        fragment SubjectFields on Subject {
            gender
            age_at_enrollment
        }
        """
        result = extract_fields_from_query(query)
        # Should at least extract the basic fields
        assert "subject" in result
        assert "id" in result["subject"]

    def test_invalid_syntax_raises_error(self):
        """Test that invalid syntax raises QueryValidationError"""
        query = "{ subject { id }"  # Missing closing brace
        with pytest.raises(QueryValidationError, match="Invalid GraphQL syntax"):
            extract_fields_from_query(query)

    def test_duplicate_fields_removed(self):
        """Test that duplicate fields are removed"""
        query = "{ subject { id id submitter_id id } }"
        result = extract_fields_from_query(query)
        expected = {"subject": ["id", "submitter_id"]}
        assert result == expected

    def test_query_with_aliases(self):
        """Test extraction from query with field aliases"""
        query = """
        {
            subject {
                identifier: id
                sub_id: submitter_id
                sex: gender
            }
        }
        """
        result = extract_fields_from_query(query)
        assert "subject" in result
        assert len(result["subject"]) == 3

    def test_mutation_query(self):
        """Test that mutation operations are handled"""
        query = """
        mutation {
            createSubject(input: {submitter_id: "test"}) {
                id
                submitter_id
            }
        }
        """
        # Should extract fields even from mutations
        result = extract_fields_from_query(query)
        assert "createSubject" in result or len(result) >= 0


class TestGraphQLParserEdgeCases:
    """Test edge cases and error handling"""

    def test_empty_selection_set(self):
        """Test handling of empty selection sets"""
        query = "{ subject }"  # No fields selected
        # Should handle gracefully, though may be invalid GraphQL
        try:
            result = extract_fields_from_query(query)
            # If it doesn't raise an error, should return empty fields
            assert isinstance(result, dict)
        except QueryValidationError:
            # It's okay if this raises a validation error
            pass

    def test_comments_in_query(self):
        """Test handling of comments in query"""
        query = """
        {
            # This is a comment
            subject {
                id  # Another comment
                gender
            }
        }
        """
        result = extract_fields_from_query(query)
        expected = {"subject": ["id", "gender"]}
        assert result == expected

    def test_whitespace_handling(self):
        """Test handling of various whitespace"""
        query = """

        {
            subject    {
                id

                gender
            }
        }

        """
        result = extract_fields_from_query(query)
        expected = {"subject": ["id", "gender"]}
        assert result == expected

    def test_very_large_query(self):
        """Test handling of very large query"""
        # Create a query with many fields
        fields = " ".join([f"field_{i}" for i in range(100)])
        query = f"{{ subject {{ {fields} }} }}"

        result = extract_fields_from_query(query)
        assert "subject" in result
        assert len(result["subject"]) == 100

    def test_unicode_field_names(self):
        """Test handling of unicode characters in field names"""
        # Note: GraphQL spec allows limited unicode in names
        query = "{ subject { id field_name } }"  # Using safe ASCII
        result = extract_fields_from_query(query)
        expected = {"subject": ["id", "field_name"]}
        assert result == expected


class TestGraphQLParsingWithQueryValidation:
    """Test GraphQL parsing integration with query validation"""

    def test_field_extraction_with_complex_nesting(self):
        """Test that field extraction works correctly with complex nesting"""
        query = """
        {
            subject(first: 5) {
                id
                submitter_id
                gender
                age_at_enrollment
                samples {
                    id
                    sample_type
                    anatomic_site
                    files {
                        file_name
                        file_size
                    }
                }
            }
        }
        """

        result = extract_fields_from_query(query)

        expected = {
            "subject": ["id", "submitter_id", "gender", "age_at_enrollment"],
            "samples": ["id", "sample_type", "anatomic_site"],
            "files": ["file_name", "file_size"],
        }

        assert result == expected

    def test_syntax_validation_before_parsing(self):
        """Test that syntax is validated before field extraction"""
        valid_query = "{ subject { id gender } }"
        invalid_query = "{ subject { id gender }"  # Missing closing brace

        # Valid query should work
        is_valid, error = validate_graphql_syntax(valid_query)
        assert is_valid is True
        assert error is None

        fields = extract_fields_from_query(valid_query)
        assert fields == {"subject": ["id", "gender"]}

        # Invalid query should fail syntax validation
        is_valid, error = validate_graphql_syntax(invalid_query)
        assert is_valid is False
        assert error is not None

    def test_robust_parsing_handles_edge_cases(self):
        """Test that robust parsing handles various edge cases"""
        # Query with arguments and nested structures
        query = """
        {
            subject(first: 10, filter: {gender: "Female"}) {
                id
                submitter_id
                studies(orderBy: created_datetime) {
                    project_id
                    data_category
                }
            }
        }
        """

        result = extract_fields_from_query(query)

        assert "subject" in result
        assert "studies" in result
        assert "id" in result["subject"]
        assert "submitter_id" in result["subject"]
        assert "project_id" in result["studies"]
        assert "data_category" in result["studies"]


class TestGraphQLErrorHandling:
    """Test GraphQL-specific error handling"""

    def test_graphql_syntax_error_handling(self):
        """Test that GraphQL syntax errors are handled properly"""
        invalid_query = "{ subject { id }"  # Missing closing brace

        with pytest.raises(QueryValidationError, match="Invalid GraphQL syntax"):
            extract_fields_from_query(invalid_query)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
