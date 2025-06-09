# Gen3 MCP Development Guide

## Development Setup

```bash
# Clone the repository
git clone <repository-url>
cd gen3-mcp

# Create development environment
./setup_dev.sh

# Activate virtual environment
source .venv/bin/activate

# Run tests
pytest -v

# Format code
black src/ tests/

# Type checking
mypy src/
```

## Project Architecture

### Design Principles

This project follows [awslabs MCP design guidelines](https://github.com/awslabs/mcp/blob/main/DESIGN_GUIDELINES.md)

### Core Components

- **`server.py`** - MCP server setup and tool definitions
- **`client.py`** - Gen3 HTTP client
- **`schema.py`** - Gen3 schema operations
- **`query.py`** - GraphQL validation and execution
- **`models.py`** - Pydantic domain models
- **`config.py`** - Configuration management

### Project Structure

```
gen3-mcp/
├── src/gen3_mcp
│   ├── auth.py              # Token management
│   ├── client.py            # Gen3 HTTP client
│   ├── config.py            # Configuration management
│   ├── consts.py            # Constants
│   ├── exceptions.py        # Custom Exceptions
│   ├── graphql_validator.py # GraphQL query validation
│   ├── models.py            # Domain models
│   ├── query.py             # GraphQL operations
│   ├── schema.py            # Gen3 schema operations
│   ├── server.py            # MCP server & tool defs
│   └── utils.py             # Package utilities
├── tests/                   # Test suite
├── docs/                    # Documentation
└── pyproject.toml           # Project configuration
```

### Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_mcp_tools.py -v

# Run with coverage
coverage run -m pytest
```

### Code Quality

The project uses:
- **Black** for code formatting
- **Ruff** for linting
- **MyPy** for type checking
- **pytest** for testing
