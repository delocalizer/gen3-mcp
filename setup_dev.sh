#!/usr/bin/env bash
"""
Setup script for Gen3 MCP development environment
Works with current version of uv
"""

set -e

echo "🚀 Setting up Gen3 MCP development environment..."

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ uv is not installed. Please install it first:"
    echo "curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

echo "✅ uv found: $(uv --version)"

# Create virtual environment
echo "📦 Creating virtual environment..."
uv venv

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Install main dependencies
echo "📥 Installing main dependencies..."
uv pip install -e .

# Install development dependencies
echo "🛠️ Installing development dependencies..."
uv pip install \
    'pytest>=7.0.0' \
    'pytest-asyncio>=0.20.0' \
    'black>=22.0.0' \
    'ruff>=0.1.0' \
    'mypy>=1.0.0' \
    'coverage>=7.0.0'

echo "✅ Setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Activate the virtual environment:"
echo "   source .venv/bin/activate"
echo ""
echo "2. Run tests:"
echo "   pytest -v -W default"
echo ""
echo "3. Format code:"
echo "   black src/ tests/"
