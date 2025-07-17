# Agent Platform Multi-project Repository

## Overview

This repository contains the source code for the Agent Platform, a multi-project repository that contains the source code for the Agent Server, core, default architectures, and related SDKs and projects.

## Basic make commands

Run `make help` to see full list:

```shell
Usage: make [target]

Available targets:
  all                       Perform a clean build of everything
  build-exe                 Build a PyInstaller executable
  build-wheels              Build Python wheels into dist/ via uv
  check-env                 Check that all required environment variables are set in the .env file
  check-format              Run formatting check with ruff
  check-pr                  Run common PR checks (format, lint, typecheck, unit tests)
  clean                     Remove build/dist artifacts
  coverage                  Run tests with pytest and generate coverage report
  dev-widget                Run pnpm run dev on server/examples/debug_widget
  format                    Run formatting with ruff and prettier (node/npm must be in the path for npx to work).
  help                      Show this help
  lint-fix-unsafe           Run ruff linting (fix violations)
  lint-fix                  Run ruff linting (fix violations)
  lint                      Run ruff linting (check only)
  new-empty-env             Create a new empty .env file if one doesn't exist
  observability-clean       Clean the observability stack and volumes.
  observability-down        Stop the observability stack.
  observability-logs        Show the logs of the observability stack.
  observability-ps          Show the status of the observability stack.
  observability-up          Start the observability stack.
  run-server-exe            Run the agent server executable
  run-server                Run the agent server
  sync                      Sync/install all packages in the monorepo
  test-integration          Run only integration tests
  test-unit                 Run only unit tests
  test-vcr-record-fresh     Run tests with pytest and record VCR cassettes
  test-vcr-record-new       Run tests with pytest and record VCR cassettes for new requests
  test                      Run all tests with pytest (VCR playback only)
  typecheck                 Run typechecking with pyright
  venv                      Create a new virtual environment with uv
```

## Manual Setup Commands

Good to know these for more advanced config or fixing issues.

Working with `uv`:

1. You need `uv` installed - see: <https://docs.astral.sh/uv/getting-started/installation/>
2. Running `uv run` commands will automatically create and use a virtual environment as needed
3. `uv sync --all-extras --all-groups --all-packages` to install the whole monorepo
4. `uv run agent-server` to run the server
5. `uv run pytest core/tests server/tests` to run tests (`brew install postgresql` before trying to run tests)
6. `uv run ruff check` to lint everything

## ⚠️ Important: UV Workspace Behavior

**Always run `uv` commands from the workspace root directory.** Running commands from subdirectories (like `server/` or `core/`) will cause issues.

### The Problem

When you run `uv` commands from a subdirectory that contains a `pyproject.toml` file, uv treats it as a standalone project instead of part of the workspace. This causes:

