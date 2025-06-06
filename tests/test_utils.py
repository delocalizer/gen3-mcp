"""Tests for utility functions."""

import pytest

from gen3_mcp.utils import suggest_similar_strings, suggest_similar_strings_with_scores


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


class TestSuggestSimilarStringsWithScores:
    """Test suggest_similar_strings_with_scores function."""

    def test_exact_match_score(self):
        """Test exact match returns score of 1.0."""
        candidates = ["subject", "study", "sample"]
        suggestions = suggest_similar_strings_with_scores("subject", candidates)

        exact_match = [s for s in suggestions if s["name"] == "subject"][0]
        assert exact_match["similarity"] == 1.0

    def test_return_format(self):
        """Test function returns proper dict format."""
        candidates = ["subject", "study"]
        suggestions = suggest_similar_strings_with_scores("subject", candidates)

        assert isinstance(suggestions, list)
        for suggestion in suggestions:
            assert isinstance(suggestion, dict)
            assert "name" in suggestion
            assert "similarity" in suggestion
            assert isinstance(suggestion["similarity"], float)

    def test_sorted_by_similarity_desc(self):
        """Test results are sorted by similarity descending."""
        candidates = ["abc", "ab", "a", "xyz"]
        suggestions = suggest_similar_strings_with_scores(
            "abc", candidates, threshold=0.1
        )

        similarities = [s["similarity"] for s in suggestions]
        assert similarities == sorted(similarities, reverse=True)

    def test_threshold_filtering_with_scores(self):
        """Test threshold filtering with score format."""
        candidates = ["apple", "banana", "cherry"]
        suggestions = suggest_similar_strings_with_scores(
            "xyz", candidates, threshold=0.8
        )

        assert len(suggestions) == 0

    def test_max_results_with_scores(self):
        """Test max_results with score format."""
        candidates = ["test1", "test2", "test3", "test4"]
        suggestions = suggest_similar_strings_with_scores(
            "test", candidates, max_results=2
        )

        assert len(suggestions) <= 2


class TestUtilityComparison:
    """Test consistency between utility functions."""

    def test_same_ordering(self):
        """Test both functions return same ordering."""
        candidates = ["subject", "study", "sample", "aliquot"]

        simple_suggestions = suggest_similar_strings("subjct", candidates)
        scored_suggestions = suggest_similar_strings_with_scores("subjct", candidates)

        # Extract names from scored suggestions
        scored_names = [s["name"] for s in scored_suggestions]

        # Should have same ordering
        assert simple_suggestions == scored_names

    def test_same_threshold_behavior(self):
        """Test both functions respect threshold the same way."""
        candidates = ["apple", "banana", "cherry"]
        threshold = 0.8

        simple_suggestions = suggest_similar_strings(
            "xyz", candidates, threshold=threshold
        )
        scored_suggestions = suggest_similar_strings_with_scores(
            "xyz", candidates, threshold=threshold
        )

        # Both should be empty due to high threshold
        assert len(simple_suggestions) == 0
        assert len(scored_suggestions) == 0


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
