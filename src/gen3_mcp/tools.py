"""MCP tools"""

import logging
from typing import Dict, Any
from .service import Gen3Service
from .query import QueryService
from .client import Gen3Client
from .config import Gen3Config

logger = logging.getLogger("gen3-mcp.tools")


class Tools:
    """MCP tools with shared services"""

    def __init__(self, client: Gen3Client, config: Gen3Config):
        self.config = config
        self.gen3_service = Gen3Service(client, config)
        self.query_service = QueryService(client, config, self.gen3_service)
        logger.info("tools initialized")

    # Schema Operations
    async def schema_summary(self) -> Dict[str, Any]:
        """Get schema summary"""
        return await self.gen3_service.get_schema_summary()

    async def schema_full(self) -> Dict[str, Any]:
        """Get full schema"""
        return await self.gen3_service.get_full_schema()

    async def schema_entity(self, entity_name: str) -> Dict[str, Any]:
        """Get schema for specific entity"""
        return await self.gen3_service.get_entity_schema(entity_name)

    async def schema_entities(self) -> Dict[str, Any]:
        """Get list of all entities"""
        entities = await self.gen3_service.get_entity_names()
        return {"entities": entities}

    async def schema_list_available_entities(self) -> Dict[str, Any]:
        """Get detailed entity list with relationships"""
        return await self.gen3_service.get_detailed_entities()

    # Data Operations
    async def data_explore(self, entity_name: str, **kwargs) -> Dict[str, Any]:
        """Explore entity using intelligent field selection"""
        field_count = kwargs.get("field_count", 15)
        record_limit = kwargs.get("limit", 5)

        # Get sample records with optimal fields
        result = await self.gen3_service.get_sample_records(entity_name, record_limit)
        result["entity"] = entity_name
        return result

    async def data_sample_records(self, entity_name: str, **kwargs) -> Dict[str, Any]:
        """Get sample records for entity"""
        limit = kwargs.get("limit", 5)
        return await self.gen3_service.get_sample_records(entity_name, limit)

    async def data_field_values(
        self, entity_name: str, field_name: str, **kwargs
    ) -> Dict[str, Any]:
        """Get field values using query service"""
        limit = kwargs.get("limit", 20)
        return await self.query_service.execute_field_sampling(
            entity_name, field_name, limit
        )

    async def data_explore_entity_data(self, entity_name: str) -> Dict[str, Any]:
        """Comprehensive entity exploration"""
        return await self.gen3_service.explore_entity_data(entity_name)

    # Query Operations
    async def query_graphql(self, query: str) -> Dict[str, Any]:
        """Execute GraphQL query"""
        result = await self.query_service.execute_graphql(query)
        if result is None:
            return {"error": "Query execution failed"}
        return result

    # Validation Operations
    async def validation_validate_query_fields(self, query: str) -> Dict[str, Any]:
        """Validate query fields"""
        return await self.query_service.validate_query_fields(query)

    async def validation_suggest_similar_fields(
        self, field_name: str, entity_name: str
    ) -> Dict[str, Any]:
        """Suggest similar fields"""
        return await self.query_service.suggest_similar_fields(field_name, entity_name)

    async def validation_get_query_template(
        self, entity_name: str, **kwargs
    ) -> Dict[str, Any]:
        """Generate query template"""
        include_relationships = kwargs.get("include_relationships", True)
        max_fields = kwargs.get("max_fields", 20)
        return await self.query_service.generate_query_template(
            entity_name, include_relationships, max_fields
        )
