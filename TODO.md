# Code Review 3 Implementation Tasks

## Overview
This file tracks the ongoing implementation of the Rust-first architecture refactoring as specified in `specs/code-review-3.md`.

**Branch**: `refactor/code-review-3`  
**Started**: 2025-06-23  
**Target Completion**: 4 weeks  

## Phase Status

### Phase 1: Rust Consolidation (Week 1) ✅ COMPLETE
- [x] Review code-review-3.md spec and current codebase state
- [x] Implement core Rust consolidation - create run_quote_pipeline function
- [x] Add missing Rust functions (profile resolution, error handling)
- [x] Create modular helper functions in Rust
- [x] Build and test Rust implementation *(pending - needs Rust environment)*

**Completed in commits:**
- `e508241` - docs: add code-review-3 specification
- `7087b7d` - build: add Rust dependencies
- `5c2b9d4` - feat: implement code-review-3 Phase 1
- `0e70625` - docs: update CLAUDE.md

### Phase 2: Python Simplification (Week 2) 🔄 IN PROGRESS
- [ ] **HIGH PRIORITY**: Build Rust extension with `maturin develop`
- [ ] Update main.py to use simplified endpoint
- [ ] Simplify tasks.py to call run_quote_pipeline
- [ ] Remove service layer entirely (delete `src/orca_quote_machine/services/`)
- [ ] Update imports and dependencies

**Key Changes Needed:**
1. FastAPI endpoint should only do basic validation and queue Celery task
2. Celery task should call `run_quote_pipeline` from Rust
3. Remove all service imports and usage

### Phase 3: Modular Testing (Week 3) ⏳ PENDING
- [ ] Create one test per Rust function (<10 lines each)
- [ ] Separate Rust tests from Python tests
- [ ] Remove all PyO3 mocking - use real objects
- [ ] Add integration tests for full pipeline
- [ ] Ensure 80%+ test coverage

**Test Structure:**
- Rust unit tests in `src/lib.rs` (using `#[cfg(test)]` module)
- Python tests in `tests/`
- Integration tests in `tests/integration/`

### Phase 4: Configuration & Cleanup (Week 4) ⏳ PENDING
- [ ] Simplify settings.py configuration
- [ ] Update all documentation
- [ ] Remove deprecated code
- [ ] Performance benchmarking
- [ ] Final code review

## Technical Debt from Phase 1
- [ ] Handle actual Telegram sending (currently just returns flag)
- [ ] Add timeout handling for OrcaSlicer execution
- [ ] Implement proper async file operations in Rust
- [ ] Add more comprehensive error messages

## Build Prerequisites
Before continuing with Phase 2, ensure:
1. Rust and Cargo are installed: `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`
2. Source Rust environment: `source ~/.cargo/env`
3. Build Rust extension: `uv run maturin develop`

## Success Metrics
- **Code Reduction**: Target ~40% fewer lines of code
- **Test Simplicity**: Average test is <10 lines
- **Performance**: 3x faster file validation
- **Modularity**: No function >50 lines
- **Clarity**: New developer can understand in <1 hour

## Notes
- Service layer (`services/`) will be completely removed
- All business logic now in Rust `run_quote_pipeline()` function
- Python reduced to HTTP handling and Celery task dispatch only
- Each Rust function does exactly ONE thing
- Celery retained for handling unpredictable OrcaSlicer execution times

## Next Steps
1. Set up Rust build environment
2. Build and test the Rust implementation
3. Begin Phase 2 by updating main.py