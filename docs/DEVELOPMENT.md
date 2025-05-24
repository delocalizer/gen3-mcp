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

### Core Components

- **`main.py`** - MCP server setup and tool definitions
- **`client.py`** - Gen3 HTTP client
- **`data.py`** - Gen3 data operations and schema caching
- **`query.py`** - GraphQL validation and execution
- **`config.py`** - Configuration management

### Project Structure

```
gen3-mcp/
├── src/gen3_mcp/           # Main package
│   ├── __init__.py         # Package exports
│   ├── main.py             # MCP server & tool definitions
│   ├── client.py           # Gen3 HTTP client
│   ├── auth.py             # Authentication management
│   ├── data.py             # Gen3 data service operations
│   ├── query.py            # GraphQL operations & validation
│   ├── graphql_parser.py   # GraphQL AST parsing
│   ├── config.py           # Configuration management
│   └── exceptions.py       # Custom exceptions
├── tests/                  # Test suite
├── docs/                   # Documentation
└── pyproject.toml          # Project configuration
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
