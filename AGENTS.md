# Agent Platform

This project utilizes `uv` for all Python package management and virtual environment handling. All code
should be written using `asyncio`.

## Dev environment tips

- Update pyproject.toml in the appropriate workspace ('core', 'server', 'quality').
- Run `make sync` after updating dependencies to update the local environment.
- Do not use `pip`, `pip-tools`, `poetry`, or `conda` directly for dependency management in this project.
- We use ruff for linting (`make lint`), pyright for typechecking (`make typecheck`), and ruff/prettier for formatting (`make check-format`)
- Code style/linting changes should only be made after the core functional changes have been made and approved.

## Testing instructions

- **Execute scripts:** Use `uv run --project agent_platform_server <script_name>.py` to run Python scripts within the project's virtual environment.
- **Interactive Python:** Use `uv run --project agent_platform_server python` to launch an interactive Python shell within the project's environment.
- **Testing instructions:** Run all tests using `make test-unit` or specific tests via `uv run --project agent_platform_server pytest`."
