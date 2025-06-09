"""Tests for utility functions."""

import pytest

from gen3_mcp.utils import suggest_similar_strings


class TestSuggestSimilarStrings:
    """Test suggest_similar_strings function."""

    def test_exact_match(self):
        """Test exact match returns highest similarity."""
        candidates = ["subject", "study", "sample", "aliquot"]
        suggestions = suggest_similar_strings("subject", candidates)

        assert "subject" in suggestions
        assert suggestions[0] == "subject"

    def test_typo_correction(self):
        """Test typo correction finds close matches."""
        candidates = ["subject", "study", "sample", "aliquot"]
        suggestions = suggest_similar_strings("subjct", candidates)

        assert "subject" in suggestions

    def test_case_insensitive(self):
        """Test matching is case insensitive."""
        candidates = ["Subject", "Study", "Sample", "Aliquot"]
        suggestions = suggest_similar_strings("subject", candidates)

        assert "Subject" in suggestions

    def test_threshold_filtering(self):
        """Test threshold filters out poor matches."""
        candidates = ["apple", "banana", "cherry"]
        suggestions = suggest_similar_strings("xyz", candidates, threshold=0.8)

        # No matches should meet high threshold
        assert len(suggestions) == 0

    def test_max_results_limit(self):
        """Test max_results limits number of suggestions."""
        candidates = ["abc", "abd", "abe", "abf", "abg"]
        suggestions = suggest_similar_strings("ab", candidates, max_results=2)

        assert len(suggestions) <= 2

    def test_empty_candidates(self):
        """Test behavior with empty candidates."""
        suggestions = suggest_similar_strings("test", [])
        assert len(suggestions) == 0

    def test_sorted_by_similarity(self):
        """Test results are sorted by similarity."""
        candidates = ["test", "testing", "tester", "xyz"]
        suggestions = suggest_similar_strings("test", candidates, threshold=0.1)

        # "test" should be first (exact match), then similar ones
        assert suggestions[0] == "test"


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_target_string(self):
        """Test behavior with empty target string."""
        candidates = ["test", "example"]
        suggestions = suggest_similar_strings("", candidates, threshold=0.1)

        # Should handle gracefully
        assert isinstance(suggestions, list)

    def test_very_long_strings(self):
        """Test with very long strings."""
        long_string = "a" * 1000
        candidates = [long_string, "test"]
        suggestions = suggest_similar_strings(long_string, candidates)

        assert long_string in suggestions

    def test_special_characters(self):
        """Test with special characters."""
        candidates = ["test_field", "test-field", "test.field"]
        suggestions = suggest_similar_strings("test_field", candidates)

        assert "test_field" in suggestions

    def test_unicode_strings(self):
        """Test with unicode strings."""
        candidates = ["café", "naïve", "résumé"]
        suggestions = suggest_similar_strings("cafe", candidates)

        # Should handle unicode gracefully
        assert isinstance(suggestions, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
