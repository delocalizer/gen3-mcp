"""Tests for config module"""

import os

import pytest
from pydantic import ValidationError

from gen3_mcp.config import Config


class TestConfig:
    """Test Config class functionality"""

    def test_config_creation(self):
        """Test that config can be created"""
        config = Config()
        assert config.base_url == "https://gen3.datacommons.io"
        assert config.log_level == "INFO"

    def test_config_properties(self):
        """Test that config properties work"""
        config = Config()
        assert config.auth_url.endswith("/user/credentials/cdis/access_token")
        assert config.graphql_url.endswith("/api/v0/submission/graphql")
        assert config.schema_url.endswith("/api/v0/submission/_dictionary/_all")

    def test_config_validation(self):
        """Test that config validation works"""
        # Invalid log level should raise ValidationError
        with pytest.raises(ValidationError):
            Config(log_level="not-a-log-level")

    def test_config_env_override(self):
        """Test environment variable override"""
        # Set environment variable
        original = os.environ.get("GEN3MCP_BASE_URL")
        os.environ["GEN3MCP_BASE_URL"] = "https://test.example.com"

        try:
            config = Config()
            assert config.base_url == "https://test.example.com"
        finally:
            # Clean up environment variable
            if original:
                os.environ["GEN3MCP_BASE_URL"] = original
            else:
                os.environ.pop("GEN3MCP_BASE_URL", None)

    #    def test_config_defaults(self):
    #        """Test that config has correct default values"""
    #        original = os.environ.get(
    #        config = Config()
    #        assert config.credentials_file.endswith("/credentials.json")
    #        assert config.timeout_seconds == 30

    def test_config_custom_values(self):
        """Test creating config with custom values"""
        config = Config(
            base_url="https://custom.gen3.io",
            log_level="DEBUG",
            timeout_seconds=60,
        )
        assert config.base_url == "https://custom.gen3.io"
        assert config.log_level == "DEBUG"
        assert config.timeout_seconds == 60

    def test_computed_fields_with_custom_base_url(self):
        """Test that computed fields work with custom base URL"""
        custom_base = "https://custom.gen3.io"
        config = Config(base_url=custom_base)

        assert config.auth_url == f"{custom_base}/user/credentials/cdis/access_token"
        assert config.graphql_url == f"{custom_base}/api/v0/submission/graphql"
        assert config.schema_url == f"{custom_base}/api/v0/submission/_dictionary/_all"

    @pytest.mark.parametrize("log_level", ["DEBUG", "INFO", "WARNING", "ERROR"])
    def test_valid_log_levels(self, log_level):
        """Test that all valid log levels are accepted"""
        config = Config(log_level=log_level)
        assert config.log_level == log_level

    @pytest.mark.parametrize(
        "invalid_level", ["TRACE", "debug", "info", "FATAL", "NONE"]
    )
    def test_invalid_log_levels(self, invalid_level):
        """Test that invalid log levels are rejected"""
        with pytest.raises(ValidationError):
            Config(log_level=invalid_level)

    def test_timeout_validation(self):
        """Test timeout seconds validation"""
        # Valid timeout
        config = Config(timeout_seconds=120)
        assert config.timeout_seconds == 120

        # Invalid timeout (too small)
        with pytest.raises(ValidationError):
            Config(timeout_seconds=0)

        # Invalid timeout (too large)
        with pytest.raises(ValidationError):
            Config(timeout_seconds=500)
