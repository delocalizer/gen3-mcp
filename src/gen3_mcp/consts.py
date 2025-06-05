"""High-value constants for the Gen3 MCP package."""

# Package metadata
PACKAGE_VERSION = "1.2.0"
SERVER_NAME = "gen3-mcp"
USER_AGENT = f"{SERVER_NAME}/{PACKAGE_VERSION}"

# External API contract consts
AUTH_URL_PATH = "/user/credentials/cdis/access_token"
GRAPHQL_URL_PATH = "/api/v0/submission/graphql"
SCHEMA_URL_PATH = "/api/v0/submission/_dictionary/_all"

# Business logic consts
TOKEN_REFRESH_BUFFER_MINUTES = 5  # refresh 5min early
DEFAULT_TOKEN_EXPIRY_SECONDS = 1800  # 30 minutes
