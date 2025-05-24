#!/bin/bash
set -e

if ! command -v uv &> /dev/null; then
    echo "Install uv first: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

echo "Ready! Run: source .venv/bin/activate && pytest"
