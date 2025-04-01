# Monorepo Work In Progress

## Basic make commands

Run `make help` to see full list:

```shell
(agent-platform) agent-platform % make help
Usage: make [target]

Available targets:
  all                   Default to 'build'
  build-exe             Build a PyInstaller executable
  build-wheels          Build Python wheels into dist/ via uv
  build                 Build both wheels and PyInstaller executable
  clean                 Remove build/dist artifacts
  dev-widget            Run pnpm run dev on server/examples/debug_widget
  help                  Show this help
  lint                  Run ruff linting
  run-server-exe        Run the agent server executable
  run-server            Run the agent server via uv run -m
  setup-keychain        Setup macOS keychain for code signing (no-op on non-macOS)
  sync                  Sync/install all packages in the monorepo
  test                  Run tests with pytest
  typecheck             Run typechecking with pyright
  venv                  Create a new virtual environment with uv
```

## Manual Setup Commands

Good to know these for more advanced config or fixing issues.

Initial setup with `uv`:

1. You need `uv` installed
2. `uv venv --python=python3.12` to create a Python 3.12 venv in the root directory
3. `source .venv/bin/activate` to activate the venv
4. `uv sync --all-extras --all-groups --all-packages` to install the whole monorepo
5. `uv run -m agent_platform.server` to run the server
6. `uv run pytest core/ server/` to run tests
7. `uv run ruff check` to lint everything

Blissfully simple.

(To run notebook, you need a terminal in `./server/examples/debug_widget` and to have `pnpm` installed; then `pnpm i` and `pnpm run dev` in that terminal to build the widget UX.)

**Note/TODO:** we have some dep that doesn't like python > 3.12 (at least on OSX).
