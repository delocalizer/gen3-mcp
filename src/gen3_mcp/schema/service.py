"""Schema service with intelligent caching"""

import logging
from typing import Dict, List, Any, Optional
import time
from ..client.gen3_client import Gen3ClientProtocol
from ..config.settings import Gen3Config
from ..exceptions import EntityNotFoundError, SchemaFetchError

logger = logging.getLogger("gen3-mcp.schema")


class SchemaService:
    """Unified schema operations using config endpoints consistently"""

    def __init__(self, client: Gen3ClientProtocol, config: Gen3Config):
        self.client = client
        self.config = config  # Use config for all endpoint URLs
        self._cache = {}
        self._cache_timestamps = {}
        self.cache_ttl = config.schema_cache_ttl
        self.max_cache_size = config.max_cache_size

    async def get_full_schema(self) -> Dict[str, Any]:
        """Get full schema using config.schema_url"""
        cache_key = "full_schema"

        if self._is_cache_valid(cache_key):
            logger.debug("Using cached full schema")
            return self._cache[cache_key]

        logger.info("Fetching full schema from Gen3")
        # Use the pre-computed URL from config
        schema = await self.client.get_json(self.config.schema_url, authenticated=False)

        if schema is None:
            raise SchemaFetchError("Failed to fetch schema from Gen3")

        logger.info(f"Fetched schema with {len(schema)} entities")
        self._update_cache(cache_key, schema)
        return schema

    async def get_entity_schema(self, entity_name: str) -> Dict[str, Any]:
        """Get single entity schema using config.entity_schema_url()"""
        cache_key = f"entity_schema:{entity_name}"

        if self._is_cache_valid(cache_key):
            logger.debug(f"Using cached schema for entity '{entity_name}'")
            return self._cache[cache_key]

        logger.debug(f"Fetching schema for entity '{entity_name}'")
        # Use the config method to build entity-specific URL
        entity_url = self.config.entity_schema_url(entity_name)
        schema = await self.client.get_json(entity_url, authenticated=False)

        if schema is None:
            raise EntityNotFoundError(f"Entity '{entity_name}' not found")

        self._update_cache(cache_key, schema)
        return schema

    async def get_entity_names(self) -> List[str]:
        """Get list of all entity names"""
        full_schema = await self.get_full_schema()
        return list(full_schema.keys())

    async def entity_exists(self, entity_name: str) -> bool:
        """Check if entity exists (uses cache when possible)"""
        try:
            # Try to get from full schema cache first (more efficient)
            if self._is_cache_valid("full_schema"):
                full_schema = self._cache["full_schema"]
                return entity_name in full_schema

            # Fall back to individual entity fetch
            await self.get_entity_schema(entity_name)
            return True
        except EntityNotFoundError:
            return False

    async def get_schema_summary(self) -> Dict[str, Any]:
        """Generate schema summary from cached data"""
        entities = await self.get_entity_names()
        full_schema = await self.get_full_schema()

        # Group by category
        by_category = {}
        total_relationships = 0

        for name, schema in full_schema.items():
            category = schema.get("category", "uncategorized")
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(name)

            # Count relationships
            links = schema.get("links", [])
            for link in links:
                if isinstance(link, dict):
                    if "subgroup" in link:
                        total_relationships += len(link.get("subgroup", []))
                    else:
                        total_relationships += 1

        return {
            "endpoint": self.config.base_url,
            "total_entities": len(entities),
            "entity_names": entities,
            "entities_by_category": by_category,
            "total_relationships": total_relationships,
            "schema_url": self.config.schema_url,
        }

    def _is_cache_valid(self, key: str) -> bool:
        """Check if cache entry is still valid"""
        if key not in self._cache:
            return False

        age = time.time() - self._cache_timestamps.get(key, 0)
        return age < self.cache_ttl

    def _update_cache(self, key: str, value: Any):
        """Update cache with new value and timestamp"""
        # Implement basic LRU eviction if cache is full
        if len(self._cache) >= self.max_cache_size:
            self._evict_oldest_entry()

        self._cache[key] = value
        self._cache_timestamps[key] = time.time()
        logger.debug(f"Cached {key} (cache size: {len(self._cache)})")

    def _evict_oldest_entry(self):
        """Evict the oldest cache entry"""
        if not self._cache_timestamps:
            return

        oldest_key = min(
            self._cache_timestamps.keys(), key=lambda k: self._cache_timestamps[k]
        )

        del self._cache[oldest_key]
        del self._cache_timestamps[oldest_key]
        logger.debug(f"Evicted cache entry: {oldest_key}")

    def clear_cache(self):
        """Clear all cached data"""
        self._cache.clear()
        self._cache_timestamps.clear()
        logger.info("Schema cache cleared")
