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
- `node / npm` (for `prettier` to work with `npx`)
- `make` (note: on `Windows` you can install it using `Chocolatey` with `choco install make`)
- `go` (used to build the `go-wrapper`, version `1.23.6` or newer required)

## Development Guide

See [docs/development-guide.md](docs/development-guide.md) for more information on how to develop the Agent Platform.

### Developing with Workroom

#### Requirements

To develop with the Workroom application, you must have **NPM** setup locally, with valid Sema4.ai authentication configured with which to use to install packages needed by Workroom and associated dependencies:

1. You should have a `~/.npmrc` file with the following structure:

   _This is needed for both local and docker-based development_

   ```
   //npm.pkg.github.com/:_authToken=ghp_<snip>
   @sema4ai:registry=https://npm.pkg.github.com/
   ```

2. Create a `.env` file in `./workroom` by copying the example file. Run this command from the `workroom` directory:

   ```
   cp .env.example .env
   ```

   This will create a `.env` file with the default environment variable values, which you can then edit as needed.

   _Note that copying the `.env.auth.example` file will setup Workroom to use authentication._

3. Run `npm install` inside the `workroom` directory

> [!NOTE]
> The `.env` file in `./workroom` is only necessary for non-docker-based Workroom development. If using workroom via Docker, you don't need to touch these files.

> [!TIP]
> If developing primarily against Workroom, it is recommended to install Docker (either via OrbStack or Docker desktop).

#### Workroom Hot Reloading & Dockerized Stack

1. Run Workroom without Docker _and_ with hot reloading:

```shell
npm run dev
```

2. Run the rest of the stack with docker:

```shell
# Runs agent-server, postgres, OTEL in Docker
COMPOSE_PROFILES=agent-server-no-auth docker compose up
# Runs postgres, OTEL in Docker
docker compose up
```

#### [Advanced Docker Stack Configuration] Workroom / Agent Server with Postgres Database

The root `compose.yml` configuration configures a wide variety of Docker services and system configurations. It's a great development target if you're working with Workroom.

This docker compose setup makes strong use of compose profiles, which allow for switching services on and off to allow for multiple ways of working with it.

> [!TIP]
> Compose profiles are just like "tags". You can set one or more by either using `COMPOSE_PROFILES=one,two docker compose up` or `docker compose --profile one --profile two up`.

The following table shows the various configurations you can run:

|                                 | _No Profiles_ | `agent-server-no-auth` | `agent-server-auth` | `workroom-production` |
| ------------------------------- | ------------- | ---------------------- | ------------------- | --------------------- |
| Postgres                        | ✅            | ✅                     | ✅                  | ✅                    |
| Influx                          | ✅            | ✅                     | ✅                  | ✅                    |
| Open Telemetry                  | ✅            | ✅                     | ✅                  | ✅                    |
| Agent Server, no authentication |               | ✅                     |                     |                       |
| Agent server, authenticated     |               |                        | ✅                  |                       |
| Workroom, production config     |               |                        |                     | ✅                    |

So, for example, if you wanted to run a _non-authenticated agent server_ with the _workroom in production mode_, you'd execute the following:

```shell
COMPOSE_PROFILES=agent-server-no-auth,workroom-production docker compose up --build
```

Or if you were using Workroom with hot reloading:

```shell
# In terminal 1:
COMPOSE_PROFILES=agent-server-no-auth docker compose up

# In terminal 2:
cd workroom && npm run dev
```

