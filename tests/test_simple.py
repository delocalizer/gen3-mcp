"""Simple tests (verify pytest working)"""

from gen3_mcp.config import Config


def test_config_creation():
    """Test that config can be created"""
    config = Config()
    assert config.base_url == "https://gen3.datacommons.io"
    assert config.log_level == "INFO"


def test_config_properties():
    """Test that config properties work"""
    config = Config()
    assert config.auth_url.endswith("/user/credentials/cdis/access_token")
    assert config.graphql_url.endswith("/api/v0/submission/graphql")
    assert config.schema_url.endswith("/api/v0/submission/_dictionary/_all")


def test_config_validation():
    """Test that config validation works"""
    # Valid config
    config = Config(log_level="DEBUG")
    assert config.log_level == "DEBUG"


def test_config_env_override():
    """Test environment variable override"""
    import os

    # Set environment variable
    os.environ["GEN3MCP_BASE_URL"] = "https://test.example.com"

    config = Config()
    assert config.base_url == "https://test.example.com"

    # Clean up
    del os.environ["GEN3MCP_BASE_URL"]


def test_imports():
    """Test that all main imports work"""
    from gen3_mcp import (
        Config,
        Gen3Client,
        Gen3MCPError,
        QueryService,
        SchemaService,
    )

    # Should not raise any import errors
    assert Config is not None
    assert Gen3Client is not None
    assert SchemaService is not None
    assert QueryService is not None
    assert Gen3MCPError is not None


if __name__ == "__main__":
    # Run tests directly
    test_config_creation()
    test_config_properties()
    test_config_validation()
    test_config_env_override()
    test_imports()
    print("✅ All simple tests passed!")
