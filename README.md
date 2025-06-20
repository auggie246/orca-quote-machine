# OrcaSlicer Quotation Generator

A web application for generating 3D printing quotations using OrcaSlicer CLI integration.

## Features

- **Web Interface**: Clean, responsive form for quote requests
- **File Validation**: Fast Rust-based validation for STL, OBJ, and STEP files
- **Background Processing**: Async slicing and quote generation with Celery
- **OrcaSlicer Integration**: Automated slicing with configurable material profiles
- **Pricing Engine**: Flexible pricing based on material, print time, and filament usage
- **Telegram Notifications**: Instant admin notifications for new quotes
- **Material Support**: PLA, PETG, and ASA with configurable pricing

## Architecture

- **FastAPI**: Web server and API endpoints
- **Rust (PyO3)**: High-performance file validation
- **Celery + Redis**: Background task processing
- **OrcaSlicer CLI**: 3D model slicing and analysis
- **Telegram Bot**: Admin notifications

## Installation

### Prerequisites

- [uv](https://docs.astral.sh/uv/) - Fast Python package manager
- Rust and Cargo
- Redis server
- OrcaSlicer (Flatpak installation)

### Setup

1. **Quick setup with uv:**
   ```bash
   git clone <repository>
   cd orca-quote-machine
   
   # Run automated setup
   ./scripts/setup.sh
   ```

   Or manually:
   ```bash
   # Install dependencies with uv
   uv sync --group dev
   
   # Build Rust components
   uv run maturin develop
   ```

2. **Configure environment:**
   ```bash
   cp example.env .env
   # Edit .env with your settings
   ```

3. **Development commands:**
   ```bash
   # Start web server (includes Redis check)
   ./scripts/web-server.sh
   
   # Start Celery worker (separate terminal)
   ./scripts/worker.sh
   
   # Run tests
   ./scripts/test.sh
   
   # Format code
   ./scripts/format.sh
   ```

   **Production:**
   ```bash
   # Start production server (4 workers, optimized)
   ./scripts/production-server.sh
   ```

   Or manually:
   ```bash
   # Start Redis
   redis-server
   
   # Start Celery worker
   uv run celery -A app.tasks worker --loglevel=info
   
   # Development server
   uv run uvicorn app.main:app --reload
   
   # Production server
   uv run uvicorn app.main:app --workers 4 --log-level warning
   ```

## Configuration

### Environment Variables

Key settings in `.env`:

- `ORCASLICER_CLI_PATH`: Path to OrcaSlicer CLI
- `TELEGRAM_BOT_TOKEN`: Telegram bot token
- `TELEGRAM_ADMIN_CHAT_ID`: Admin chat ID for notifications
- `MATERIAL_PRICES`: Pricing per kg for different materials

### Slicer Profiles

The application requires OrcaSlicer configuration files in `config/slicer_profiles/`:
```
config/slicer_profiles/
├── machine/
│   └── default_machine.json
├── filament/
│   ├── pla.json
│   ├── petg.json
│   └── asa.json
└── process/
    └── standard_0.2mm.json
```

#### Setting up OrcaSlicer Profiles

**Option 1: Symlink from existing OrcaSlicer installation**
```bash
# Find your OrcaSlicer config directory
# Linux: ~/.config/OrcaSlicer/ or ~/.OrcaSlicer/
# macOS: ~/Library/Application Support/OrcaSlicer/
# Windows: %APPDATA%\OrcaSlicer\

# Create symlinks to your existing profiles
ln -s ~/.config/OrcaSlicer/machine config/slicer_profiles/machine
ln -s ~/.config/OrcaSlicer/filament config/slicer_profiles/filament  
ln -s ~/.config/OrcaSlicer/process config/slicer_profiles/process
```

**Option 2: Copy profiles manually**
```bash
# Copy from OrcaSlicer installation
cp -r ~/.config/OrcaSlicer/machine config/slicer_profiles/
cp -r ~/.config/OrcaSlicer/filament config/slicer_profiles/
cp -r ~/.config/OrcaSlicer/process config/slicer_profiles/

# Rename/select your desired profiles
mv config/slicer_profiles/machine/your_printer.json config/slicer_profiles/machine/default_machine.json
mv config/slicer_profiles/process/your_process.json config/slicer_profiles/process/standard_0.2mm.json
```

**Required Profile Files:**
- `machine/default_machine.json` - Your 3D printer configuration
- `filament/pla.json` - PLA material settings
- `filament/petg.json` - PETG material settings (optional)
- `filament/asa.json` - ASA material settings (optional)
- `process/standard_0.2mm.json` - Print settings (layer height, speeds, etc.)

**Note:** Ensure the G-code settings include `G92 E0` in layer change G-code to prevent slicing errors.

#### Custom Materials

The system supports custom materials beyond the official PLA/PETG/ASA:

1. **Add custom filament profile**: Place `your_material.json` in `config/slicer_profiles/filament/`
2. **No code changes needed**: The system automatically discovers new materials
3. **Convention**: Material name matches filename (e.g., `TPU.json` for TPU material)
4. **Pricing**: Custom materials use PLA pricing by default

#### Configuration Override

You can override default profiles via environment variables:

```bash
# Override machine profile
SLICER_PROFILES__MACHINE=Bambu_Lab_P1S_0.4_nozzle.json

# Override process settings  
SLICER_PROFILES__PROCESS=0.20mm_Standard_@BBL_P1P.json

# Override official material profiles
SLICER_PROFILES__FILAMENT_PLA=Generic_PLA.json
SLICER_PROFILES__FILAMENT_PETG=Generic_PETG.json
```

## Usage

1. **User Flow:**
   - Visit the web interface
   - Fill out quote form (name, WhatsApp, material, color)
   - Upload 3D model file (.stl, .obj, .step)
   - Receive confirmation message

2. **Admin Flow:**
   - Receive Telegram notification with quote details
   - Review print time, filament usage, and calculated price
   - Contact customer via WhatsApp

## API Endpoints

- `POST /quote`: Submit quote request
- `GET /status/{task_id}`: Check processing status
- `GET /health`: Health check

## Pricing Formula

```
Total = (filament_kg × price_per_kg) × (print_time + 0.5h) × 1.1
Minimum: S$5.00
```

## Development

### Testing OrcaSlicer Integration

```bash
uv run python poc_orcaslicer.py [model_file.stl]
```

### Running Tests

```bash
./scripts/test.sh
# or
uv run pytest
```

### Code Formatting

```bash
./scripts/format.sh
# or manually:
uv run black .
uv run isort .
uv run mypy app/
```

## Deployment

### Docker (Recommended)

```bash
# Build image
docker build -t orca-quote-machine .

# Run with docker-compose
docker-compose up -d
```

### Nginx Configuration

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Troubleshooting

### Common Issues

1. **OrcaSlicer CLI not found:**
   - Verify `ORCASLICER_CLI_PATH` in `.env`
   - Check Flatpak installation

2. **Telegram notifications not working:**
   - Verify bot token and chat ID
   - Check bot permissions

3. **File validation errors:**
   - Ensure Rust components are built: `maturin develop`
   - Check file format and size limits

### Logs

- Application logs: Check FastAPI console output
- Celery logs: Check worker console output
- Redis logs: Check Redis server logs

## License

MIT License - see LICENSE file for details.