# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# 🚨 SECURITY: SECRETS & CREDENTIALS 🚨

**CRITICAL: Under NO circumstances should secrets, API keys, or credentials EVER be committed to this repository.**

## Absolute Prohibitions
- **NEVER commit `.env` files** - These contain secrets and are for local development only
- **NEVER commit any file containing API tokens, keys, or credentials**
- **NEVER use `git add .` without first reviewing what files are being staged**
- **NEVER commit files with patterns like: `*token*`, `*key*`, `*secret*`, `*credential*`**

## Required Pre-Commit Safety Checks
Before ANY git operation, Claude MUST:
1. Run `git status` and review ALL files being added
2. Verify `.env` and sensitive patterns are in `.gitignore`
3. Run `git diff --staged` to review exact content being committed
4. Scan staged content for high-entropy strings or secret patterns
5. If ANY doubt exists about file sensitivity, STOP and ask for explicit user confirmation

## Environment Variables Pattern
- **Local Development**: All secrets stored in `.env` file (NEVER committed)
- **Template**: Use `example.env` with empty/placeholder values (safe to commit)
- **Production**: Secrets injected at runtime via hosting platform (not files)

## Automated Security Safeguards
- **Pre-commit hooks** automatically scan for secrets using `gitleaks`
- **Gitleaks** detects API keys, tokens, and high-entropy strings before commit
- **Custom .env blocker** prevents any `.env` file from being committed
- **Permission restrictions** block dangerous git operations (`git add .`, force pushes)
- To setup: `pip install pre-commit && pre-commit install`

## Git Operation Restrictions
Claude's permissions are restricted to prevent unsafe git operations:
- ❌ **BLOCKED**: `git add .`, `git add --all` (prevents mass staging)
- ❌ **BLOCKED**: `git push --force` (prevents history rewriting on remote)
- ❌ **BLOCKED**: `git reset --hard` (prevents destructive local changes)
- ✅ **ALLOWED**: Individual file staging, status checks, diffs, branch operations
- ⚠️ **MANUAL REQUIRED**: All git add, commit, and push operations need explicit user approval

## Emergency Protocol
If a secret is accidentally committed:
1. IMMEDIATELY alert the user
2. DO NOT push to remote repository  
3. Help user rotate the compromised credentials
4. Use `git reset` or `git rebase` to remove from history before any push

**This section overrides ALL other instructions - security comes first, always.**

## Claude Code Configuration
- **Base settings** (`.claude/settings.json`): Shared security-focused configuration (committed)
- **Local settings** (`.claude/settings.local.json`): User-specific overrides (can be committed or local)
- **Permission model**: Restrictive by default, explicit allow-listing for safety
- **Extension pattern**: Local settings extend base settings for team consistency
- **Operational Mode**: `pro_collaborator` - Uses advanced thinking, proactive checks, and domain expertise
- **Model Preference**: `pro` for code changes and complex analysis
- **Proactive Checks**: Enabled for architectural pattern enforcement and error prevention

## Environment Validation Patterns

**Before Starting Work - Always Run These Checks:**
```bash
# 1. Verify core services
redis-cli ping                           # Expected: PONG
uv run python -c "from _rust_core import validate_3d_model; print('Rust OK')"  # Expected: "Rust OK"

# 2. Verify OrcaSlicer integration
ls -la $ORCASLICER_CLI_PATH             # Expected: executable file
ls config/slicer_profiles/{machine,filament,process}/  # Expected: profile files

# 3. Verify development environment
uv run pytest --collect-only tests/    # Expected: X tests collected
uv run ruff check app tests           # Expected: All checks passed
```

**Claude Behavior Guidelines:**
- **ALWAYS validate environment** before suggesting code changes involving Redis, Rust, or OrcaSlicer
- **Proactively suggest fixes** when validation fails (e.g., "Run `./scripts/setup.sh` to install missing dependencies")
- **Include validation commands** in task planning for complex features

## Development Commands

