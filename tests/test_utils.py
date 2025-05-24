"""Tests for parameter parsing utilities"""

import pytest

from gen3_mcp.utils import parse_kwargs_string, validate_kwargs_for_operation


class TestParseKwargsString:
    """Test the kwargs string parsing functionality"""

    def test_empty_string(self):
        """Test parsing empty string"""
        result = parse_kwargs_string("")
        assert result == {}

    def test_none_string(self):
        """Test parsing None/whitespace"""
        result = parse_kwargs_string("   ")
        assert result == {}

    def test_simple_string_values(self):
        """Test parsing simple string values"""
        result = parse_kwargs_string("name=test,description=hello world")
        assert result == {"name": "test", "description": "hello world"}

    def test_integer_values(self):
        """Test parsing integer values"""
        result = parse_kwargs_string("limit=5,offset=10,count=0")
        assert result == {"limit": 5, "offset": 10, "count": 0}

    def test_float_values(self):
        """Test parsing float values"""
        result = parse_kwargs_string("score=3.14,ratio=0.5,threshold=1.0")
        assert result == {"score": 3.14, "ratio": 0.5, "threshold": 1.0}

    def test_boolean_values(self):
        """Test parsing boolean values"""
        result = parse_kwargs_string("enabled=true,active=false,debug=yes,verbose=no")
        assert result == {
            "enabled": True,
            "active": False,
            "debug": True,
            "verbose": False,
        }

    def test_null_values(self):
        """Test parsing null/none values"""
        result = parse_kwargs_string("value=null,data=none,result=nil")
        assert result == {"value": None, "data": None, "result": None}

    def test_quoted_strings(self):
        """Test parsing quoted string values"""
        result = parse_kwargs_string("name=\"John Doe\",description='hello world'")
        assert result == {"name": "John Doe", "description": "hello world"}

    def test_mixed_types(self):
        """Test parsing mixed value types"""
        result = parse_kwargs_string(
            "name=test,limit=5,enabled=true,score=3.14,data=null"
        )
        expected = {
            "name": "test",
            "limit": 5,
            "enabled": True,
            "score": 3.14,
            "data": None,
        }
        assert result == expected

    def test_values_with_equals(self):
        """Test parsing values containing equals signs"""
        result = parse_kwargs_string("query=id=123,expression=x=y+1")
        assert result == {"query": "id=123", "expression": "x=y+1"}

    def test_whitespace_handling(self):
        """Test handling of whitespace around keys and values"""
        result = parse_kwargs_string("  name = test  ,  limit = 5  ")
        assert result == {"name": "test", "limit": 5}

    def test_complex_graphql_query(self):
        """Test parsing a complex GraphQL query as a parameter"""
        query = "{ subject { id gender age_at_enrollment } }"
        result = parse_kwargs_string(f"query={query},limit=10")
        assert result == {"query": query, "limit": 10}

    def test_invalid_format_no_equals(self):
        """Test error handling for invalid format without equals"""
        with pytest.raises(ValueError, match="Invalid key-value pair"):
            parse_kwargs_string("invalid_pair")

    def test_invalid_format_empty_key(self):
        """Test error handling for empty key"""
        with pytest.raises(ValueError, match="Empty key"):
            parse_kwargs_string("=value")

    def test_scientific_notation(self):
        """Test parsing scientific notation numbers"""
        result = parse_kwargs_string("value=1e10,small=1.5e-3")
        assert result == {"value": 1e10, "small": 1.5e-3}

    def test_special_boolean_values(self):
        """Test various boolean representations"""
        result = parse_kwargs_string("a=1,b=0,c=on,d=off,e=TRUE,f=FALSE")
        assert result == {
            "a": True,
            "b": False,
            "c": True,
            "d": False,
            "e": True,
            "f": False,
        }


class TestValidateKwargsForOperation:
    """Test the kwargs validation functionality"""

    def test_no_required_params(self):
        """Test validation with no required parameters"""
        # Should not raise any exception
        validate_kwargs_for_operation("test_op", {"key": "value"}, [])
        validate_kwargs_for_operation("test_op", {"key": "value"}, None)

    def test_all_required_present(self):
        """Test validation when all required parameters are present"""
        kwargs = {"field_name": "test", "entity_name": "subject", "extra": "value"}
        required = ["field_name", "entity_name"]

        # Should not raise any exception
        validate_kwargs_for_operation("suggest_fields", kwargs, required)

    def test_missing_required_params(self):
        """Test validation when required parameters are missing"""
        kwargs = {"field_name": "test"}
        required = ["field_name", "entity_name"]

        with pytest.raises(
            ValueError, match="Operation 'suggest_fields' requires parameters"
        ):
            validate_kwargs_for_operation("suggest_fields", kwargs, required)

    def test_multiple_missing_params(self):
        """Test validation with multiple missing parameters"""
        kwargs = {}
        required = ["field_name", "entity_name", "query"]

        with pytest.raises(ValueError, match="Missing: field_name, entity_name, query"):
            validate_kwargs_for_operation("test_op", kwargs, required)

    def test_empty_kwargs_with_required(self):
        """Test validation with empty kwargs but required parameters"""
        with pytest.raises(ValueError, match="requires parameters"):
            validate_kwargs_for_operation("validate_query", {}, ["query"])


