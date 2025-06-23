#!/bin/bash
set -e

echo "Starting Celery worker for background processing"

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

echo "Starting Celery worker..."

uv run celery -A orca_quote_machine.tasks worker \
    --loglevel=info \
    --concurrency=2 \
    --hostname=worker@%h