"""Logging configuration"""

import logging


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Configure logging for the entire application"""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        force=True,  # Override any existing configuration
    )
    return logging.getLogger("gen3-mcp")
