"""Comprehensive tests for the SchemaManager module"""

import json

import pytest

from gen3_mcp.config import Config
from gen3_mcp.exceptions import Gen3SchemaError
from gen3_mcp.models import EntitySchema, SchemaExtract
from gen3_mcp.schema import SchemaManager, get_schema_manager


class TestSchemaManagerInitialization:
    """Test SchemaManager initialization and basic properties"""

    def test_schema_manager_initialization(self, mock_client):
        """Test SchemaManager initialization"""
        manager = SchemaManager(mock_client)

        assert manager.client is mock_client
        assert isinstance(manager._cache, dict)
        assert isinstance(manager.config, Config)
        assert len(manager._cache) == 0


class TestGetSchemaFull:
    """Test get_schema_full method"""

    @pytest.mark.asyncio
    async def test_get_schema_full_success(self, schema_manager, test_schema):
        """Test successful schema fetch"""
        result = await schema_manager.get_schema_full()

        assert result == test_schema
        assert isinstance(result, dict)
        assert "subject" in result
        assert "sample" in result
        assert "study" in result

    @pytest.mark.asyncio
    async def test_get_schema_full_caching(self, schema_manager):
        """Test that full schema is cached properly"""
        # First call should hit the client
        schema1 = await schema_manager.get_schema_full()
        assert schema_manager.client.get_json.call_count == 1

        # Second call should use cache
        schema2 = await schema_manager.get_schema_full()
        assert schema_manager.client.get_json.call_count == 1  # No additional calls
        assert schema1 is schema2  # Same object reference

    @pytest.mark.asyncio
    async def test_get_schema_full_network_error(self, mock_client):
        """Test handling of network errors"""
        mock_client.get_json.side_effect = None  # Clear side_effect
        mock_client.get_json.return_value = None
        manager = SchemaManager(mock_client)

        with pytest.raises(Gen3SchemaError, match="Failed to fetch schema from Gen3"):
            await manager.get_schema_full()

    @pytest.mark.asyncio
    async def test_get_schema_full_cache_after_error(self, mock_client, test_schema):
        """Test that cache is not populated after errors"""
        manager = SchemaManager(mock_client)
        manager.clear_cache()

        # First call fails
        mock_client.get_json.side_effect = None  # Clear side_effect
        mock_client.get_json.return_value = None
        with pytest.raises(Gen3SchemaError):
            await manager.get_schema_full()

        # Cache should be empty
        assert "full_schema" not in manager._cache

        # Second call succeeds
        mock_client.get_json.return_value = test_schema
        result = await manager.get_schema_full()
        assert result == test_schema


class TestGetSchemaExtract:
    """Test get_schema_extract method"""

    @pytest.mark.asyncio
    async def test_get_schema_extract_success(self, schema_extract):
        """Test successful schema extract creation"""
        assert isinstance(schema_extract, SchemaExtract)
        assert isinstance(schema_extract, dict)  # Should be dict subclass

        # Check expected entities are present
        expected_entities = {
            "subject",
            "sample",
            "study",
            "aliquot",
            "aligned_reads_file",
        }
        assert set(schema_extract.keys()) == expected_entities

    @pytest.mark.asyncio
    async def test_get_schema_extract_caching(self, schema_manager):
        """Test that schema extract is cached properly"""
        # First call should create extract
        extract1 = await schema_manager.get_schema_extract()

        # Second call should use cache
        extract2 = await schema_manager.get_schema_extract()
        assert extract1 is extract2  # Same object reference

    @pytest.mark.asyncio
    async def test_get_schema_extract_entities_structure(self, schema_extract):
        """Test that entities have correct structure"""
        for entity_name, entity in schema_extract.items():
            assert isinstance(entity, EntitySchema)
            assert entity.name == entity_name
            assert hasattr(entity, "fields")
            assert hasattr(entity, "relationships")
            assert hasattr(entity, "schema_summary")
            assert isinstance(entity.fields, dict)
            assert isinstance(entity.relationships, dict)

    @pytest.mark.asyncio
    async def test_schema_extract_serialization(
        self, schema_extract, reference_extract_json
    ):
        """Test that schema extract serializes correctly"""
        # Convert to JSON and compare with reference
        json_output = json.dumps(schema_extract.to_json(), sort_keys=True)

        # Parse both for comparison (to handle formatting differences)
        output_data = json.loads(json_output)
        reference_data = json.loads(reference_extract_json)

        assert output_data == reference_data

    @pytest.mark.asyncio
    async def test_schema_extract_to_json_method(self, schema_extract):
        """Test the to_json method specifically"""
        json_data = schema_extract.to_json()

        assert isinstance(json_data, dict)
        assert set(json_data.keys()) == set(schema_extract.keys())

        # Each entity should be a dict (model_dump result)
        for entity_name, entity_data in json_data.items():
            assert isinstance(entity_data, dict)
            assert entity_data["name"] == entity_name
            assert "fields" in entity_data
            assert "relationships" in entity_data
            assert "schema_summary" in entity_data


