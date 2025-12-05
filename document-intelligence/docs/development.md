# Development Guide

## Requirements

- Python 3.12
- uv 0.8 or later
- invoke 2.2.0 or later (optional, for task automation)

## Setup

```bash
cd document-intelligence
uv sync --group dev
```

## Development Commands

### Using invoke (optional)

`inv -l` to list available tasks:

- `inv install` : Get dependencies
  - `inv install --update` : Update lock file (CVE updates)
- `inv build` : Build the wheel
- `inv test` : Run tests
- `inv lint` : Run linting
- `inv typecheck` : Run type checking
- `inv pretty` : Auto-format code
- `inv set-version a.b.c` : Update the library version numbers
- `inv check-all` : Run all checks

### Using uv directly

```bash
# Run tests
uv run pytest -v

# Run linting
uv run ruff check sema4ai_docint tests

# Run formatting
uv run ruff format sema4ai_docint tests

# Run type checking
uv run pyright

# Run pre-commit checks
uv run python pre-commit.py
```

## Changelog

Add changes to `docs/CHANGELOG.md` under the `Unreleased` section as you develop.

## Publishing

1. Update `docs/CHANGELOG.md`
2. `inv set-version a.b.c`: Updates the library version numbers and changelog
3. `inv make-release` : Create and push a release tag
4. The CI workflow will automatically build and publish to PyPI when the tag is pushed

### Manual Release (alternative)

```bash
# Create tag manually
git tag sema4ai-docint-X.Y.Z
git push origin sema4ai-docint-X.Y.Z
```

The GitHub Actions workflow at `.github/workflows/docint-release.yml` handles PyPI publishing.
