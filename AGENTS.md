# Agent Platform Mono-repository

This mono-repository contains the code for both the backend and the frontend of the agent platform.

Primary components:

- Frontend: @workroom/frontend, @workroom/spar-ui
- Backend:
  - Agent-server: @server, @core
  - SPAR proxy/router: @workroom/backend

Additional components:

- MCP runtime: @workroom/mcp-runtime - used to provision action servers (as MCP servers) in SPAR

## Layout

### SPAR

This repository builds an artifact called "SPAR", which is a combination of the Python environment (agent-server) and NodeJS environment (workroom). Refer to the primary components. Consult the `compose.yml` docker configuration for an example as to how this project is used.

The SPAR docker file (`Dockerfile.spar`) builds both the agent-server and workroom components in a single container. The container, once running, maintains the agent-server as a mostly internal service, with the workroom back-end and front-end handling public-facing requests. The workroom backend (express server) proxies requests through to the agent server based upon a strict set of allowed routes and permissions.

## Project Interaction

- This project utilizes `uv` for all Python package management and virtual environment handling. All code
  should be written using `asyncio`.

### Dev environment tips

- Update pyproject.toml in the appropriate workspace ('core', 'server', 'quality').
- Run `make sync` after updating dependencies to update the local environment.
- Do not use `pip`, `pip-tools`, `poetry`, or `conda` directly for dependency management in this project.
- We use ruff for linting (`make lint`), pyright for typechecking (`make typecheck`), and ruff/prettier for formatting (`make check-format`)
- Code style/linting changes should only be made after the core functional changes have been made and approved.

### Testing instructions

- **Execute scripts:** Use `uv run --project agent_platform_server <script_name>.py` to run Python scripts within the project's virtual environment.
- **Interactive Python:** Use `uv run --project agent_platform_server python` to launch an interactive Python shell within the project's environment.
- **Testing instructions:** Run all tests using `make test-unit` or specific tests via `uv run --project agent_platform_server pytest`."

- **IMPORTANT**: Tests MUST always be run from the root of the `agent-platform` monorepo
- **IMPORTANT**: NEVER run `uv` or `make` from a subdirectory (running `uv` from `server/` or `core/` is NOT supported and commands will fail).

### Python imports coding standard

Whenever possible, add imports inside of methods instead of importing in the top-level.
Alternatively, if the tokens of the imported module need to be used in the top-level just for type-checking, add
the import inside of a `typing.TYPE_CHECKING` block and use top-level references as strings.
Note: add the imports inside of the method at the start of the method (right after the docstring if there's one).
Note: if the token must be resolved in the top-level to be used in runtime (for FastAPI, Pydantic), top-level imports are still required.