class TestCacheManagement:
    """Test cache management functionality"""

    def test_clear_cache(self, schema_manager):
        """Test cache clearing"""
        # Add something to cache manually
        schema_manager._cache["test"] = "value"
        assert len(schema_manager._cache) == 1

        # Clear cache
        schema_manager.clear_cache()
        assert len(schema_manager._cache) == 0

    @pytest.mark.asyncio
    async def test_clear_cache_forces_refetch(self, schema_manager):
        """Test that clearing cache forces refetch"""
        # First fetch
        extract1 = await schema_manager.get_schema_extract()

        # Clear cache
        schema_manager.clear_cache()

        # Second fetch should create new object
        extract2 = await schema_manager.get_schema_extract()
        assert extract1 is not extract2

    @pytest.mark.asyncio
    async def test_cache_independence(self, schema_manager):
        """Test that full_schema and extract caches are independent"""
        # Get full schema
        await schema_manager.get_schema_full()
        assert "full_schema" in schema_manager._cache
        assert "extract" not in schema_manager._cache

        # Get extract (should use cached full_schema)
        await schema_manager.get_schema_extract()
        assert "extract" in schema_manager._cache

        # Both should be cached
        assert len(schema_manager._cache) == 2


class TestSchemaExtractModel:
    """Test SchemaExtract dict functionality"""

    @pytest.mark.asyncio
    async def test_schema_extract_dict_interface(self, schema_extract):
        """Test that SchemaExtract works as a dict"""
        # Test dict operations
        assert len(schema_extract) == 5
        assert "subject" in schema_extract
        assert list(schema_extract.keys())

        # Test iteration
        for entity_name, entity in schema_extract.items():
            assert isinstance(entity_name, str)
            assert isinstance(entity, EntitySchema)

        # Test access
        subject = schema_extract["subject"]
        assert subject.name == "subject"

    @pytest.mark.asyncio
    async def test_schema_extract_type_checking(self, schema_extract):
        """Test type properties of SchemaExtract"""
        assert isinstance(schema_extract, dict)
        assert isinstance(schema_extract, SchemaExtract)

    def test_schema_extract_creation(self):
        """Test creating empty SchemaExtract"""
        extract = SchemaExtract()
        assert isinstance(extract, dict)
        assert len(extract) == 0

        # Should be able to add items
        from gen3_mcp.models import EntitySchema

        entity = EntitySchema(name="test")
        extract["test"] = entity
        assert extract["test"] is entity


class TestRelationshipExtraction:
    """Test relationship extraction logic"""

    @pytest.mark.asyncio
    async def test_relationship_extraction(self, schema_extract):
        """Test that relationships are extracted correctly"""
        subject = schema_extract["subject"]

        # Subject should have relationship to studies
        assert "studies" in subject.relationships
        studies_rel = subject.relationships["studies"]
        assert studies_rel.target_type == "study"
        assert studies_rel.link_type.value == "child_of"

    @pytest.mark.asyncio
    async def test_backref_relationships(self, schema_extract):
        """Test that backref relationships are added correctly"""
        study = schema_extract["study"]

        # Study should have backref relationship from subject
        assert "subjects" in study.relationships
        subjects_rel = study.relationships["subjects"]
        assert subjects_rel.target_type == "subject"
        assert subjects_rel.link_type.value == "parent_of"

    @pytest.mark.asyncio
    async def test_relationship_closure(self, schema_extract):
        """Test that all relationships reference entities in the schema"""
        all_entities = set(schema_extract.keys())

        for entity in schema_extract.values():
            for rel in entity.relationships.values():
                assert rel.source_type in all_entities
                assert rel.target_type in all_entities


