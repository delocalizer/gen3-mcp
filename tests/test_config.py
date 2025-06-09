"""Tests for config module"""

import os

import pytest
from pydantic import ValidationError

from gen3_mcp.config import Config
from gen3_mcp.consts import (
    AUTH_URL_PATH,
    GRAPHQL_URL_PATH,
    SCHEMA_URL_PATH,
)


class TestConfig:
    """Test Config class functionality"""

    def test_config_defaults_and_creation(self, clean_config):
        """Test config creation and default values"""
        assert clean_config.base_url == "https://gen3.datacommons.io"
        assert clean_config.log_level == "INFO"
        assert clean_config.credentials_file == "~/credentials.json"
        assert clean_config.timeout_seconds == 30

        # Test computed properties
        assert clean_config.auth_url.endswith(AUTH_URL_PATH)
        assert clean_config.graphql_url.endswith(GRAPHQL_URL_PATH)
        assert clean_config.schema_url.endswith(SCHEMA_URL_PATH)

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

        assert config.auth_url == f"{custom_base}{AUTH_URL_PATH}"
        assert config.graphql_url == f"{custom_base}{GRAPHQL_URL_PATH}"
        assert config.schema_url == f"{custom_base}{SCHEMA_URL_PATH}"

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

    def test_env_vars_isolated_from_defaults(self, clean_env):
        """Test that environment variables don't affect default testing"""
        # This test runs with clean_env, so should see defaults
        config = Config()
        assert config.base_url == "https://gen3.datacommons.io"
        assert config.log_level == "INFO"

        # Now set an env var within the test
        os.environ["GEN3MCP_LOG_LEVEL"] = "DEBUG"
        config_with_env = Config()
        assert config_with_env.log_level == "DEBUG"

        # The clean_env fixture will restore the original state