> [!TIP]
> The running agent server will be available on [`http://localhost:8000`](http://localhost:8000), and workroom on [`http://localhost:8001`](http://localhost:8001).

#### Known limitations

- Actions do not work (MCP servers do) at all: the short answer "missing router"

#### Troubleshooting

Networking and other issues:

```sh
docker compose down --remove-orphans
docker network prune
COMPOSE_PROFILES=agent-server-no-auth docker compose up --build --force-recreate
```

---

You can run a full-stack workroom and agent-server system using `docker` and `docker compose`. This stack comes in several flavours:

1.  Hot reloading (agent-server and workroom built and watched for changes)
2.  Production (everything built for you at startup - "finished product")
3.  Agent server with forced-auth (docker)

### Single Container Deployment (SPAR)

#### Quick Start

```bash
# Pull and run both services with minimal configuration
docker run -p 8000:8000 -p 8001:8001 \
  -e DEPLOYMENT_TYPE=spar \
  -e SEMA4AI_AGENT_SERVER_OTEL_ENABLED=true \
  -e SEMA4AI_AGENT_SERVER_ENABLE_WORKITEMS=true \
  -e AUTH_MODE=none \
  024848458368.dkr.ecr.us-east-1.amazonaws.com/manual/ace/spar:latest
```

After starting, access:

- **Agent Server API**: http://localhost:8000
- **Workroom UI**: http://localhost:8001

#### Configuration Examples

**With PostgreSQL Database:**

```bash
docker run -p 8000:8000 -p 8001:8001 \
  -e DEPLOYMENT_TYPE=spar \
  -e SEMA4AI_AGENT_SERVER_OTEL_ENABLED=true \
  -e SEMA4AI_AGENT_SERVER_ENABLE_WORKITEMS=true \
  -e POSTGRES_HOST=your-db-host.com \
  -e POSTGRES_USER=myuser \
  -e POSTGRES_PASSWORD=mypassword \
  024848458368.dkr.ecr.us-east-1.amazonaws.com/manual/ace/spar:latest
```

**With Agent Server JWT Authentication:**

```bash
docker run -p 8000:8000 -p 8001:8001 \
  -e DEPLOYMENT_TYPE=spar \
  -e SEMA4AI_AGENT_SERVER_OTEL_ENABLED=true \
  -e SEMA4AI_AGENT_SERVER_ENABLE_WORKITEMS=true \
  -e AUTH_MODE=none \
  -e AUTH_TYPE=jwt_local \
  -e JWT_DECODE_KEY_B64=your_base64_jwt_key \
  -e JWT_ALG=ES256 \
  -e JWT_AUD=agent_server \
  -e JWT_ISS=spar \
  024848458368.dkr.ecr.us-east-1.amazonaws.com/manual/ace/spar:latest
```

**With Snowflake Authentication (Workroom):**

```bash
docker run -p 8000:8000 -p 8001:8001 \
  -e DEPLOYMENT_TYPE=spar \
  -e SEMA4AI_AGENT_SERVER_OTEL_ENABLED=true \
  -e SEMA4AI_AGENT_SERVER_ENABLE_WORKITEMS=true \
  -e AUTH_MODE=snowflake \
  -e JWT_PRIVATE_KEY_B64=your_base64_jwt_key \
  024848458368.dkr.ecr.us-east-1.amazonaws.com/manual/ace/spar:latest
```

**Run Individual Services:**

```bash
# Workroom only (requires external agent-server)
docker run -p 8001:8001 \
  -e DISABLED_SERVICE=agent-server \
  -e DEPLOYMENT_TYPE=spar \
  -e AUTH_MODE=none \
  -e AGENT_SERVER_URL=http://your-agent-server.com \
  024848458368.dkr.ecr.us-east-1.amazonaws.com/manual/ace/spar:latest

# Agent-server only
docker run -p 8000:8000 \
  -e DISABLED_SERVICE=workroom \
  -e DEPLOYMENT_TYPE=spar \
  -e SEMA4AI_AGENT_SERVER_OTEL_ENABLED=true \
  -e SEMA4AI_AGENT_SERVER_ENABLE_WORKITEMS=true \
  024848458368.dkr.ecr.us-east-1.amazonaws.com/manual/ace/spar:latest
```

#### Key Environment Variables

| Variable                                | Description                                        | Default        |
| --------------------------------------- | -------------------------------------------------- | -------------- |
| `DEPLOYMENT_TYPE`                       | Must be set to `spar`                              | -              |
| `SEMA4AI_AGENT_SERVER_OTEL_ENABLED`     | Enable telemetry                                   | -              |
| `SEMA4AI_AGENT_SERVER_ENABLE_WORKITEMS` | Enable work items                                  | -              |
| `AUTH_TYPE`                             | Agent server auth type (`jwt_local`)               | -              |
| `JWT_DECODE_KEY_B64`                    | JWT decode key (base64, required for JWT)          | -              |
| `JWT_ALG`                               | JWT algorithm                                      | `ES256`        |
| `JWT_AUD`                               | JWT audience                                       | `agent_server` |
| `JWT_ISS`                               | JWT issuer                                         | `spar`         |
| `AUTH_MODE`                             | Workroom auth mode (`none`, `snowflake`, `google`) | `none`         |
| `JWT_PRIVATE_KEY_B64`                   | Workroom JWT key (for snowflake/google auth)       | -              |
| `DISABLED_SERVICE`                      | Disable `agent-server` or `workroom`               | -              |
| `PORT`                                  | Agent server port                                  | `8000`         |
| `WORKROOM_PORT`                         | Workroom port                                      | `8001`         |

See the image in ECR: `024848458368.dkr.ecr.us-east-1.amazonaws.com/manual/ace/spar:latest`

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

## 🚀 GCP Deployment

The Agent Platform includes a comprehensive Google Cloud Platform deployment system supporting multi-developer environments, security controls, and flexible deployment profiles.

### Quick Start

```bash
make gcp setup      # Initial setup (interactive menu)
make gcp deploy     # Deploy your personal instance
make gcp status     # Check deployment status
make gcp iap        # Manage access control
```

### Deployment Profiles

The system supports three deployment profiles:

#### 1️⃣ Personal Isolated (Recommended)

- **Services**: `agent-server-{your-username}`, `workroom-{your-username}`
- **Database**: `agent-postgres-{your-username}` (your own data)
- **Security**: IAP enabled, you control access
- **Best for**: Development, testing, personal use

#### 2️⃣ Personal Shared Database

- **Services**: `agent-server-{your-username}`, `workroom-{your-username}`
- **Database**: `agent-postgres` (shared team data)
- **Best for**: Accessing team data with your own endpoints

#### 3️⃣ Team Production (Admin Only)

- **Services**: `agent-server`, `workroom` (shared endpoints)
- **Database**: `agent-postgres` (shared team data)
- **Best for**: Production demos, shared team environment

### Available Commands

| Command                  | Purpose                          | Notes                                             |
| ------------------------ | -------------------------------- | ------------------------------------------------- |
| `make gcp setup`         | Initial GCP environment setup    | Interactive menu, auto-detects missing components |
| `make gcp deploy`        | Deploy services to Cloud Run     | Interactive menu with deployment profiles         |
| `make gcp status`        | Check deployment status & health | Shows URLs, health, logs                          |
| `make gcp teardown`      | Clean up GCP resources           | Interactive menu, respects permissions            |
| `make gcp add-developer` | Add developers to project        | Admin only, grants necessary permissions          |
| `make gcp iap`           | Manage IAP access control        | Control who can access your services              |

### Multi-Developer Support

- **Automatic Namespacing**: Your services are named `agent-server-{username}`, `workroom-{username}`
- **Isolation**: Each developer has complete control over their instances
- **Access Control**: You manage who can access your services via Identity-Aware Proxy (IAP)
- **Cost Efficient**: Personal instances ~$0.40/month when idle

### Identity-Aware Proxy (IAP)

Use `make gcp iap` to manage access to your services:

- **Add Access**: Give colleagues or your domain access to your instances
- **Remove Access**: Revoke access when needed
- **Domain Support**: `@company.com` gives access to entire Google Workspace domain
- **Group Support**: Use Google Groups for team access
- **Security**: All access is authenticated through Google identity

### Prerequisites

1. **Google Cloud SDK**: Install `gcloud` CLI
2. **Authentication**: `gcloud auth login`
3. **Project Setup**: `gcloud config set project YOUR_PROJECT_ID`
4. **Docker**: Required for building container images

### Advanced Usage

For advanced usage beyond the `make` commands, see the individual scripts in `scripts/gcp/`:

```bash
# Get detailed help for any script
./scripts/gcp/setup.sh --help
./scripts/gcp/deploy.sh --help
./scripts/gcp/manage-my-iap.sh --help
```

### Environment Variables

| Variable         | Description               | Default        |
| ---------------- | ------------------------- | -------------- |
| `REGION`         | GCP region for deployment | `europe-west1` |
| `GCLOUD_PROJECT` | GCP project ID            | Auto-detected  |
