"""GraphQL query execution service"""

import logging
from typing import Dict, Any, Optional
from ..client.gen3_client import Gen3ClientProtocol
from ..config.settings import Gen3Config

logger = logging.getLogger("gen3-mcp.query")


class QueryExecutor:
    """Handles GraphQL query execution using config endpoints"""

    def __init__(self, client: Gen3ClientProtocol, config: Gen3Config):
        self.client = client
        self.config = config  # Use config.graphql_url consistently

    async def execute_graphql(self, query: str) -> Optional[Dict[str, Any]]:
        """Execute GraphQL query using config.graphql_url"""
        logger.info("Executing GraphQL query")
        logger.debug(f"Query: {query[:200]}{'...' if len(query) > 200 else ''}")

        result = await self.client.post_json(
            self.config.graphql_url,  # Use pre-computed URL from config
            json={"query": query},
        )

        if result is None:
            logger.error("GraphQL query execution failed")
            return None

        # Check for GraphQL errors
        if "errors" in result:
            logger.warning(f"GraphQL query returned errors: {result['errors']}")

        return result

    async def execute_field_sampling(
        self, entity_name: str, field_name: str, limit: int = 100
    ) -> Dict[str, Any]:
        """Execute query for field value sampling with processing"""
        query = f"""
        {{
            {entity_name}(first: {limit}) {{
                {field_name}
            }}
        }}
        """

        logger.info(f"Sampling field values for {entity_name}.{field_name}")
        result = await self.execute_graphql(query)

        if not result or "data" not in result:
            return {
                "error": f"Failed to fetch field values for {entity_name}.{field_name}",
                "query": query.strip(),
            }

        # Process field values
        entity_data = result["data"].get(entity_name, [])
        value_counts = {}

        for record in entity_data:
            value = record.get(field_name)
            if value is not None:
                value_str = str(value)
                value_counts[value_str] = value_counts.get(value_str, 0) + 1

        # Sort by frequency
        sorted_values = dict(
            sorted(value_counts.items(), key=lambda x: x[1], reverse=True)
        )

        logger.debug(f"Found {len(value_counts)} unique values for {field_name}")

        return {
            "entity": entity_name,
            "field": field_name,
            "total_records": len(entity_data),
            "unique_values": len(value_counts),
            "values": sorted_values,
            "query_used": query.strip(),
        }

    async def execute_exploration_query(
        self, entity_name: str, fields: list[str], limit: int = 5
    ) -> Dict[str, Any]:
        """Execute query for entity exploration"""
        # Format fields for GraphQL
        fields_str = "\n        ".join(fields)
        query = f"""
        {{
            {entity_name}(first: {limit}) {{
                {fields_str}
            }}
        }}
        """

        logger.info(f"Exploring entity {entity_name} with {len(fields)} fields")
        result = await self.execute_graphql(query)

        if not result or "data" not in result:
            return {
                "error": f"Failed to explore entity {entity_name}",
                "query": query.strip(),
            }

        entity_data = result["data"].get(entity_name, [])

        return {
            "entity": entity_name,
            "total_records_returned": len(entity_data),
            "fields_queried": fields,
            "sample_records": entity_data,
            "query_used": query.strip(),
        }
