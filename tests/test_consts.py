from gen3_mcp.consts import (
    AUTH_URL_PATH,
    GRAPHQL_URL_PATH,
    PACKAGE_VERSION,
    SCHEMA_URL_PATH,
    SERVER_NAME,
    USER_AGENT,
)


class TestPackageConstants:
    """Test package constants are properly defined"""

    def test_package_version_defined(self):
        """Test that package version is defined"""
        assert isinstance(PACKAGE_VERSION, str)
        assert len(PACKAGE_VERSION) > 0
        assert "." in PACKAGE_VERSION  # Should be semantic version

    def test_user_agent_format(self):
        """Test that user agent follows expected format"""
        expected_user_agent = f"{SERVER_NAME}/{PACKAGE_VERSION}"
        assert USER_AGENT == expected_user_agent
        assert "/" in USER_AGENT
        assert USER_AGENT.startswith(SERVER_NAME)

    def test_url_path_constants(self):
        """Test that URL path constants are properly defined"""
        # All should start with / and not be empty
        assert AUTH_URL_PATH.startswith("/")
        assert GRAPHQL_URL_PATH.startswith("/")
        assert SCHEMA_URL_PATH.startswith("/")

        assert len(AUTH_URL_PATH) > 1
        assert len(GRAPHQL_URL_PATH) > 1
        assert len(SCHEMA_URL_PATH) > 1

        # Should contain expected path segments
        assert "credentials" in AUTH_URL_PATH
        assert "graphql" in GRAPHQL_URL_PATH
        assert "dictionary" in SCHEMA_URL_PATH
