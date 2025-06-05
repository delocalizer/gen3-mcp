"""Tests for conf module"""

from unittest import TestCase

from pydantic import ValidationError

from gen3_mcp.config import Config


class TestConfig(TestCase):

    def test_config_creation(self):
        """Test that config can be created"""
        config = Config()
        self.assertEqual(config.base_url, "https://gen3.datacommons.io")
        self.assertEqual(config.log_level, "INFO")

    def test_config_properties(self):
        """Test that config properties work"""
        config = Config()
        self.assertTrue(config.auth_url.endswith("/user/credentials/cdis/access_token"))
        self.assertTrue(config.graphql_url.endswith("/api/v0/submission/graphql"))
        self.assertTrue(
            config.schema_url.endswith("/api/v0/submission/_dictionary/_all")
        )

    def test_config_validation(self):
        """Test that config validation works"""
        # Valid config
        with self.assertRaises(ValidationError):
            Config(log_level="not-a-log-level")

    def test_config_env_override(self):
        """Test environment variable override"""
        import os

        # Set environment variable
        original = os.environ.get("GEN3MCP_BASE_URL")
        os.environ["GEN3MCP_BASE_URL"] = "https://test.example.com"

        config = Config()
        self.assertEqual(config.base_url, "https://test.example.com")

        # Clean up
        if original:
            os.environ["GEN3MCP_BASE_URL"] = original
