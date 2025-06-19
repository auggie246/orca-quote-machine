# Format Command

Formats code and runs linting checks using ruff and mypy.

```bash
./scripts/format.sh
```

This command executes:
- Code formatting with ruff format
- Import sorting with ruff check --fix
- Type checking with mypy
- Reports any remaining lint issues