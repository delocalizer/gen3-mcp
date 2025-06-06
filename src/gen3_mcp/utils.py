"""Utility functions for string similarity and suggestions."""

from typing import Any


def suggest_similar_strings(
    target: str,
    candidates: set[str] | list[str],
    threshold: float = 0.6,
    max_results: int = 3,
) -> list[str]:
    """Suggest similar strings using basic similarity scoring.

    Args:
        target: String to match against.
        candidates: Set or list of candidate strings.
        threshold: Minimum similarity threshold (0.0 to 1.0).
        max_results: Maximum number of suggestions to return.

    Returns:
        List of similar strings, sorted by similarity (highest first).
    """
    from difflib import SequenceMatcher

    suggestions = []
    for candidate in candidates:
        similarity = SequenceMatcher(None, target.lower(), candidate.lower()).ratio()
        if similarity >= threshold:
            suggestions.append((candidate, similarity))

    # Sort by similarity (descending) and return just the strings
    suggestions.sort(key=lambda x: x[1], reverse=True)
    return [s[0] for s in suggestions[:max_results]]


def suggest_similar_strings_with_scores(
    target: str,
    candidates: set[str] | list[str],
    threshold: float = 0.5,
    max_results: int = 10,
) -> list[dict[str, Any]]:
    """Suggest similar strings with similarity scores.

    Args:
        target: String to match against.
        candidates: Set or list of candidate strings.
        threshold: Minimum similarity threshold (0.0 to 1.0).
        max_results: Maximum number of suggestions to return.

    Returns:
        List of dicts with 'name' and 'similarity' keys, sorted by similarity (highest first).
    """
    from difflib import SequenceMatcher

    suggestions = []
    for candidate in candidates:
        similarity = SequenceMatcher(None, target.lower(), candidate.lower()).ratio()
        if similarity >= threshold:
            suggestions.append({"name": candidate, "similarity": similarity})

    # Sort by similarity (descending)
    suggestions.sort(key=lambda x: x["similarity"], reverse=True)
    return suggestions[:max_results]
