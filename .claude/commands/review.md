# Review Command

Performs architecture-aware code review using domain-specific patterns.

This command checks for:
- Async/sync boundary violations
- Proper Celery task patterns
- Rust integration safety
- OrcaSlicer CLI usage
- File handling and cleanup
- Security and performance issues

## Usage
```
/review [file_or_directory] [focus_area]
```

## Focus Areas
- `async` - Async/await patterns and performance
- `celery` - Task design and idempotency
- `rust` - PyO3 integration and safety
- `security` - File handling and input validation
- `performance` - Resource usage and optimization
- `all` - Complete review (default)

Uses advanced thinking mode for thorough analysis of architectural patterns.