# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

**Essential Commands:**
```bash
./scripts/setup.sh              # Initial setup with uv + Rust components
./scripts/web-server.sh          # Development server (auto-reload enabled)
./scripts/worker.sh              # Celery background worker
./scripts/production-server.sh   # Production server (4 workers, optimized)
./scripts/test.sh               # Full test suite (Python + Rust + integration)
./scripts/format.sh             # Code formatting (black, isort, mypy)
```

**Manual Commands:**
```bash
uv sync --group dev             # Install dependencies
maturin develop                 # Build Rust components
uv run pytest -xvs tests/      # Run specific tests
uv run celery -A app.tasks worker --loglevel=debug  # Debug worker
redis-cli ping                 # Verify Redis connection
```

**Build System:**
- Use `uv` for all Python package management (not pip/poetry)
- Use `maturin develop` to rebuild Rust components after changes
- Redis must be running before starting workers or web server

## System Architecture

**Core Processing Pipeline:**
```
HTTP Upload → FastAPI → File Validation (Rust) → Celery Queue → 
OrcaSlicer CLI → G-code Parsing → Pricing → Telegram Notification
```

**Component Separation:**
- **Web Layer** (`app/main.py`): FastAPI with async file upload, immediate responses
- **Worker Layer** (`app/tasks.py`): Celery background processing with `asyncio.run()`
- **Service Layer** (`app/services/`): Business logic isolation (slicer, pricing, telegram)
- **Performance Layer** (`src/lib.rs`): Rust validation via PyO3 bindings

**Critical Async Patterns:**
- FastAPI routes use chunked file reading (8KB chunks) to prevent memory DoS
- Celery tasks use `asyncio.run()` to execute async service calls
- All external calls (OrcaSlicer CLI, Telegram API) are properly awaited

## Configuration Management

**Settings Architecture:**
- **Central Config** (`app/core/config.py`): Pydantic BaseSettings with validation
- **Environment Variables**: All settings configurable via `.env` file
- **Security**: `SECRET_KEY` must be set in environment (no default)
- **Material Pricing**: Configurable per-kg costs for PLA/PETG/ASA in SGD

**Critical Settings:**
```python
ORCASLICER_CLI_PATH=/var/lib/flatpak/exports/bin/io.github.softfever.OrcaSlicer
SLICER_PROFILES_DIR=config/slicer_profiles/  # Required: machine/, filament/, process/ subdirs
TELEGRAM_BOT_TOKEN=                          # For admin notifications
TELEGRAM_ADMIN_CHAT_ID=                      # Where quotes are sent
```

## Security Implementation

**File Upload Protection:**
- `secure_filename()` function prevents path traversal attacks
- Streaming validation during upload (not after) prevents memory exhaustion
- Rust validation checks file integrity before expensive slicing operations

**Input Sanitization:**
- All user inputs validated through Pydantic models with custom validators
- Filename sanitization removes directory traversal characters
- File extension validation before processing

## OrcaSlicer Integration

**CLI Workflow:**
1. Model uploaded and validated
2. Appropriate material profile selected from `config/slicer_profiles/`
3. CLI executed with `--slice`, `--export-slicedata`, profile loading
4. G-code comments parsed for print time/filament usage
5. Results fed into pricing calculation

**Profile Management:**
- Profiles stored in `config/slicer_profiles/{machine,filament,process}/`
- Machine profile: `machine/default_machine.ini` (your 3D printer config)
- Material profiles: PLA (default), PETG, ASA in `filament/` directory
- Process profile: `process/standard_0.2mm.ini` (print settings)
- Symlink from existing OrcaSlicer installation recommended for easy updates

## Development vs Production

**Key Differences:**
- **Development**: Single worker, `--reload`, detailed logging, local Redis
- **Production**: Multi-worker (4), no reload, warning-level logs, containerized
- **Testing**: Use test Redis instance, mock OrcaSlicer for unit tests

**Docker Architecture:**
- Multi-stage build: builder stage (Rust compilation) + runtime stage
- Health checks for all services
- Nginx reverse proxy with security headers and upload optimization

## Celery Task Architecture

**Background Processing Design:**
- `process_quote_request()`: Main task orchestrating the pipeline
- `run_processing_pipeline()`: Async helper for service coordination
- `send_failure_notification()`: Error handling with admin alerts

**Task Flow:**
1. File validation (Rust)
2. Material enum parsing
3. Async pipeline execution (slicing → pricing → notification)
4. Result storage and cleanup

**Important Patterns:**
- Use full UUIDs for quote_id (collision prevention)
- Always clean up uploaded files in finally blocks
- Graceful degradation when external services unavailable

## Currency and Pricing

**Pricing Formula:**
```
total = (filament_kg × price_per_kg) × (print_time + 0.5h) × 1.1
minimum = S$5.00
```

**Currency**: All prices in Singapore Dollars (SGD), formatted as `S$X.XX`

## Common Issues and Patterns

**Memory Management:**
- Rust validation uses `BufReader` for streaming (never load entire files)
- Python file operations use chunked reading
- OrcaSlicer timeout protection (default 5 minutes)

**Error Handling:**
- Rust components have graceful fallback when unavailable
- Telegram notifications have error capture for debugging
- File cleanup always happens in finally blocks

**Testing Strategy:**
- Mock OrcaSlicer CLI for unit tests (avoid actual slicing)
- Test Rust validation with sample STL/OBJ/STEP files
- Integration tests should verify complete pipeline without external dependencies