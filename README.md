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
  lint-fix                  Run ruff linting (fix violations)
  lint-fix-unsafe           Run ruff linting (fix violations)
  lint                      Run ruff linting (check only)
  new-empty-env             Create a new empty .env file if one doesn't exist
  observability-clean       Clean the observability stack and volumes.
  observability-down        Stop the observability stack.
  observability-logs        Show the logs of the observability stack.
  observability-ps          Show the status of the observability stack.
  observability-up          Start the observability stack.
  run-as-studio             Run the agent server as in Studio
  run-server-exe            Run the agent server executable
  run-server-hot-reload     Run the agent server with hot reloading (uvicorn --reload)
  run-server                Run the agent server
  sync                      Sync/install all packages in the monorepo
  test-integration          Run only integration tests
  test                      Run all tests with pytest (VCR playback only)
  test-unit                 Run only unit tests
  test-vcr-record-fresh     Run tests with pytest and record VCR cassettes
  test-vcr-record-new       Run tests with pytest and record VCR cassettes for new requests
  test-workitems-judge      Test work item judge stability by running multiple times
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
- `node / npm` (for `prettier` to work with `npx`) (Node v22 or later)
- `make` (note: on `Windows` you can install it using `Chocolatey` with `choco install make`)
- `go` (used to build the `go-wrapper`, version `1.23.6` or newer required)

## Development Guide

See [docs/development-guide.md](docs/development-guide.md) for more information on how to develop the Agent Platform.

### Development with Workroom & Agent Server (SPAR)

Both the agent server and workroom (interaction UI) are available in this repository - you can develop against both projects at the same time in a combined manner (SPAR stack). The recommended approach is with Docker, but you can run both components outside of the Docker stack with hot reloading for improved development experience.

#### Requirements

To develop the Workroom application, you must have **NodeJS** and **NPM** installed, with valid Sema4.ai authentication configured with which to install packages needed by Workroom and associated dependencies.

