"""Unified MCP tools with consolidated functionality"""

import logging
from typing import Dict, Any
from ..schema.service import SchemaService
from ..schema.validation import ValidationService
from ..query.builder import QueryBuilder
from ..query.executor import QueryExecutor
from ..client.gen3_client import Gen3ClientProtocol
from ..config.settings import Gen3Config

logger = logging.getLogger("gen3-mcp.tools")


class UnifiedTools:
    """Consolidated MCP tools with shared services"""

    def __init__(self, client: Gen3ClientProtocol, config: Gen3Config):
        self.config = config

        # Initialize services with proper dependencies
        self.schema_service = SchemaService(client, config)
        self.validation_service = ValidationService(self.schema_service)
        self.query_builder = QueryBuilder(self.schema_service)
        self.query_executor = QueryExecutor(client, config)

        logger.info("Unified tools initialized")

    # Schema Operations
    async def schema_summary(self) -> Dict[str, Any]:
        """Get schema summary using service"""
        return await self.schema_service.get_schema_summary()

    async def schema_full(self) -> Dict[str, Any]:
        """Get full schema"""
        return await self.schema_service.get_full_schema()

    async def schema_entity(self, entity_name: str) -> Dict[str, Any]:
        """Get schema for specific entity"""
        return await self.schema_service.get_entity_schema(entity_name)

    async def schema_entities(self) -> Dict[str, Any]:
        """Get list of all entities"""
        entities = await self.schema_service.get_entity_names()
        return {"entities": entities}

    async def schema_list_available_entities(self) -> Dict[str, Any]:
        """Get detailed entity list with relationships (backward compatibility)"""
        full_schema = await self.schema_service.get_full_schema()

        entities = {}
        all_links = []

        for entity_name, entity_data in full_schema.items():
            if isinstance(entity_data, dict):
                # Extract link information
                links = entity_data.get("links", [])
                processed_links = []

                for link in links:
                    if isinstance(link, dict):
                        # Handle subgroup links (common in Gen3)
                        if "subgroup" in link:
                            for sublink in link.get("subgroup", []):
                                if isinstance(sublink, dict):
                                    link_info = {
                                        "target_entity": sublink.get("target_type"),
                                        "relationship": sublink.get(
                                            "label", "related_to"
                                        ),
                                        "multiplicity": sublink.get(
                                            "multiplicity", "unknown"
                                        ),
                                        "required": sublink.get("required", False),
                                        "backref": sublink.get("backref"),
                                    }
                                    processed_links.append(link_info)
                                    all_links.append(
                                        {
                                            "from": entity_name,
                                            "to": sublink.get("target_type"),
                                            "relationship": sublink.get(
                                                "label", "related_to"
                                            ),
                                            "multiplicity": sublink.get(
                                                "multiplicity", "unknown"
                                            ),
                                        }
                                    )
                        else:
                            # Direct link
                            link_info = {
                                "target_entity": link.get("target_type"),
                                "relationship": link.get("label", "related_to"),
                                "multiplicity": link.get("multiplicity", "unknown"),
                                "required": link.get("required", False),
                                "backref": link.get("backref"),
                            }
                            processed_links.append(link_info)
                            all_links.append(
                                {
                                    "from": entity_name,
                                    "to": link.get("target_type"),
                                    "relationship": link.get("label", "related_to"),
                                    "multiplicity": link.get("multiplicity", "unknown"),
                                }
                            )

                entities[entity_name] = {
                    "title": entity_data.get("title", ""),
                    "description": entity_data.get("description", ""),
                    "category": entity_data.get("category", ""),
                    "properties_count": len(entity_data.get("properties", {})),
                    "links": processed_links,
                    "links_count": len(processed_links),
                }

        # Build relationship summary
        relationship_summary = {}
        for link in all_links:
            rel_type = link["relationship"]
            if rel_type not in relationship_summary:
                relationship_summary[rel_type] = []
            relationship_summary[rel_type].append(f"{link['from']} -> {link['to']}")

        # Find entities by category
        entities_by_category = {}
        for entity_name, entity_info in entities.items():
            category = entity_info["category"] or "uncategorized"
            if category not in entities_by_category:
                entities_by_category[category] = []
            entities_by_category[category].append(entity_name)

        return {
            "total_entities": len(entities),
            "entities": entities,
            "entities_by_category": entities_by_category,
            "relationship_summary": relationship_summary,
            "total_relationships": len(all_links),
            "common_graphql_patterns": {
                "hierarchical_query": "project -> study -> subject -> sample -> files",
                "file_with_subject": "Use links to query: file { subjects { age_at_enrollment sex } }",
                "subject_with_samples": "Use links to query: subject { samples { sample_type anatomic_site } }",
            },
        }

    # Data Operations
    async def data_explore(self, entity_name: str, **kwargs) -> Dict[str, Any]:
        """Explore entity using query builder"""
        field_count = kwargs.get("field_count", 15)
        record_limit = kwargs.get("limit", 5)

        # Build safe query
        query = await self.query_builder.build_safe_query(
            entity_name, field_count, record_limit
        )

        # Execute query
        result = await self.query_executor.execute_graphql(query)

        return {
            "entity": entity_name,
            "query_used": query,
            "result": result or {"error": "Query execution failed"},
        }

    async def data_sample_records(self, entity_name: str, **kwargs) -> Dict[str, Any]:
        """Get sample records for entity"""
        limit = kwargs.get("limit", 5)

        # Get schema to select fields intelligently
        schema = await self.schema_service.get_entity_schema(entity_name)
        fields = await self.query_builder._select_optimal_fields(schema, 15)

        # Execute exploration query
        result = await self.query_executor.execute_exploration_query(
            entity_name, fields, limit
        )

        return result

    async def data_field_values(
        self, entity_name: str, field_name: str, **kwargs
    ) -> Dict[str, Any]:
        """Get field values using query executor"""
        limit = kwargs.get("limit", 20)
        return await self.query_executor.execute_field_sampling(
            entity_name, field_name, limit
        )

    async def data_explore_entity_data(self, entity_name: str) -> Dict[str, Any]:
        """Comprehensive entity exploration (backward compatibility)"""
        schema = await self.schema_service.get_entity_schema(entity_name)

        # Get sample records
        sample_result = await self.data_sample_records(entity_name, limit=3)

        # Analyze schema for enum fields and important fields
        properties = schema.get("properties", {})
        enum_fields = []
        important_fields = []

        for field_name, field_def in properties.items():
            if isinstance(field_def, dict):
                if "enum" in field_def:
                    enum_fields.append(
                        {"field": field_name, "enum_values": field_def["enum"]}
                    )

                # Mark fields that are likely important for filtering
                if any(
                    keyword in field_name.lower()
                    for keyword in [
                        "type",
                        "format",
                        "category",
                        "sex",
                        "race",
                        "status",
                    ]
                ):
                    important_fields.append(field_name)

        return {
            "entity": entity_name,
            "schema_info": {
                "title": schema.get("title", ""),
                "description": schema.get("description", ""),
                "category": schema.get("category", ""),
                "total_properties": len(properties),
                "required_fields": schema.get("required", []),
            },
            "enum_fields": enum_fields,
            "important_filtering_fields": important_fields,
            "sample_records": sample_result.get("sample_records", []),
        }

    # Query Operations
    async def query_graphql(self, query: str) -> Dict[str, Any]:
        """Execute GraphQL query"""
        result = await self.query_executor.execute_graphql(query)
        if result is None:
            return {"error": "Query execution failed"}
        return result

    # Validation Operations
    async def validation_validate_query_fields(self, query: str) -> Dict[str, Any]:
        """Validate query fields"""
        return await self.validation_service.validate_query_fields(query)

    async def validation_suggest_similar_fields(
        self, field_name: str, entity_name: str
    ) -> Dict[str, Any]:
        """Suggest similar fields"""
        return await self.validation_service.suggest_similar_fields(
            field_name, entity_name
        )

    async def validation_get_query_template(
        self, entity_name: str, **kwargs
    ) -> Dict[str, Any]:
        """Generate query template"""
        include_relationships = kwargs.get("include_relationships", True)
        max_fields = kwargs.get("max_fields", 20)
        return await self.validation_service.generate_query_template(
            entity_name, include_relationships, max_fields
        )
