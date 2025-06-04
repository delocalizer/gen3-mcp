"""Service providing Gen3 schema operations and caching."""

import logging
import time
from typing import Any

from .client import Gen3Client
from .config import Config
from .exceptions import Gen3SchemaError

logger = logging.getLogger("gen3-mcp.schema")


class SchemaService:
    """Service for cached schema operations and data access.

    Requires a client and a config instance.
    """

    def __init__(self, client: Gen3Client, config: Config):
        """Initialize SchemaService.

        Args:
            client: Gen3Client instance for API calls.
            config: Config instance with settings.
        """
        self.client = client
        self.config = config
        self._cache = {}
        self._cache_timestamps = {}
        self.cache_ttl = config.schema_cache_ttl

    async def get_schema_full(self) -> dict[str, Any]:
        """Get full schema using config.schema_url.

        Returns:
            Full schema dict with entity definitions. Top level keys may include
            common elements identified with a leading underscore (_definitions,
            _settings, _terms) as well as individual entity schemas.

        Raises:
            Gen3SchemaError: If schema fetch fails.
        """
        cache_key = "full_schema"

        if self._is_cache_valid(cache_key):
            logger.debug("Using cached full schema")
            return self._cache[cache_key]

        logger.info("Fetching full schema from Gen3")
        schema = await self.client.get_json(self.config.schema_url, authenticated=False)

        if schema is None:
            logger.error("Failed to fetch schema from Gen3")
            raise Gen3SchemaError("Failed to fetch schema from Gen3")

        logger.info(f"Fetched schema with {len(schema)} entities")
        self._update_cache(cache_key, schema)
        return schema

    def _is_cache_valid(self, key: str) -> bool:
        """Check if cache entry is still valid.

        Args:
            key: Cache key to check.

        Returns:
            True if cache is valid, False otherwise.
        """
        if key not in self._cache:
            return False

        age = time.time() - self._cache_timestamps.get(key, 0)
        return age < self.cache_ttl

    def _update_cache(self, key: str, value: Any) -> None:
        """Update cache with new value and timestamp.

        Args:
            key: Cache key.
            value: Value to cache.
        """
        self._cache[key] = value
        self._cache_timestamps[key] = time.time()
        logger.debug(f"Cached {key}")
