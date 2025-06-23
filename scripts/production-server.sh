#!/bin/bash
set -e

echo "Starting OrcaSlicer Quotation Machine production server"

# Check if uv environment exists
if [ ! -d ".venv" ]; then
    echo "ERROR: uv environment not found. Run ./scripts/setup.sh first"
    exit 1
fi

# Check if Redis is running
if ! redis-cli ping &> /dev/null; then
    echo "ERROR: Redis is not running. Please start it first:"
    echo "redis-server"
    exit 1
fi

echo "Environment: $(cat .env | grep DEBUG || echo 'DEBUG=false')"
echo "Starting FastAPI production server..."

uv run uvicorn orca_quote_machine.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 4 \
    --log-level warning \
    --access-log