1. You **must** have an `~/.npmrc` file.

   _This is needed for both local and docker-based development._

   You must generate a Personal Access Token (PAT) in [GitHub settings](https://github.com/settings/tokens). The token must be granted access to at least the `read:packages` scope.

   The structure of the `~/.npmrc` file should be as follows:

   ```
   //npm.pkg.github.com/:_authToken=ghp_<snip>
   @sema4ai:registry=https://npm.pkg.github.com/
   ```

1. You need to set up authentication against GitHub Container Registry (GHCR).

   This is required to pull the **Data Server** Docker image.

   Run the following command, supplying your GitHub **username** and the **PAT** you created in the previous step (`ghp_xxx...`):

   ```
   $ docker login ghcr.io
   Username: mygithubusername
   Password: <paste your PAT here>
   Login Succeeded
   $
   ```

1. Create a `.env` file in `./workroom` by copying the example file. Run this command from the `workroom` directory:

   ```
   cp .env.example .env
   ```

   This will create a `.env` file with the default environment variable values, which you can then edit as needed.

   _Note that copying the `.env.auth.example` file will setup Workroom to use authentication._

1. Run `npm install` inside the `workroom` directory

> [!NOTE]
> The `.env` file in `./workroom` is only necessary for non-docker-based Workroom development. If using workroom via Docker, you don't need to touch these files.

#### Running SPAR Docker stack

You can run the full platform, without hot reloading, by running the following:

```shell
COMPOSE_PROFILES=spar-no-auth docker compose up --build
```

This launches the base services as well as the SPAR module, which contains both workroom and agent server.

If you want **hot reloading** for workroom, you can run the following:

_Terminal 1:_

```shell
COMPOSE_PROFILES=agent-server-no-auth docker compose up --build
```

_Terminal 2:_

```shell
cd workroom
npm run dev
```

And finally if you want to hot reload both workroom and agent server, just run the base docker stack in one terminal:

```shell
docker compose up
```

And the other hot reloading commands in separate terminals.

> [!TIP]
> Compose profiles are just like "tags". You can set one or more by either using `COMPOSE_PROFILES=one,two docker compose up` or `docker compose --profile one --profile two up`.

The following table shows the various configurations you can run:

|                            | _No Profiles_ | `agent-server-no-auth` | `spar-no-auth` |
| -------------------------- | ------------- | ---------------------- | -------------- |
| Postgres                   | ✅            | ✅                     | ✅             |
| Influx                     | ✅            | ✅                     | ✅             |
| Open Telemetry             | ✅            | ✅                     | ✅             |
| Workroom (SPAR module)     |               |                        | ✅             |
| Agent Server (SPAR module) |               | ✅                     | ✅             |

> [!TIP]
> The running agent server will be available on [`http://localhost:8000`](http://localhost:8000), and workroom on [`http://localhost:8001`](http://localhost:8001).

#### Known limitations

- Actions do not work (MCP servers do) at all: the short answer "missing router"

#### Troubleshooting

Networking and other issues:

```sh
docker compose down --remove-orphans
docker network prune
COMPOSE_PROFILES=spar-no-auth docker compose up --build --force-recreate
```

> [!TIP]
> Refer to the `compose.yml` and Dockerfile sources for what environment variables are required in each case. Since they change often, maintaining a list in the README is non-ideal.

#### Developing with JWT Local Authentication

To develop with JWT Local Authentication so you can test or work with the JWT tokens, you can use the launch configuration `Debug Agent Server (JWT Local w/ Postgres)`. This will launch the agent server with JWT Local Authentication and local Postgres. If you want to use the SPAR stack at the same time, you must update the launch configuration to change the appropriate environment variables to use the SPAR stack.

When in fully local mode, the following environment variables will be set:

- `AUTH_TYPE`: `jwt_local`
- `JWT_ALG`: `HS256`
- `JWT_AUD`: `agent_server`
- `JWT_DECODE_KEY_B64`: `dmVyeV9zZWNyZXRfa2V5` (base64 encoded `very_secret_key`)
- `JWT_ISS`: `ace`
- `POSTGRES_DB`: `agent_server_db`
- `POSTGRES_HOST`: `localhost`
- `POSTGRES_PORT`: `5432`
- `POSTGRES_USER`: `admin`
- `POSTGRES_PASSWORD`: `password`
- `SEMA4AI_AGENT_SERVER_DB_TYPE`: `postgres`

In order to switch to using SPAR, first, SPAR must be started with no profile so you can run the agent-server locally in debug mode, then you must update the following environment variables to use the SPAR stack:

- `POSTGRES_DB`: `agents`
- `POSTGRES_USER`: `agents`
- `POSTGRES_PASSWORD`: `agents`

Finally, to actually authenticate to the agent server once it's running, you need to generate a JWT token with the following fields:

- `iss`: `ace`
- `aud`: `agent_server`
- `alg`: `HS256`
- `sub`: `/tenant/{tenant_id}/user/{user_id}` (tenant ID and user ID can be whatever you want or an existing on in the database)

And you must use the key `very_secret_key` as the secret key. You can generate token using [jwtbuilder](http://jwtbuilder.jamiekurtz.com/) or you can build a script to do so for your own needs. We may in the future have a Make target for this.

> [!TIP]
> There is a SPAR profile called `agent-server-auth` but it has not been tested in some time so your mileage may vary.

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
      "url": "http://localhost:3001/sse" # http://host.docker.internal:3001/sse when running agent-server inside Docker
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

### Configuring Document Intelligence v2 Data Server

In order to use the DIv2 endpoints, you will need to configure the data connection and Reducto API key. This can be done via the workroom UI. Navigate to [Document Intelligence](http://localhost:8001/tenants/spar/documentIntelligence) and fill in the following fields:

- **Reducto API key**: this is available within the Sema4.ai 1Password vault (as of writing this README, we have been primarily using the vault item labled `PROD DocIntel v2: Sema4 API Key - Internal testing (Reducto)`)
- **Bring your own Database**: for the data server brought up as part of the SPAR stack, use the connection string: `postgresql://agents:agents@postgres:5432/data`

### Breaking Interface Changes: build failing

The SPAR UI and Backend rely on the `agent-server-interface` strictly. Changes to the interface may break the build: CI/CD checks will be `red` until the build is fixed.

#### Main reasons for the SPAR build to fail:

1. **Adding / removing a new endpoint**: endpoints exposed and allowed in SPAR backend are derived from the interface: a new `endpoint` will make the SPAR backend tests fail _until_ the endpoint is added. A single map of all exposed endpoints is defined [here](https://github.com/Sema4AI/agent-platform/blob/4e1eb1264225e69da0f8b5647b6bc18e689770cd/workroom/backend/src/api/routing.ts#L34). The new endpoint must be added to the map, alongside the permissions required.

2. **Adding or removing fields on an entity**: types used in the UI are derived from the interface. A new field addition _should_ not break the build (but may on some occasions). Removal of a field that is actively used by the UI will break the build as this is a breaking change. Update the UI to not rely on the field (if intentional) or revert the API changes and seek guidance from the UI engineers.