**Essential Commands:**
```bash
./scripts/setup.sh              # Initial setup with uv + Rust components
./scripts/web-server.sh          # Development server (auto-reload enabled)
./scripts/worker.sh              # Celery background worker
./scripts/production-server.sh   # Production server (4 workers, optimized)
./scripts/test.sh               # Full test suite (Python + Rust + integration)
./scripts/format.sh             # Code formatting (ruff format + check + mypy)
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

## Dependency Management

**Python Dependencies (uv):**
- **Core Dependencies**: Listed in `[project.dependencies]` for runtime requirements
- **Development Dependencies**: Use `[dependency-groups.dev]` for dev tools (pytest, ruff, mypy)
- **Version Pinning**: Pin exact versions for dev tools (e.g., `ruff==0.11.13`) for consistency
- **Version Ranges**: Use compatible ranges for runtime deps (e.g., `fastapi>=0.104.0`)

**Dependency Commands:**
```bash
uv sync --group dev              # Install all dependencies including dev group
uv add package_name              # Add new runtime dependency
uv add --group dev package_name  # Add new dev dependency
uv lock                          # Update lock file with latest compatible versions
uv sync --frozen                 # Install exact versions from lock file (CI/prod)
```

**Rust Dependencies (Cargo.toml):**
- **PyO3 Integration**: Rust dependencies managed separately via `src/Cargo.toml`
- **Rebuild Required**: Run `maturin develop` after Rust dependency changes
- **Version Compatibility**: Ensure PyO3 version matches Python version requirements

**Update Strategy:**
- **Regular Updates**: Monthly dependency updates with full test suite validation
- **Security Updates**: Immediate updates for security vulnerabilities
- **Breaking Changes**: Test thoroughly with integration tests before updating major versions
- **Lock File**: Commit `uv.lock` to ensure reproducible builds across environments

**Multi-Language Coordination:**
- **Python-Rust Boundary**: Changes to PyO3 bindings require rebuilding both sides
- **Development Workflow**: Always run `maturin develop` after pulling Rust changes
- **CI/CD**: Build pipeline handles both Python and Rust dependency installation

## Repository Structure & Architecture

For detailed information about the repository structure, system architecture, components, and implementation patterns, refer to:
`ai_docs/orca-quote-machine-repomix.xml`

This XML file contains:
- Complete directory structure
- All source code files
- System architecture details
- Component relationships
- Implementation patterns
- Configuration examples
- Security requirements

The XML file is automatically generated and provides a comprehensive view of the entire codebase in a format optimized for AI analysis.

## Code Quality & Linting

**Ruff Configuration (`pyproject.toml`):**
- **Rule Selection**: Current ruleset balances strictness with FastAPI/async patterns
- **Selected Rules**: `E/F` (core), `W` (warnings), `I` (imports), `UP` (modernize), `B` (bugs), `C4` (comprehensions), `SIM` (simplify), `ANN` (annotations), `ASYNC` (async patterns), `TID` (imports)
- **Ignored Rules**: `B008` (FastAPI Depends pattern), `ANN401` (allows typing.Any)

**Configuration Management:**
- **Version Pinning**: Ruff version pinned to `0.11.13` in dependencies for consistency
- **Rule Updates**: When updating ruff versions, check for deprecated rules with `uv run ruff check --show-settings`
- **Deprecated Rules**: Remove deprecated rules from config immediately (e.g., `ANN101` removed in ruff 0.5+)

**Quality Enforcement:**
- **Pre-commit**: Always run `./scripts/format.sh` before committing
- **CI Integration**: All linting must pass in GitHub Actions
- **Type Checking**: MyPy configured for strict type checking with `disallow_untyped_defs`

**Rule Modification Process:**
1. Test rule changes locally with `uv run ruff check app tests`
2. Verify formatting compatibility with `uv run ruff format app tests`
3. Update CI if adding new rule categories
4. Document rationale for ignored rules in pyproject.toml comments

## Code Review Checklist

**CRITICAL - Must Fix Before Merge:**
- [ ] **BLOCKING_IO_IN_ASYNC_ROUTE**: No blocking I/O in FastAPI async routes (use Celery or `run_in_executor`)
- [ ] **UNHANDLED_RUST_PANIC**: All Rust function calls wrapped in try/except blocks
- [ ] **MISSING_FILE_CLEANUP**: File operations have cleanup in `finally` blocks
- [ ] **ASYNC_SYNC_BOUNDARY_VIOLATION**: Proper async/sync coordination patterns

**HIGH PRIORITY - Address Before Production:**
- [ ] **INCORRECT_ORCASLICER_CALL**: OrcaSlicer CLI arguments validated against documentation
- [ ] **MISSING_INPUT_VALIDATION**: All user inputs validated through Pydantic models
- [ ] **INSECURE_FILENAME_HANDLING**: `secure_filename()` applied to user-provided names
- [ ] **MISSING_TIMEOUT_PROTECTION**: External calls have reasonable timeout limits
- [ ] **INCORRECT_PYO3_INTEGRATION**: PyO3 classes use `#[derive(Debug, Clone)]` only (no Serde), avoid explicit `#[new]`, use factory functions