class TestFieldExtraction:
    """Test field extraction logic"""

    @pytest.mark.asyncio
    async def test_field_extraction(self, schema_extract):
        """Test that fields are extracted correctly"""
        subject = schema_extract["subject"]

        # Should have standard fields
        assert "id" in subject.fields
        assert "submitter_id" in subject.fields
        assert "type" in subject.fields

        # Should have entity-specific fields
        assert "gender" in subject.fields
        assert "race" in subject.fields
        assert "ethnicity" in subject.fields

    @pytest.mark.asyncio
    async def test_enum_field_extraction(self, schema_extract):
        """Test that enum fields are identified correctly"""
        sample = schema_extract["sample"]

        # Sample should have enum fields
        enum_fields = [f for f in sample.fields.values() if f.type_.value == "enum"]
        assert len(enum_fields) > 0

        # Check specific enum field
        fasting_status = sample.fields["fasting_status"]
        assert fasting_status.type_.value == "enum"
        assert fasting_status.enum_vals is not None
        assert len(fasting_status.enum_vals) > 0


class TestSchemaSummary:
    """Test schema summary generation"""

    @pytest.mark.asyncio
    async def test_schema_summary_generation(self, schema_extract):
        """Test that schema summaries are generated correctly"""
        subject = schema_extract["subject"]
        summary = subject.schema_summary

        assert summary is not None
        assert summary.title == "Subject"
        assert summary.category == "administrative"
        assert isinstance(summary.required_fields, list)
        assert summary.field_count > 0
        assert summary.parent_count >= 0
        assert summary.child_count >= 0

    @pytest.mark.asyncio
    async def test_position_description(self, schema_extract):
        """Test position description logic"""
        # Study should be root (no parents)
        study = schema_extract["study"]
        assert study.schema_summary.position_description == "root"

        # Aligned reads file should be leaf (no children)
        aligned_reads = schema_extract["aligned_reads_file"]
        assert aligned_reads.schema_summary.position_description == "leaf"

        # Subject should be intermediate (has both parents and children)
        subject = schema_extract["subject"]
        assert subject.schema_summary.position_description == "intermediate"


class TestSingletonFactory:
    """Test get_schema_manager singleton factory"""

    def test_get_schema_manager_returns_same_instance(self):
        """Test that get_schema_manager returns the same instance"""
        manager1 = get_schema_manager()
        manager2 = get_schema_manager()

        assert manager1 is manager2

    def test_get_schema_manager_cache_clear(self):
        """Test clearing the singleton cache"""
        manager1 = get_schema_manager()

        # Clear the cache
        get_schema_manager.cache_clear()

        # Should get new instance
        manager2 = get_schema_manager()
        assert manager1 is not manager2


class TestErrorHandling:
    """Test error handling scenarios"""

    @pytest.mark.asyncio
    async def test_schema_fetch_failure_propagates(self, mock_client):
        """Test that schema fetch failures propagate correctly"""
        mock_client.get_json.side_effect = Exception("Network error")
        manager = SchemaManager(mock_client)

        with pytest.raises(Exception, match="Network error"):
            await manager.get_schema_full()

    @pytest.mark.asyncio
    async def test_invalid_schema_handling(self, mock_client):
        """Test handling of invalid schema responses"""
        # Return empty dict instead of None to avoid Gen3SchemaError
        mock_client.get_json.side_effect = None  # Clear side_effect
        mock_client.get_json.return_value = {}
        manager = SchemaManager(mock_client)

        # Should handle empty schema gracefully
        extract = await manager.get_schema_extract()
        assert isinstance(extract, SchemaExtract)
        assert len(extract) == 0


class TestIntegration:
    """Integration tests combining multiple components"""

    @pytest.mark.asyncio
    async def test_full_workflow(self, mock_client, test_schema):
        """Test complete workflow from client to extract"""
        manager = SchemaManager(mock_client)

        # Get full schema
        full_schema = await manager.get_schema_full()
        assert full_schema == test_schema

        # Get extract
        extract = await manager.get_schema_extract()
        assert isinstance(extract, SchemaExtract)
        assert len(extract) > 0

        # All should use caching
        assert len(manager._cache) == 2  # full_schema and extract

    @pytest.mark.asyncio
    async def test_concurrent_access(self, schema_manager):
        """Test that concurrent access works correctly"""
        import asyncio

        # Simulate concurrent access
        results = await asyncio.gather(
            schema_manager.get_schema_extract(),
            schema_manager.get_schema_extract(),
            schema_manager.get_schema_extract(),
        )

        # All should be the same instance (cached)
        assert results[0] is results[1] is results[2]
