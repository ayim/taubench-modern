# SPAR Mono-repository

This mono-repository contains the code for both the backend and the frontend of SPAR. This repository is called Moonraker.

## TypeScript & React Guidelines

**For any TypeScript/React implementation in the workroom codebase, invoke the `typescript-guidelines` skill.** This skill contains all coding standards, patterns, and review guidelines for the frontend and backend TypeScript code.

Primary components:

- Frontend: @workroom/frontend
- Backend: @workroom/backend (SPAR proxy/router)

## Python Guidelines

**For any Python implementation in the SPAR codebase, invoke the `python-guidelines` skill.** This skill contains all coding standards, patterns, and review guidelines for the Python code. We also call this agent-platform.

Primary components:

- Agent-platform: @server, @core, @architectures

## Layout

### SPAR

"SPAR" is the combination of `agent-server` and `workroom` (frontend and backend)

Consult the `compose.yml` docker configuration for an example as to how this project is used.

The SPAR docker file (`Dockerfile.spar`) builds both the agent-server and workroom components in a single container. The container, once running, maintains the agent-server as a mostly internal service, with the workroom back-end and front-end handling public-facing requests. The workroom backend (express server) proxies requests through to the agent server based upon a strict set of allowed routes and permissions.

## Project Interaction

- This project utilizes `uv` for all Python package management and virtual environment handling. All code
  should be written using `asyncio`.

### Dev environment tips

- Update pyproject.toml in the appropriate workspace ('core', 'server', 'quality').
- Run `make sync` after updating dependencies to update the local environment.
- Run `make update-interface` after modifying the API between server and frontend to update API type definitions.
- Do not use `pip`, `pip-tools`, `poetry`, or `conda` directly for dependency management in this project.
- Do not use the system default `python` executable directly.
- We use ruff for linting (`make lint`), pyright for typechecking (`make typecheck`), and ruff/prettier for formatting (`make check-format`)
- Code style/linting changes should only be made after the core functional changes have been made and approved.
- Use `agent-browser` skill to test any changes you make to the frontend. The frontend can be assumed to be running at http://localhost:8001 and to require no authentication. Run the browser in headless mode by default.

### Testing instructions

- **Execute scripts:** Use `uv run --project agent_platform_server <script_name>.py` to run Python scripts within the project's virtual environment.
- **Interactive Python:** Use `uv run --project agent_platform_server python` to launch an interactive Python shell within the project's environment.
- **Testing instructions:** Run all tests using `make test-unit` or specific tests via `uv run --project agent_platform_server pytest`."

- **IMPORTANT**: Tests MUST always be run from the root of the `moonraker` monorepo
- **IMPORTANT**: NEVER run `uv` or `make` from a subdirectory (running `uv` from `server/` or `core/` is NOT supported and commands will fail).

### Python imports coding standard

Whenever possible, add imports inside of methods instead of importing in the top-level.
Alternatively, if the tokens of the imported module need to be used in the top-level just for type-checking, add
the import inside of a `typing.TYPE_CHECKING` block and use top-level references as strings.
Note: add the imports inside of the method at the start of the method (right after the docstring if there's one).
Note: if the token must be resolved in the top-level to be used in runtime (for FastAPI, Pydantic), top-level imports are still required.

### GitHub Actions & Workflows

When writing shell scripts in GitHub Actions workflows:

- **Variable naming**: Use lowercase for script-local variables. UPPERCASE is reserved exclusively for exported/environment variables.
- **Variable assignment**: Always quote the value assigned to a variable: `my_var="$(command)"` not `my_var=$(command)`
- **Variable interpolation**: Always use curly braces to delimit the variable name: `"${my_var}"` not `"$my_var"`
- **Command substitution**: Use `$()` syntax and quote the result: `result="$(some_command)"`

Example:

```bash
# Good
version="$(uv run python -c "print('1.0.0')")"
tag_name="agent-server-v${version}"
echo "Creating tag: ${tag_name}"

# Bad
VERSION=$(uv run python -c "print('1.0.0')")
TAG_NAME="agent-server-v$VERSION"
echo "Creating tag: $TAG_NAME"
```

## Development Logs

Development logs are written to timestamped files in tmp/ at the repo root.

### Local Development

| Service          | Command                        | Log pattern                                  |
| ---------------- | ------------------------------ | -------------------------------------------- |
| Agent Server     | `make run-server-hot-reload`   | `tmp/agent-server-YYYY-MM-DD-HHMMSS.log`     |
| Workroom Backend | `npm run dev` (from workroom/) | `tmp/workroom-backend-YYYY-MM-DD-HHMMSS.log` |

### Docker Compose

When running via `docker compose`, logs are also written to tmp/:

| Service          | Log pattern                                  |
| ---------------- | -------------------------------------------- |
| Agent Server     | `tmp/agent-server-YYYY-MM-DD-HHMMSS.log`     |
| Workroom Backend | `tmp/workroom-backend-YYYY-MM-DD-HHMMSS.log` |

### Viewing Logs

**Important: when the logic is not working and you see errors or if the user mention errors, proactively look at the logs**

```sh
# Agent Server logs (most recent)
tail -f $(ls -t tmp/agent-server-*.log 2>/dev/null | head -1)

# Workroom Backend logs (most recent)
tail -f $(ls -t tmp/workroom-backend-*.log 2>/dev/null | head -1)
```

#### Spar UI / Workroom frontend logs

Use the `agent-browser` skill to view logs and interact with SPAR UI (see Dev environment tips above).

_The frontend is hot-reloaded - look for "[vite] (client) hmr update" in workroom-backend logs._