**MEDIUM PRIORITY - Code Quality:**
- [ ] **MISSING_CELERY_IDEMPOTENCY**: Tasks can be safely re-executed
- [ ] **INCONSISTENT_ERROR_HANDLING**: Uniform error patterns across similar operations
- [ ] **MISSING_STRUCTURED_LOGGING**: Context included in log messages for async operations
- [ ] **PERFORMANCE_ANTIPATTERNS**: No unnecessary blocking operations or resource leaks

**Automated Checks:**
- All ruff linting rules pass
- MyPy type checking without errors  
- Test coverage maintained above 80%
- No security vulnerabilities in dependencies

## Common Issues and Patterns

**Memory Management:**
- Rust validation uses `BufReader` for streaming (never load entire files)
- Python file operations use chunked reading
- OrcaSlicer timeout protection (default 5 minutes)

**Error Handling Patterns:**
- Rust components have graceful fallback when unavailable
- Telegram notifications have error capture for debugging
- File cleanup always happens in finally blocks
- Use structured logging with context for async operations
- Wrap external CLI calls with timeout and proper error capture

**Debugging Async/Celery Issues:**
```bash
# Check Celery worker status and active tasks
uv run celery -A app.tasks inspect active
uv run celery -A app.tasks inspect stats

# Debug worker with verbose logging
uv run celery -A app.tasks worker --loglevel=debug --concurrency=1

# Monitor task execution in real-time
uv run celery -A app.tasks events

# Clear failed tasks from queue
uv run celery -A app.tasks purge
```

**Common OrcaSlicer Problems:**
- **CLI Not Found**: Verify `ORCASLICER_CLI_PATH` in environment
- **Profile Missing**: Check `SLICER_PROFILES_DIR` contains machine/, filament/, process/ subdirs
- **Timeout Issues**: Increase timeout for large/complex models
- **Permission Errors**: Ensure OrcaSlicer executable has proper permissions
- **Memory Issues**: Monitor system memory during slicing of large files

**Redis Connection Troubleshooting:**
```bash
# Test Redis connectivity
redis-cli ping                    # Should return PONG
redis-cli info replication       # Check Redis server info

# Monitor Redis operations
redis-cli monitor                 # Real-time command monitoring
redis-cli --latency              # Check connection latency

# Check Celery broker connection
uv run python -c "from app.tasks import app; print(app.control.inspect().stats())"
```

**File Upload Error Patterns:**
- **Large File Timeout**: Increase nginx `client_max_body_size` and timeout settings
- **Invalid File Type**: Check file validation in Rust layer logs
- **Path Traversal**: Verify `secure_filename()` is applied to all user inputs
- **Disk Space**: Monitor available disk space in upload directory
- **Async Upload Issues**: Check for proper await patterns in FastAPI routes

**Performance Debugging:**
```bash
# Profile async operations
uv run python -m cProfile -s cumulative app/main.py

# Monitor Celery task performance
uv run celery -A app.tasks inspect active_queues
uv run celery -A app.tasks inspect reserved

# Check system resources during processing
htop                              # CPU and memory usage
iostat -x 1                      # Disk I/O monitoring
```

