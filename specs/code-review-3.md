# Code Review 3: Maximum Simplification & Rust-First Architecture

## Executive Summary

This specification focuses on radical simplification while maintaining robustness. We'll move most business logic to Rust, keep Python as a thin orchestration layer, and retain Celery for handling long-running operations (based on expert advice about unpredictable slicing times).

## Core Principles

1. **SIMPLICITY FIRST**: Remove unnecessary complexity, consolidate duplicate logic
2. **RUST-FIRST**: Move all computational and business logic to Rust
3. **MODULAR FUNCTIONS**: Each function does ONE thing, easily testable
4. **PYTHON AS GLUE**: Python only handles HTTP, configuration, and external services
5. **PRACTICAL ARCHITECTURE**: Keep Celery for robustness but simplify its usage

## Phase 1: Rust Consolidation (Week 1)

### 1.1 Create Core Quote Pipeline Function
```rust
// New main function in src/lib.rs
#[pyfunction]
fn run_quote_pipeline(
    py: Python,
    file_contents: Vec<u8>,
    original_filename: String,
    material_type: String,
    slicer_path: String,
    slicer_profiles_dir: String,
    telegram_config: TelegramConfig,
) -> PyResult<QuoteResult> {
    // All business logic in one place:
    // 1. Validate filename
    // 2. Validate file contents
    // 3. Save to temp directory
    // 4. Resolve slicer profiles
    // 5. Execute slicer
    // 6. Parse G-code
    // 7. Calculate pricing
    // 8. Format output
    // 9. Clean up
    // Return complete result
}
```

### 1.2 Add Missing Rust Functions
```rust
// Profile resolution
#[pyfunction]
fn discover_available_materials(profiles_dir: String) -> PyResult<Vec<String>>

#[pyfunction]
fn resolve_profile_paths(
    profiles_dir: String,
    material: String,
    machine_profile: String,
    process_profile: String,
) -> PyResult<ProfilePaths>

// Error handling
#[pyclass(extends=PyException)]
pub enum OrcaError {
    InvalidFile { msg: String },
    ProfileNotFound { msg: String },
    SlicerFailed { msg: String },
    ParsingFailed { msg: String },
}
```

### 1.3 Modular Helper Functions
```rust
// Each function does ONE thing
#[pyfunction]
fn validate_filename(filename: &str) -> PyResult<String>

#[pyfunction]
fn validate_3d_file(contents: &[u8], extension: &str) -> PyResult<FileInfo>

#[pyfunction]
fn execute_slicer(
    model_path: &Path,
    profiles: &ProfilePaths,
    slicer_path: &Path,
) -> PyResult<PathBuf>  // Returns G-code path

#[pyfunction]
fn parse_gcode_metadata(gcode_path: &Path) -> PyResult<SlicingMetadata>

#[pyfunction]
fn calculate_final_quote(
    metadata: &SlicingMetadata,
    material: &str,
    pricing_config: &PricingConfig,
) -> PyResult<QuoteBreakdown>
```

## Phase 2: Simplify Python Layer (Week 2)

### 2.1 Simplified main.py
```python
# Single endpoint, minimal logic
@app.post("/quote")
async def create_quote(
    file: UploadFile,
    name: str = Form(...),
    mobile: str = Form(...),
    material: str = Form("PLA"),
):
    # 1. Basic validation
    contents = await file.read()
    
    # 2. Queue for processing
    task = process_quote.delay(
        contents, file.filename, name, mobile, material
    )
    
    return {"task_id": task.id, "status": "processing"}
```

### 2.2 Simplified tasks.py
```python
from _rust_core import run_quote_pipeline, OrcaError

@celery_app.task
def process_quote(contents: bytes, filename: str, name: str, mobile: str, material: str):
    try:
        result = run_quote_pipeline(
            file_contents=contents,
            original_filename=filename,
            material_type=material,
            slicer_path=settings.SLICER_PATH,
            slicer_profiles_dir=settings.PROFILES_DIR,
            telegram_config={
                "token": settings.TELEGRAM_TOKEN,
                "chat_id": settings.TELEGRAM_CHAT_ID,
                "customer_name": name,
                "customer_mobile": mobile,
            }
        )
        return result.to_dict()
    except OrcaError as e:
        # Rust errors are already well-formatted
        return {"error": str(e)}
```

