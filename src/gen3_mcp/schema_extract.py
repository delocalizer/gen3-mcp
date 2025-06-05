"""
DEPRECATED: This module has been moved into SchemaManager.

This file provides backward compatibility for existing tests and imports.
All functionality has been moved to schema.SchemaManager.
"""

import warnings
from typing import Any

from .models import SchemaExtract


def get_schema_extract(full_schema: dict[str, Any]) -> SchemaExtract:
    """
    DEPRECATED: Use SchemaManager.get_schema_extract() instead.

    This function is kept for backward compatibility with existing tests.
    """
    warnings.warn(
        "get_schema_extract() is deprecated. Use SchemaManager.get_schema_extract() instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    # Import here to avoid circular imports
    from .schema import SchemaManager

    # Create a temporary manager instance for compatibility
    # Note: This won't have proper client/config, but works for testing
    class _CompatManager(SchemaManager):
        def __init__(self):
            # Skip parent __init__ to avoid requiring client
            self._cache = {}
            self.config = None  # Not needed for pure processing

    service = _CompatManager()
    return service._create_extract(full_schema)


def clear_schema_cache():
    """
    DEPRECATED: This is kept for backward compatibility with tests.

    Since schema extract functionality moved to SchemaManager,
    this function does nothing.
    """
    warnings.warn(
        "clear_schema_cache() is deprecated. Use SchemaManager.clear_cache() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    pass
