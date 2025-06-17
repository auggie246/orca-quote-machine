#!/bin/bash
set -e

echo "Formatting code with black and isort"

# Check if uv environment exists
if [ ! -d ".venv" ]; then
    echo "ERROR: uv environment not found. Run ./scripts/setup.sh first"
    exit 1
fi

echo "Running black..."
uv run black .

echo "Running isort..."
uv run isort .

echo "Running mypy type checks..."
uv run mypy app/ --ignore-missing-imports

echo "Code formatting complete!"