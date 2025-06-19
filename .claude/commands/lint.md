# Lint Command

Checks code for linting errors and type issues without fixing them.

```bash
uv run ruff check app tests && uv run mypy app
```

This command:
- Runs ruff linting checks on app and tests directories
- Runs mypy type checking on the app directory
- Reports issues without auto-fixing
- Use `/format` to fix auto-fixable issues