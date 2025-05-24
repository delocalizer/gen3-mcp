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
        Tools,
    )

    # Should not raise any import errors
    assert Gen3Config is not None
    assert Gen3Client is not None
    assert Gen3Service is not None
    assert QueryService is not None
    assert Tools is not None
    assert Gen3MCPError is not None


if __name__ == "__main__":
    # Run tests directly
    test_config_creation()
    test_config_properties()
    test_config_validation()
    test_config_env_override()
    test_imports()
    print("✅ All simple tests passed!")