- Creation of a local `.venv` in the subdirectory
- Dependency resolution failures (can't find workspace dependencies like `agent-platform-core`)
- Isolation from the monorepo's shared environment

### Solutions

1. **Use `make` commands (Recommended)**: `make sync`, `make test`, `make lint`, etc.
2. **Run from workspace root**: Always `cd` to the repo root before running `uv` commands
3. **Use `--package` flag from root**: `uv run --package agent_platform_server python -m agent_platform.server`

### Examples

```bash
# ✅ Good - from workspace root
uv run pytest server/tests/
uv run --package agent_platform_server python -m agent_platform.server
uv sync --all-packages

# ✅ Good - using make commands (from anywhere)
make test
make sync
make run-server

# ❌ Bad - from subdirectory without --project
cd server/
uv run pytest tests/  # This will fail!
```

## Running example notebooks

To run the example notebooks:

1. Set up your environment:

   - Run `make new-empty-env` to create a new .env file if you don't have one
   - Run `make check-env` to verify all required environment variables are set
   - Navigate to the `server/examples` directory in your IDE
   - Select a Jupyter kernel that matches the Python environment from `uv sync`

2. Start the server:

   - Ensure the server is running on port 8000
   - If using a different port, modify the notebook to use your port

3. Run the notebook:

   - Execute the first 3 cells in the notebook
   - Run the cell that imports the `DebugChatWidget` class to load the widget

4. Optional: Modify agent configuration:

   - Look for configuration settings in cells before the widget import
   - Make your desired changes to the agent's behavior

5. Optional: Run other cells to get the full thread and delete the agent you created.

> **Important:** Generally, you should not commit your notebook changes to the repo unless you are fundamentally changing how the notebook works or adding documentation or functionality.

## Dependencies

The following dependencies need to be installed manually:

- `uv` (which is used to manage the Python environment), see: <https://docs.astral.sh/uv/getting-started/installation/>
- `node / npm` (for `prettier` to work with `npx`)
- `make` (note: on `Windows` you can install it using `Chocolatey` with `choco install make`)
- `go` (used to build the `go-wrapper`, version `1.23.6` or newer required)

## Development Guide

See [docs/development-guide.md](docs/development-guide.md) for more information on how to develop the Agent Platform.

### Developing with Workroom

##### Requirements

_To develop with the Workroom application, you must have NPM setup locally in that you have valid authentication with which to use to install packages needed by Workroom and associated dependencies. You should have a `~/.npmrc` file with the following structure:_

_This is needed for both local and docker-based development_

```
//npm.pkg.github.com/:_authToken=ghp_<snip>
@sema4ai:registry=https://npm.pkg.github.com/
```

#### Running the full stack with hot reloading

```sh
docker compose --profile hot up --build

# Agent Server available on http://localhost:8000
# Work Room available on http://localhost:8001
```

#### Known limitations

- Actions do not work (MCP servers do) at all: the short answer "missing router"

---

You can run a full-stack workroom and agent-server system using `docker` and `docker compose`. This stack comes in two flavours:

1. Hot reloading (agent-server and workroom built and watched for changes)
2. Default (everything built for you at startup - "finished product")

#### Hot reload mode: currently work room only

```sh
COMPOSE_PROFILES=hot docker compose up --build

# or:
docker compose --profile hot up --build
```

#### Default mode: no hot-reload

```sh
COMPOSE_PROFILES=default docker compose up --build

# or:
docker compose --profile default up --build
```

Navigate to [`http://localhost:8001`](http://localhost:8001) to open the workroom instance (agent-server is available at [`http://localhost:8002`](http://localhost:8002))

### Creating agents

_Make sure to at least replace the Open API LLM key `REPLACE_WITH_VALID_KEY` to have a working agent_

_Note: The documentation for the agent API is exposed on the running server [over here](http://localhost:8000/docs#/agents/create_agent_agents__post)_

```sh
curl --request POST -L \
  --url http://localhost:8000/api/v2/agents \
  --header 'content-type: application/json' \
  --data '{
  "mode": "conversational",
  "name": "New Agent",
  "version": "1.0.0",
  "description": "This is a test agent created using the CURL command in the README.\nThis agent uses the OpenAI PlatformClient.",
  "runbook": "# Objective\nYou are a helpful assistant.",
  "platform_configs": [
    {
      "kind": "openai",
      "openai_api_key": "REPLACE_WITH_VALID_KEY"
    }
  ],
  "action_packages": [],
  "mcp_servers": [
    {
      "name": "placeholder-mcp-server",
      "url": "http://localhost:3001/sse"
    }
  ],
  "agent_architecture": {
    "name": "agent_platform.architectures.default",
    "version": "1.0.0"
  },
  "observability_configs": [
    {
      "type": "langsmith",
      "api_url": "https://api.smith.langchain.com",
      "api_key": "REPLACE_WITH_VALID_KEY",
      "settings": {
        "project_name": "example"
      }
    }
  ],
  "question_groups": [],
  "extra": {
    "test": "test"
  }
}'
```

### Troubleshooting

Networking and other issues

```sh
docker compose down --remove-orphans
docker network prune
docker compose --profile hot up --build --force-recreate
```