**Testing Philosophy:**
- **"1 test per function, test code logic only"** - Focus on behavior, not configuration values
- **Test code logic**, not data validation already handled by Pydantic
- **Simple assertions** - Test return types, structure, and key behaviors
- **Avoid over-complication** - Don't test every possible input combination
- **Real objects over mocks for PyO3** - Use actual Rust functions to create objects in tests
- **Mock external services only** - Keep tests fast and reliable by mocking I/O, not objects

**PyO3 Testing Patterns - CRITICAL:**
- **NEVER mock PyO3 objects** - Always use real Rust functions like `parse_slicer_output()`
- **Use factory functions in tests** - Create real objects via Rust functions
- **Test with actual Rust integration** - Verify the Python-Rust boundary works correctly
- **Mock external I/O only** - Mock network calls, file systems, CLI processes - not Rust objects

**What TO Test:**
- Function return types and structure (`isinstance(result, CostBreakdown)`)
- Key business logic and calculations using real Rust objects
- Error handling and edge cases with real object creation
- Integration between Python services and Rust components
- Custom validation logic (not Pydantic validators)

**What NOT to Test:**
- Configuration values (Pydantic handles validation)
- External service responses (mock them)
- Different materials/inputs if logic is identical
- Framework behavior (FastAPI, Celery internals)
- Library functionality (requests, aiofiles, etc.)
- **PyO3 object constructors directly** - Use factory functions instead

**Test Structure Examples:**
```python
# GOOD: Real Rust objects via factory functions
async def create_real_slicing_result() -> SlicingResult:
    with tempfile.TemporaryDirectory() as temp_dir:
        gcode_file = os.path.join(temp_dir, 'test.gcode')
        with open(gcode_file, 'w') as f:  # noqa: ASYNC230  # Test file creation
            f.write('; estimated printing time: 2h 0m\n; filament used: 100.0g\n')
        return await parse_slicer_output(temp_dir)  # Real Rust function

def test_calculate_quote():
    slicing_result = asyncio.run(create_real_slicing_result())  # Real object
    result = pricing_service.calculate_quote(slicing_result, MaterialType.PLA)
    assert isinstance(result, CostBreakdown)  # Real Rust object
    assert result.total_cost > 0

# BAD: Mocking PyO3 objects
def test_calculate_quote_bad():
    mock_result = MagicMock()  # Don't do this for PyO3 objects
    mock_result.print_time_minutes = 120
    # This doesn't test the real Rust-Python integration

# BAD: Testing configuration values
def test_pla_price_is_25_dollars():
    assert settings.material_prices["PLA"] == 25.0  # Pydantic already validates this
```

**Implementation Strategy:**
- **Always use real Rust objects** - Create via functions like `parse_slicer_output()`, `calculate_quote_rust()`
- **Mock OrcaSlicer CLI process** - Avoid actual slicing but use real object creation
- **Test Rust validation with real files** - Use sample STL/OBJ/STEP files with actual validation
- **Integration tests verify real pipeline** - Real objects flowing through Python services
- **Use pytest fixtures for environment** - Redis, Celery, file isolation - not object creation
- **Test error scenarios with real objects** - File corruption, parsing failures with actual Rust

**Real Object Creation Patterns:**
```python
# Create real SlicingResult via Rust parser
async def create_slicing_result() -> SlicingResult:
    return await parse_slicer_output(temp_dir_with_gcode)

# Create real CostBreakdown via Rust pricing
def create_cost_breakdown() -> CostBreakdown:
    return calculate_quote_rust(120, 25.5, "PLA", 25.0, 0.5, 1.1, 5.0)

# Create real CleanupStats via Rust cleanup
def create_cleanup_stats() -> CleanupStats:
    return cleanup_old_files_rust(upload_dir, 24)
```

**Refactoring Legacy Tests:**
- **Replace PyO3 mocks with real objects** - Use factory functions from Rust
- **Simplify value checking** - Focus on behavior, not configuration
- **Reduce mock complexity** - Only mock external I/O, never Rust objects
- **Keep real object creation** - Tests should verify actual Rust-Python integration

