"""Simple tests (verify pytest working)"""

from gen3_mcp.config import Gen3Config


def test_config_creation():
    """Test that config can be created"""
    config = Gen3Config()
    assert config.base_url == "https://gen3.datacommons.io"
    assert config.log_level == "INFO"


def test_config_properties():
    """Test that config properties work"""
    config = Gen3Config()
    assert config.auth_url.endswith("/user/credentials/cdis/access_token")
    assert config.graphql_url.endswith("/api/v0/submission/graphql")
    assert config.schema_url.endswith("/api/v0/submission/_dictionary/_all")


def test_config_validation():
    """Test that config validation works"""
    # Valid config
    config = Gen3Config(log_level="DEBUG")
    assert config.log_level == "DEBUG"


def test_config_env_override():
    """Test environment variable override"""
    import os

    # Set environment variable
    os.environ["GEN3_BASE_URL"] = "https://test.example.com"

    config = Gen3Config()
    assert config.base_url == "https://test.example.com"

    # Clean up
    del os.environ["GEN3_BASE_URL"]


def test_imports():
    """Test that all main imports work"""
    from gen3_mcp import (
        Gen3Client,
        Gen3Config,
        Gen3MCPError,
        Gen3Service,
        QueryService,
        extract_query_fields,
        validate_graphql,
    )

    # Should not raise any import errors
    assert Gen3Config is not None
    assert Gen3Client is not None
    assert Gen3Service is not None
    assert QueryService is not None
    assert Gen3MCPError is not None
    assert extract_query_fields is not None
    assert validate_graphql is not None


class TestLoggingSetup:
    """Test that logging setup works correctly"""

    def test_logging_setup_without_force(self):
        """Test that logging setup doesn't use force=True"""
        import logging

        from gen3_mcp.config import setup_logging

        # Clear any existing handlers
        root_logger = logging.getLogger()
        original_handlers = root_logger.handlers[:]
        root_logger.handlers = []

        try:
            # Set up logging
            logger = setup_logging("DEBUG")
            assert logger is not None
            assert logger.name == "gen3-mcp"

            # Should have added handlers without conflicts
            assert len(root_logger.handlers) > 0

            # Test that it doesn't override existing configuration
            setup_logging("INFO")  # Should not cause conflicts

        finally:
            # Restore original handlers
            root_logger.handlers = original_handlers

    def test_logging_respects_existing_configuration(self):
        """Test that logging respects existing configuration"""
        import logging

        from gen3_mcp.config import setup_logging

        # Set up a handler first
        logger = logging.getLogger()
        handler = logging.StreamHandler()
        logger.addHandler(handler)
        original_level = logger.level

        try:
            # This should just set level, not add new handlers
            setup_logging("DEBUG")

            # Should still have our handler
            assert handler in logger.handlers

        finally:
            # Clean up
            logger.removeHandler(handler)
            logger.setLevel(original_level)


if __name__ == "__main__":
    # Run tests directly
    test_config_creation()
    test_config_properties()
    test_config_validation()
    test_config_env_override()
    test_imports()
    print("✅ All simple tests passed!")
