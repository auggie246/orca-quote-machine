#!/bin/bash
set -e

echo "Formatting code with ruff"

# Check if uv environment exists
if [ ! -d ".venv" ]; then
    echo "ERROR: uv environment not found. Run ./scripts/setup.sh first"
    exit 1
fi

echo "Running ruff linting..."
uv run ruff check --fix .

echo "Running ruff formatting..."
uv run ruff format .

echo "Running mypy type checks..."
uv run mypy app/ --ignore-missing-imports

echo "Code formatting complete!"