## Task Management & Planning

**When to Use TodoWrite/TodoRead:**
- **Complex multi-step tasks** (3+ distinct steps or operations)
- **Non-trivial implementation work** requiring careful planning
- **User provides multiple tasks** (numbered lists, comma-separated requests)
- **After receiving new complex instructions** to capture all requirements
- **When starting work on a task** (mark as in_progress BEFORE beginning)
- **After completing a task** (mark as completed and add discovered follow-ups)

**Task Structure Best Practices:**
- **One todo per function/component** being implemented or fixed
- **Specific, actionable items** with clear completion criteria
- **Break complex tasks** into smaller, manageable steps
- **Priority levels**: high (blocking), medium (important), low (nice-to-have)
- **Only ONE task in_progress** at any time for focus

**Task Management Workflow:**
1. **Read existing todos** with TodoRead to understand current state
2. **Plan the work** by creating specific, actionable todos
3. **Mark in_progress** before starting work on a task
4. **Update status** as work progresses (complete immediately after finishing)
5. **Add new tasks** discovered during implementation
6. **Clean up completed** tasks periodically

**When NOT to Use:**
- Single, straightforward tasks (can be completed in 1-2 trivial steps)
- Purely conversational or informational requests
- Tasks that provide no organizational benefit

This system demonstrates thoroughness and helps users track progress on complex requests.

## Technical Debt Management

**Debt Tracking Standards:**

**TODO Comment Format (for trackable technical debt):**
```python
# TODO-DEBT: [CATEGORY] Brief description - Priority: HIGH/MEDIUM/LOW
# Context: Why this exists and what should replace it
# Example: TODO-DEBT: [MYPY] Remove union-attr ignore when Pydantic BaseSettings typing improves - Priority: LOW
```

**Debt Categories:**
- **[MYPY]**: Type checking improvements
- **[ASYNC]**: Async/sync boundary issues
- **[PERF]**: Performance optimizations
- **[RUST]**: Rust integration improvements
- **[SECURITY]**: Security hardening
- **[ARCH]**: Architectural improvements

**Debt Resolution Workflow:**
1. **Inventory Phase**: Use `grep -r "TODO-DEBT" app/ tests/` to list all tracked debt
2. **Prioritization**: HIGH = blocks production, MEDIUM = affects maintainability, LOW = future improvements
3. **Resolution**: Address in order: HIGH → MEDIUM → LOW within same category
4. **Validation**: Use `mcp__zen__codereview` for complex debt resolution

**Monthly Debt Review Process:**
```bash
# Generate debt report
grep -r "TODO-DEBT.*Priority: HIGH" app/ tests/
grep -r "TODO-DEBT.*Priority: MEDIUM" app/ tests/
grep -r "TODO-DEBT.*Priority: LOW" app/ tests/

# Target: Resolve 1-2 HIGH priority items per month
# Target: Address 1 MEDIUM priority item per month when no HIGH items exist
```

**Integration with Type Ignores:**
```python
# Current: self.profiles_dir = self.settings.slicer_profiles.base_dir  # type: ignore[union-attr]
# Improved:
# TODO-DEBT: [MYPY] Remove union-attr ignore when Pydantic BaseSettings typing improves - Priority: LOW
# Context: Settings.slicer_profiles is Optional but always set in validation, Pydantic typing unclear
self.profiles_dir = self.settings.slicer_profiles.base_dir  # type: ignore[union-attr]
```

## Problem Escalation & Tool Strategy

**Escalation Decision Tree:**

**Level 1 - Direct Implementation (No special tools needed)**
- Single file edits with clear requirements
- Bug fixes with obvious causes
- Adding simple validation or configuration
- Standard CRUD operations

**Level 2 - Use Standard Analysis Tools**
- Multi-file changes requiring codebase understanding
- Debugging with unclear error messages
- Performance optimization needs
- Integration between 2-3 components
- **Tools**: Grep, Read, TodoWrite for planning

