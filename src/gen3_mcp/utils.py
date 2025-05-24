"""Utility functions for the Gen3 MCP server"""

import logging
from typing import Any

logger = logging.getLogger("gen3-mcp.utils")


def parse_kwargs_string(kwargs_str: str) -> dict[str, Any]:
    """
    Parse a kwargs string into a dictionary with proper type conversion.

    Note: MCP tools can only accept primitive parameter types (str, int, float, bool),
    not complex types like dict. Therefore, we use a string parameter and parse it
    manually to work around this MCP limitation.

    Args:
        kwargs_str: String in format "key1=value1,key2=value2"

    Returns:
        Dictionary with parsed key-value pairs and appropriate type conversion

    Raises:
        ValueError: If the kwargs string format is invalid

    Examples:
        >>> parse_kwargs_string("limit=5,include_nulls=true")
        {'limit': 5, 'include_nulls': True}

        >>> parse_kwargs_string("name=test,score=3.14,enabled=false")
        {'name': 'test', 'score': 3.14, 'enabled': False}
    """
    if not kwargs_str or not kwargs_str.strip():
        return {}

    parsed_kwargs = {}

    try:
        # Split by comma, but handle escaped commas
        pairs = _split_preserving_escapes(kwargs_str, ",")

        for pair in pairs:
            pair = pair.strip()
            if not pair:
                continue

            if "=" not in pair:
                raise ValueError(f"Invalid key-value pair (missing '='): '{pair}'")

            # Split only on the first '=' to handle values containing '='
            key, value = pair.split("=", 1)
            key = key.strip()
            value = value.strip()

            if not key:
                raise ValueError(f"Empty key in pair: '{pair}'")

            # Parse the value with type conversion
            parsed_value = _parse_value(value)
            parsed_kwargs[key] = parsed_value

        logger.debug(f"Parsed kwargs: {parsed_kwargs}")
        return parsed_kwargs

    except Exception as e:
        logger.error(f"Failed to parse kwargs string '{kwargs_str}': {e}")
        raise ValueError(f"Invalid kwargs format: {e}") from e


def _parse_value(value_str: str) -> Any:
    """
    Parse a string value to the appropriate Python type.

    Supports: bool, int, float, null/None, and string
    """
    value = value_str.strip()

    # Handle empty values
    if not value:
        return ""

    # Handle quoted strings (remove quotes but preserve the string type)
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]  # Remove quotes

    # Handle boolean values
    if value.lower() in ("true", "yes", "on", "1"):
        return True
    if value.lower() in ("false", "no", "off", "0"):
        return False

    # Handle null/none values
    if value.lower() in ("null", "none", "nil"):
        return None

    # Try numeric conversion
    try:
        # Check for float first (has decimal point)
        if "." in value or "e" in value.lower():
            return float(value)
        # Integer conversion
        return int(value)
    except ValueError:
        pass

    # Default to string
    return value


def _split_preserving_escapes(text: str, delimiter: str) -> list[str]:
    """
    Split text by delimiter while preserving escaped delimiters.

    For now, this is a simple implementation. Could be enhanced later
    to handle proper escaping if needed.
    """
    # Simple split for now - can be enhanced if escaping is needed
    return text.split(delimiter)


def validate_kwargs_for_operation(
    operation: str, parsed_kwargs: dict[str, Any], required_params: list[str] = None
) -> None:
    """
    Validate that required parameters are present for an operation.

    Args:
        operation: Name of the operation
        parsed_kwargs: Parsed kwargs dictionary
        required_params: List of required parameter names

    Raises:
        ValueError: If required parameters are missing
    """
    if not required_params:
        return

    missing_params = [param for param in required_params if param not in parsed_kwargs]

    if missing_params:
        raise ValueError(
            f"Operation '{operation}' requires parameters: {', '.join(missing_params)}. "
            f"Missing: {', '.join(missing_params)}"
        )
