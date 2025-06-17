#!/bin/bash
set -e

echo "Running tests for OrcaSlicer Quotation Machine"

# Check if uv environment exists
if [ ! -d ".venv" ]; then
    echo "ERROR: uv environment not found. Run ./scripts/setup.sh first"
    exit 1
fi

echo "Running Python tests..."
uv run pytest -v

echo "Testing Rust components..."
uv run python -c "
from orca_quote_machine._rust_core import validate_3d_model
import tempfile
import os

# Test with the PoC STL file
if os.path.exists('test_cube.stl'):
    result = validate_3d_model('test_cube.stl')
    print(f'STL validation: {result.is_valid} ({result.file_type}, {result.file_size} bytes)')
else:
    print('WARNING: test_cube.stl not found, skipping validation test')
"

echo "Testing OrcaSlicer CLI..."
uv run python poc_orcaslicer.py

echo "Testing configuration..."
uv run python -c "
from app.core.config import get_settings
from app.services.pricing import PricingService
from app.models.quote import SlicingResult

settings = get_settings()
print(f'Config loaded: {settings.app_name}')

# Test pricing calculation
pricing = PricingService()
mock_result = SlicingResult(print_time_minutes=90, filament_weight_grams=25.5)
cost = pricing.calculate_quote(mock_result)
print(f'Pricing test: {cost[\"total_cost\"]:.2f} SGD')
"

echo "All tests completed!"