### 2.3 Remove Service Layer
- Delete `services/` directory entirely
- All logic now in Rust
- Python only orchestrates

## Phase 3: Modular Testing (Week 3)

### 3.1 Test Structure
```
tests/
├── rust/
│   ├── test_validation.rs      # Test each validation function
│   ├── test_parsing.rs         # Test G-code parsing
│   ├── test_pricing.rs         # Test calculation logic
│   └── test_pipeline.rs        # Test full pipeline
└── python/
    ├── test_api.py            # Test HTTP endpoints
    ├── test_celery.py         # Test task execution
    └── fixtures/
        ├── valid_models/      # Real STL/OBJ/STEP files
        └── sample_gcodes/     # Real G-code outputs
```

### 3.2 Test Philosophy
```python
# One test per function
def test_validate_filename_removes_path_traversal():
    assert validate_filename("../../etc/passwd") == "etc_passwd"

def test_validate_3d_file_accepts_valid_stl():
    with open("fixtures/valid.stl", "rb") as f:
        result = validate_3d_file(f.read(), ".stl")
    assert result.is_valid == True

def test_calculate_final_quote_applies_minimum():
    metadata = SlicingMetadata(time_minutes=1, filament_grams=0.5)
    quote = calculate_final_quote(metadata, "PLA", pricing_config)
    assert quote.total_cost == 5.0  # Minimum price
```

## Phase 4: Configuration & Environment (Week 4)

### 4.1 Simplified Configuration
```python
# Single settings.py
class Settings:
    # Paths
    SLICER_PATH: Path
    PROFILES_DIR: Path
    UPLOAD_DIR: Path
    
    # Pricing
    MATERIAL_PRICES: dict[str, float]
    MINIMUM_PRICE: float = 5.0
    
    # External services
    TELEGRAM_TOKEN: str
    TELEGRAM_CHAT_ID: str
    
    # No complex nested configs
```

### 4.2 Environment Variables
```bash
# example.env
SLICER_PATH=/usr/local/bin/orcaslicer
PROFILES_DIR=/app/config/slicer_profiles
TELEGRAM_TOKEN=your_token_here
TELEGRAM_CHAT_ID=your_chat_id
```

## Implementation Order

1. **Week 1**: Implement Rust functions
   - Start with modular helpers
   - Build up to `run_quote_pipeline`
   - Comprehensive Rust tests

2. **Week 2**: Simplify Python
   - Update imports to use new Rust functions
   - Simplify endpoints and tasks
   - Remove service layer

3. **Week 3**: Rewrite tests
   - One test per Rust function
   - Integration tests for pipeline
   - Remove all PyO3 mocking

4. **Week 4**: Documentation & Cleanup
   - Update CLAUDE.md
   - Clean up old code
   - Performance benchmarking

## Success Metrics

1. **Code Reduction**: ~40% fewer lines of code
2. **Test Simplicity**: Average test is <10 lines
3. **Performance**: 3x faster file validation
4. **Modularity**: No function >50 lines
5. **Clarity**: New developer can understand in <1 hour

## Risk Mitigation

1. **Keep Celery**: Handles unpredictable slicing times
2. **Incremental Migration**: Test each Rust function thoroughly
3. **Monitoring**: Add timing metrics to track performance
4. **Rollback Plan**: Git tags at each phase

## Deferred Decisions

1. **Celery Removal**: Collect metrics first, remove if 95% of jobs <10s
2. **WebSocket Updates**: Could replace polling in future
3. **Database Storage**: Currently stateless, could add if needed

This plan achieves maximum simplification while maintaining robustness and practical operation.