class TestIntegrationParsingAndValidation:
    """Integration tests combining parsing and validation"""

    def test_field_values_operation_params(self):
        """Test parsing and validation for field_values operation"""
        kwargs_str = "field_name=gender,entity_name=subject,limit=100"
        parsed = parse_kwargs_string(kwargs_str)

        # Should not raise exception
        validate_kwargs_for_operation("field_values", parsed, ["field_name"])

        assert parsed["field_name"] == "gender"
        assert parsed["entity_name"] == "subject"
        assert parsed["limit"] == 100

    def test_validate_query_operation_params(self):
        """Test parsing and validation for validate_query operation"""
        query = "{ subject { id gender invalid_field } }"
        kwargs_str = f"query={query}"
        parsed = parse_kwargs_string(kwargs_str)

        # Should not raise exception
        validate_kwargs_for_operation("validate_query", parsed, ["query"])

        assert parsed["query"] == query

    def test_suggest_fields_operation_params(self):
        """Test parsing and validation for suggest_fields operation"""
        kwargs_str = "field_name=gander,entity_name=subject"
        parsed = parse_kwargs_string(kwargs_str)

        # Should not raise exception
        validate_kwargs_for_operation(
            "suggest_fields", parsed, ["field_name", "entity_name"]
        )

        assert parsed["field_name"] == "gander"
        assert parsed["entity_name"] == "subject"

    def test_query_template_operation_params(self):
        """Test parsing and validation for query_template operation"""
        kwargs_str = "entity_name=subject,include_relationships=true,max_fields=15"
        parsed = parse_kwargs_string(kwargs_str)

        # Should not raise exception
        validate_kwargs_for_operation("query_template", parsed, ["entity_name"])

        assert parsed["entity_name"] == "subject"
        assert parsed["include_relationships"] is True
        assert parsed["max_fields"] == 15

    def test_missing_required_in_realistic_scenario(self):
        """Test missing required parameter in realistic scenario"""
        kwargs_str = "entity_name=subject,limit=10"  # Missing field_name
        parsed = parse_kwargs_string(kwargs_str)

        with pytest.raises(ValueError, match="field_name"):
            validate_kwargs_for_operation("field_values", parsed, ["field_name"])


class TestParameterParsingWithMCPTools:
    """Test parameter parsing with MCP tools"""

    def test_data_operations_parameter_parsing(self):
        """Test that data operations can parse parameters correctly"""
        # Simulate what happens in the MCP tool
        kwargs_str = "limit=5,field_count=10,include_nulls=true"
        parsed = parse_kwargs_string(kwargs_str)

        assert parsed == {"limit": 5, "field_count": 10, "include_nulls": True}

    def test_validation_operations_parameter_parsing(self):
        """Test that validation operations can parse parameters correctly"""
        query = "{ subject { id gender age_at_enrollment } }"
        kwargs_str = f"query={query},entity_name=subject"
        parsed = parse_kwargs_string(kwargs_str)

        assert parsed["query"] == query
        assert parsed["entity_name"] == "subject"

    def test_complex_graphql_query_as_parameter(self):
        """Test parsing complex GraphQL query as parameter"""
        query = """
        {
            subject(first: 10) {
                id
                submitter_id
                gender
                samples {
                    id
                    sample_type
                    anatomic_site
                }
            }
        }
        """
        kwargs_str = f"query={query.strip()},limit=10"
        parsed = parse_kwargs_string(kwargs_str)

        assert "query" in parsed
        assert "limit" in parsed
        assert parsed["limit"] == 10


class TestErrorHandlingInUtils:
    """Test error handling in utils functions"""

    def test_parameter_validation_errors(self):
        """Test that parameter validation gives helpful errors"""
        with pytest.raises(
            ValueError, match="Operation 'field_values' requires parameters: field_name"
        ):
            validate_kwargs_for_operation("field_values", {}, ["field_name"])

    def test_parameter_parsing_error_handling(self):
        """Test that parameter parsing errors are handled properly"""
        # Invalid format should raise ValueError
        with pytest.raises(ValueError, match="Invalid kwargs format"):
            parse_kwargs_string("invalid_format_no_equals")

    def test_empty_key_error_handling(self):
        """Test that empty key errors are handled properly"""
        with pytest.raises(ValueError, match="Empty key"):
            parse_kwargs_string("=value")


class TestBackwardCompatibilityInUtils:
    """Test that utils functions maintain backward compatibility"""

    def test_empty_kwargs_still_handled(self):
        """Test that empty kwargs are still handled correctly"""
        result = parse_kwargs_string("")
        assert result == {}

        result = parse_kwargs_string("   ")
        assert result == {}

    def test_simple_parameters_still_work(self):
        """Test that simple parameter formats still work"""
        result = parse_kwargs_string("limit=5")
        assert result == {"limit": 5}

    def test_validation_with_no_requirements_still_works(self):
        """Test that validation with no requirements still works"""
        # Should not raise any exception
        validate_kwargs_for_operation("test_op", {"key": "value"}, [])
        validate_kwargs_for_operation("test_op", {"key": "value"}, None)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