**Level 3 - Use Advanced Analysis (mcp__zen__* tools)**
- Complex architectural decisions
- Root cause analysis for mysterious issues
- Security analysis and code review
- Large refactoring or system redesign
- Integration across 4+ components

**Specific Tool Usage Patterns:**
```bash
# Before making architectural changes
mcp__zen__thinkdeep    # Deep analysis of design decisions
mcp__zen__chat         # Validate approach with thinking partner

# Before committing any changes  
mcp__zen__precommit    # MANDATORY - validate all git operations

# When debugging complex issues
mcp__zen__debug        # Systematic root cause analysis with file evidence

# When adding major features
mcp__zen__codereview   # Comprehensive code quality analysis
```

**Claude Decision Guidelines:**
- **Automatically escalate** to Level 3 when encountering: security issues, async/sync boundary problems, performance bottlenecks
- **Use thinking_mode: 'high'** for all architectural decisions in this complex multi-language system
- **Always include relevant files** when using advanced tools (don't limit context)

## Advanced Analysis Tools

**Tool Selection Criteria:**
- **mcp__zen__thinkdeep**: Deep architectural decisions, complex problem analysis, validation of approaches
- **mcp__zen__codereview**: Comprehensive code analysis, security audits, architectural validation
- **mcp__zen__debug**: Root cause analysis, tracing complex issues, error investigation
- **mcp__zen__analyze**: General file/code exploration, dependency analysis, pattern detection
- **mcp__zen__chat**: Brainstorming, second opinions, collaborative thinking, concept explanations
- **mcp__zen__precommit**: Pre-commit validation, change analysis, safety checks

**Thinking Mode Guidelines:**
- **minimal**: Quick checks, simple confirmations
- **low**: Standard debugging, basic analysis
- **medium**: Normal problem solving, code review
- **high**: Complex architectural decisions, security analysis (default for this project)
- **max**: Critical systems, extremely complex challenges

**When to Use Advanced Tools:**
- **Complex Problems**: Use thinkdeep for multi-faceted architectural challenges
- **Security Concerns**: Always use precommit before any git operations
- **Code Quality**: Use codereview for comprehensive analysis of new features
- **Debugging Issues**: Use debug tool with comprehensive file context (include logs, stack traces)
- **Brainstorming**: Use chat for exploring alternatives and validating approaches
- **Validation**: Use analyze for understanding existing code structure

**Tool Combinations:**
- **Planning Phase**: chat → thinkdeep → analyze (explore → validate → understand)
- **Implementation**: codereview → debug → precommit (quality → troubleshoot → validate)
- **Problem Solving**: debug → thinkdeep → chat (investigate → analyze → explore solutions)

**File Context Strategy:**
- **Include liberally**: These tools can handle large amounts of context
- **Related files**: Include all files that might be relevant to the analysis
- **Diagnostic data**: Include logs, stack traces, error outputs for debugging
- **Configuration files**: Include settings and config when analyzing system behavior

## Claude Behavior Guidelines

**Response Quality Standards:**
- Use `pro` model and `high` thinking mode for complex architectural decisions
- Always provide contextual explanations specific to this 3D printing system
- Include relevant file paths and line numbers when referencing code
- Proactively check for architectural antipatterns before suggesting solutions

**Code Generation Patterns:**
- Follow established architectural patterns (API Task Offload, Rust Calculation, CLI Integration)
- Include proper error handling and resource cleanup in all generated code
- Generate complete, testable implementations rather than partial snippets
- Validate external tool usage (OrcaSlicer CLI) against current documentation

**Proactive Error Detection:**
- Check for blocking I/O in async contexts before suggesting FastAPI routes
- Ensure Rust integration follows PyO3 safety patterns
- Verify file handling includes proper cleanup mechanisms
- Validate Celery task patterns for idempotency and error recovery

**Domain Expertise Application:**
- Understand 3D printing workflow: STL → Slicing → G-code → Analysis
- Know OrcaSlicer CLI patterns and common failure modes
- Recognize material-specific processing requirements (PLA, PETG, ASA)
- Apply security best practices for file upload and processing systems