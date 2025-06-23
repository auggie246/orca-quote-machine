#!/bin/bash
set -e

echo "Starting OrcaSlicer Quotation Machine web server"

# Check if uv environment exists
if [ ! -d ".venv" ]; then
    echo "ERROR: uv environment not found. Run ./scripts/setup.sh first"
    exit 1
fi

# Check if Redis is running
if ! redis-cli ping &> /dev/null; then
    echo "WARNING: Redis is not running. Starting redis-server..."
    redis-server --daemonize yes
    sleep 2
fi

echo "Environment: $(cat .env | grep DEBUG || echo 'DEBUG=true')"
echo "Starting FastAPI web server..."

uv run uvicorn orca_quote_machine.main:app \
    --reload \
    --host 0.0.0.0 \
    --port 8000 \
    --log-level info