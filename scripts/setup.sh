#!/bin/bash
set -e

echo "Setting up OrcaSlicer Quotation Machine with uv"

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "ERROR: uv is not installed. Please install it first:"
    echo "curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Check if rust is installed
if ! command -v cargo &> /dev/null; then
    echo "ERROR: Rust is not installed. Please install it first:"
    echo "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
    exit 1
fi

echo "Creating uv environment and installing dependencies..."
uv sync --group dev

echo "Building Rust components..."
uv run maturin develop

echo "Creating necessary directories..."
mkdir -p uploads static config/slicer_profiles/{machine,filament,process}

echo "Setting up environment file..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Please edit .env with your configuration"
else
    echo ".env already exists"
fi

echo "Running basic tests..."
uv run python -c "
try:
    from orca_quote_machine._rust_core import validate_3d_model
    print('Rust components loaded successfully')
except ImportError as e:
    print(f'ERROR: Rust components failed to load: {e}')

try:
    from app.core.config import get_settings
    settings = get_settings()
    print(f'Configuration loaded: {settings.app_name}')
except Exception as e:
    print(f'ERROR: Configuration failed: {e}')
"

echo ""
echo "Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env with your configuration"
echo "2. Set up OrcaSlicer profiles in config/slicer_profiles/"
echo "3. Start Redis: redis-server"
echo "4. Start Celery worker: uv run celery -A app.tasks worker --loglevel=info"
echo "5. Start the app: uv run uvicorn app.main:app --reload"
echo ""
echo "Or use the provided scripts:"
echo "- ./scripts/web-server.sh       - Start web server (development)"
echo "- ./scripts/production-server.sh - Start web server (production)"
echo "- ./scripts/worker.sh           - Start Celery worker"
echo "- ./scripts/test.sh             - Run tests"