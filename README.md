# Monorepo Work In Progress

## Basic make commands

Run `make help` to see full list:

```shell
(agent-platform) agent-platform % make help
Usage: make [target]

Available targets:
  all                       Perform a clean build of everything
  build                     Build both wheels and PyInstaller executable
  build-exe                 Build a PyInstaller executable
  build-wheels              Build Python wheels into dist/ via uv
  check-env                 Check that all required environment variables are set in the .env file
  clean                     Remove build/dist artifacts
  coverage                  Run tests with pytest and generate coverage report
  dev-widget                Run pnpm run dev on server/examples/debug_widget
  help                      Show this help
  lint-fix                  Run ruff linting (fix violations)
  lint                      Run ruff linting (check only)
  new-empty-env             Create a new empty .env file if one doesn't exist
  run-server-exe            Run the agent server executable
  run-server                Run the agent server
  setup-keychain            Setup macOS keychain for code signing (no-op on non-macOS)
  sync                      Sync/install all packages in the monorepo
  test                      Run tests with pytest (VCR playback only)
  test-vcr-record-fresh     Run tests with pytest and record VCR cassettes
  test-vcr-record-new       Run tests with pytest and record VCR cassettes for new requests
  typecheck                 Run typechecking with pyright
  venv                      Create a new virtual environment with uv
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
