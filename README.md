# Moonraker Multi-project Repository

The latest version of Moonraker is available at [https://moonraker.sema4ai.dev/tenants/main](https://moonraker.sema4ai.dev/tenants/main).

It is automatically deployed ~5 to 10min after a PR is merged to `main` thanks to this [workflow](.github/workflows/spar-build.yaml)

[Moonraker SSO-enabled](./docs/spar/oidc.md)

## Overview

This repository contains the source code for the Agent Platform, a multi-project repository that contains the source code for the Agent Server, core, default architectures, and related SDKs and projects.

## Basic make commands

Run `make help` to see full list:

```shell
Usage: make [target]

Available targets:
  all                       Perform a clean build of everything
  aws                       AWS operations: make aws deploy|status|destroy|logs|troubleshoot
  build-exe                 Build a PyInstaller executable
  build-wheels              Build Python wheels into dist/ via uv
  check-env                 Check that all required environment variables are set in the .env file
  check-format              Run formatting check with ruff
  check-pr                  Run common PR checks (format, lint, typecheck, unit tests)
  clean                     Remove build/dist artifacts
  coverage                  Run tests with pytest and generate coverage report
  force-clean               Force remove build/dist artifacts (use with caution)
  format                    Run formatting with ruff and prettier (node/npm must be in the path for npx to work).
  help                      Show this help
  lint-fix-unsafe           Run ruff linting (fix violations)
  lint-fix                  Run ruff linting (fix violations)
  lint                      Run ruff linting (check only)
  new-empty-env             Create a new empty .env file if one does not exist
  notebooks-check           Check if notebooks have outputs that need stripping (dry-run)
  notebooks-clean           Strip outputs from all Jupyter notebooks
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
  update-interface          Regenerates Agent Server interface files from OpenAPI spec
  test-integration          Run only integration tests
  test-unit                 Run only unit tests
  test-vcr-record-fresh     Run tests with pytest and record VCR cassettes
  test-vcr-record-new       Run tests with pytest and record VCR cassettes for new requests
  test-workitems-judge      Test work item judge stability by running multiple times (NUM_RUNS=20, TEST_PATTERN=test_work_item_judge_with_recorded_threads)
  test                      Run all tests with pytest (VCR playback only)
  typecheck                 Run typechecking with pyright
  venv                      Create a new virtual environment with uv
```

## Manual Setup Commands

Good to know these for more advanced config or fixing issues.

### Prerequisites

1. **MySQL Client Libraries** (required for MySQL data connections):
   - See the [MySQL Client Setup Guide](docs/mysql-client-setup.md) for detailed instructions
   - Quick start for macOS:
     ```bash
     brew install mysql-client pkg-config
     export PATH="$(brew --prefix)/opt/mysql-client/bin:$PATH"
     export PKG_CONFIG_PATH="$(brew --prefix)/opt/mysql-client/lib/pkgconfig"
     # Add to ~/.zshrc to make permanent
     ```

Working with `uv`:

1. You need `uv` installed - see: <https://docs.astral.sh/uv/getting-started/installation/>
2. Running `uv run` commands will automatically create and use a virtual environment as needed
3. `uv sync --all-extras --all-groups --all-packages` to install the whole monorepo
4. `uv run agent-server` to run the server
5. `uv run pytest core/tests server/tests` to run tests (`brew install postgresql` before trying to run tests)
6. `uv run ruff check` to lint everything

Examples of private agent creation payloads that mirror our current tests and helpers live in [docs/create-agent-examples.md](docs/create-agent-examples.md).

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

## Dependencies

The following dependencies need to be installed manually:

- `uv` (which is used to manage the Python environment), see: <https://docs.astral.sh/uv/getting-started/installation/>
- `node / npm` (for `prettier` to work with `npx`) (Node v22 or later)
- `make` (note: on `Windows` you can install it using `Chocolatey` with `choco install make`)
- `go` (used to build the `go-wrapper`, version `1.23.6` or newer required)

## Development Guide

See [docs/development-guide.md](docs/development-guide.md) for more information on how to develop the Agent Server.

### Development with Workroom & Agent Server (SPAR)

See the [docs/spar/development.md](SPAR development guide).

### Bypassing workroom backend to call agent-server directly locally

By design, all requests go through the workroom backend which handles authentication and proxies allowed routes to the agent-server. For local testing, it's often more convenient to call the agent-server directly.

The agent-server expects a Bearer token in the form of an unsigned JWT (`alg: "none"`) with a `sub` claim. In production, this same token is generated by the [workroom backend](workroom/backend/src/utils/signing.ts) as a way to carry authenticated user information to the agent-server (see more details about the security model [here](docs/spar/security.md)). You can generate one manually and make requests as follows:

```sh
TOKEN=$(node -e "const b=s=>Buffer.from(s).toString('base64url');console.log(b('{\"alg\":\"none\",\"typ\":\"JWT\"}')+'.'+b('{\"sub\":\"local-dev-user\"}')+'.')")

curl http://localhost:8000/api/v2/agents/ \
  -H "Authorization: Bearer $TOKEN"
```

The `sub` value can be any string - it's used as the user identity. The full API documentation is available on the running server at [http://localhost:8000/docs](http://localhost:8000/docs).

### Configuring Document Intelligence v2 Data Server

In order to use the DIv2 endpoints, you will need to configure the data connection and Reducto API key. This can be done via the workroom UI. Navigate to [Document Intelligence](http://localhost:8001/tenants/spar/configuration/documentIntelligence) and fill in the following fields:

- **Reducto API key**: this is available within the Sema4.ai 1Password vault (as of writing this README, we have been primarily using the vault item labled `PROD DocIntel v2: Sema4 API Key - Internal testing (Reducto)`)

### Developing with Document Intelligence v2

Document Intelligence is now part of the monorepo workspace. Changes to `document-intelligence/` will be automatically picked up by uv when you run `make sync`.

#### Hot-reloading SPAR integration tests

Our pytest fixtures (for example `agent_server_client_with_doc_int`) allow overriding the Document Intelligence configuration via environment variables. This is especially useful when running the Agent Server outside of Docker with hot reload enabled.

Set whichever of these exports you need before running `uv run pytest -v -m spar`:

| Variable                            | Purpose                                                                                                  | Default                                           |
| ----------------------------------- | -------------------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| `SPAR_DATA_SERVER_HOST`             | Data Server host.                                                                                        | `data-server`                                     |
| `SPAR_DATA_SERVER_HTTP_URL`         | Full HTTP URL to the Data Server API. Overrides host/port when set.                                      | `None`                                            |
| `SPAR_DATA_SERVER_HTTP_HOST`        | Data Server HTTP host (if `*_HTTP_URL` is not provided, otherwise falls back to `SPAR_DATA_SERVER_HOST`) | `data-server`                                     |
| `SPAR_DATA_SERVER_HTTP_PORT`        | Data Server HTTP port.                                                                                   | `47334`                                           |
| `SPAR_DATA_SERVER_MYSQL_HOST`       | Data Server MySQL host (falls back to `SPAR_DATA_SERVER_HOST` when set).                                 | `data-server`                                     |
| `SPAR_DATA_SERVER_MYSQL_PORT`       | Data Server MySQL port.                                                                                  | `47335`                                           |
| `SPAR_DATA_SERVER_USERNAME`         | Data Server username.                                                                                    | `sema4ai`                                         |
| `SPAR_DATA_SERVER_PASSWORD`         | Data Server password.                                                                                    | `sema4ai`                                         |
| `SPAR_DATA_CONNECTION_POSTGRES_URL` | Postgres connection URL.                                                                                 | `postgresql://agents:agents@postgres:5432/agents` |
| `SPAR_DATA_CONNECTION_HOST`         | Postgres host backing Document Intelligence. (falls back to `SPAR_DATA_CONNECTION_POSTGRES_URL`)         | `postgres`                                        |
| `SPAR_DATA_CONNECTION_PORT`         | Postgres port. (falls back to `SPAR_DATA_CONNECTION_POSTGRES_URL`)                                       | `5432`                                            |
| `SPAR_DATA_CONNECTION_USER`         | Postgres username. (falls back to `SPAR_DATA_CONNECTION_POSTGRES_URL`)                                   | `agents`                                          |
| `SPAR_DATA_CONNECTION_PASSWORD`     | Postgres password. (falls back to `SPAR_DATA_CONNECTION_POSTGRES_URL`)                                   | `agents`                                          |
| `SPAR_DATA_CONNECTION_DATABASE`     | Postgres database name. (falls back to `SPAR_DATA_CONNECTION_POSTGRES_URL`)                              | `agents`                                          |
| `SPAR_DATA_CONNECTION_ENGINE`       | Engine reported to Agent Server.                                                                         | `postgres`                                        |
| `SPAR_DATA_CONNECTION_POSTGRES_URL` | Postgres connection URL.                                                                                 | `postgresql://agents:agents@postgres:5432/agents` |

Example for running SPAR integration tests against locally running agent server and base SPAR compose stack with no profiles set (assuming `.env` file is set up correctly with valid API keys):

```bash
SPAR_DATA_SERVER_HOST=localhost uv run pytest -v -m spar
```

If the configuration still fails (for example because the data server is unreachable), the fixtures will automatically `pytest.skip(...)` the SPAR tests and print guidance so the rest of your selected suite can continue.

### Breaking Interface Changes: build failing

The SPAR UI and Backend rely on the `agent-server-interface` strictly. Changes to the interface may break the build: CI/CD checks will be `red` until the build is fixed.

#### Main reasons for the SPAR build to fail:

1. **Adding / removing a new endpoint**: endpoints exposed and allowed in SPAR backend are derived from the interface: a new `endpoint` will make the SPAR backend tests fail _until_ the endpoint is added. A single map of all exposed endpoints is defined [here](https://github.com/Sema4AI/agent-platform/blob/4e1eb1264225e69da0f8b5647b6bc18e689770cd/workroom/backend/src/api/routing.ts#L34). The new endpoint must be added to the map, alongside the permissions required.

2. **Adding or removing fields on an entity**: types used in the UI are derived from the interface. A new field addition _should_ not break the build (but may on some occasions). Removal of a field that is actively used by the UI will break the build as this is a breaking change. Update the UI to not rely on the field (if intentional) or revert the API changes and seek guidance from the UI engineers.
