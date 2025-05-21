SHELL := /bin/bash

# --------------------------------------------------------------------
# OS Detection
# --------------------------------------------------------------------
IS_WINDOWS := $(shell uname -s | grep -q "MINGW\|MSYS\|CYGWIN\|Windows" && echo true || echo false)
IS_LINUX   := $(shell uname -s | grep -q "Linux" && echo true || echo false)
IS_MACOS   := $(shell test "$$(uname -s)" = "Darwin" && echo true || echo false)

# --------------------------------------------------------------------
# Default variables for building
# You can override on the command line, e.g.:
#   make build-exe DEBUG=true CI=true
# --------------------------------------------------------------------
DEBUG     ?= false
CI        ?= false
EXE_NAME  ?= agent-server
DIST_PATH ?= dist

# Update the EXE_NAME if we're on Windows
ifeq ($(IS_WINDOWS),true)
# Only add .exe suffix if it doesn't already end with .exe
ifeq ($(suffix $(EXE_NAME)),.exe)
# Already has .exe suffix, do nothing
else
EXE_NAME := $(EXE_NAME).exe
endif
endif

# Create exe path based on provided vars
EXE_PATH := $(DIST_PATH)/$(EXE_NAME)

# --------------------------------------------------------------------
# Tools/paths
# --------------------------------------------------------------------
# CI environment variables, should be set by GitHub Actions
ifeq ($(IS_WINDOWS),true)
RUNNER_TEMP      ?= $(shell echo %TEMP%)
else
RUNNER_TEMP      ?= /tmp
endif


# --------------------------------------------------------------------
# Help
# --------------------------------------------------------------------
help:  ## Show this help
	@echo "Usage: make [target]"
	@echo
	@echo "Available targets:"
	@grep -E '^[a-zA-Z0-9_-]+:.*?##' $(MAKEFILE_LIST) \
	 | sort \
	 | awk 'BEGIN {FS = ":.*?##"}; {printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2}'

# --------------------------------------------------------------------
# Setup & Install
# --------------------------------------------------------------------
venv:  ## Create a new virtual environment with uv
	@if [ -n "$$VIRTUAL_ENV" ]; then \
		echo "Already in virtual environment: $$VIRTUAL_ENV"; \
	else \
		echo "Creating new virtual environment..."; \
		uv venv --python=python3.12; \
	fi

sync:  ## Sync/install all packages in the monorepo
	uv sync --all-extras --all-groups --all-packages $(if $(filter true,$(CI)),--locked,)


# --------------------------------------------------------------------
# Building: Wheels & PyInstaller
# --------------------------------------------------------------------
build-wheels: sync ## Build Python wheels into dist/ via uv
	@echo "Building wheels..."
	uv build --out-dir $(DIST_PATH) --package agent_platform_core
	uv build --out-dir $(DIST_PATH) --package agent_platform_architectures_default
	uv build --out-dir $(DIST_PATH) --package agent_platform_server

build-exe: sync  ## Build a PyInstaller executable
	@echo "Building PyInstaller/Go wrapper executable..."
	uv run python scripts/build_exe.py build-executable --go-wrapper --ci

build: clean build-wheels build-exe
	@echo "Build complete!"

# --------------------------------------------------------------------
# Debug UX Widget
# --------------------------------------------------------------------
dev-widget:  ## Run pnpm run dev on server/examples/debug_widget
	@# First, make sure we have pnpm installed
	which pnpm || npm install -g pnpm
	@# Save current directory and change to widget directory
	pushd server/examples/debug_widget && \
	pnpm install && \
	pnpm run dev; \
	popd
	
# --------------------------------------------------------------------
# Run & Test
# --------------------------------------------------------------------
run-server:  ## Run the agent server
	@echo "Running server from agent_platform.server..."
	uv run -m agent_platform.server

run-server-exe:  ## Run the agent server executable
	@if [ ! -f dist/$(EXE_NAME) ]; then \
		echo "Executable not found in dist/"; \
		echo "Please build the executable first with 'make build-exe'"; \
		exit 1; \
	fi
	@echo "Running server from dist/..."
	./dist/$(EXE_NAME)

otel-collector:  ## Run the OTEL collector for viewing telemetry data
	@echo "Starting OTEL collector..."
	uv run -m agent_platform.server.otel_collector

langsmith-collector:  ## Run the LangSmith collector for viewing LangChain traces
	@echo "Starting LangSmith collector..."
	uv run -m agent_platform.server.langsmith_collector

test:  check-env-or-no-env ## Run all tests with pytest (VCR playback only)
	VCR_RECORD=none uv run pytest

test-unit:  ## Run only unit tests
ifeq ($(CI),true)
ifeq ($(IS_LINUX),true)
	VCR_RECORD=none uv run pytest -v -m "not integration"
else
	VCR_RECORD=none uv run pytest -v -m "not integration and not postgresql"
endif
else
	VCR_RECORD=none uv run pytest -v -m "not integration"
endif

test-integration:  check-env-or-no-env ## Run only integration tests
ifeq ($(CI),true)
ifeq ($(IS_LINUX),true)
	VCR_RECORD=none uv run pytest -v -m "integration"
else
	VCR_RECORD=none uv run pytest -v -m "integration and not postgresql"
endif
else
	VCR_RECORD=none uv run pytest -v -m "integration"
endif

test-vcr-record-new:  check-env ## Run tests with pytest and record VCR cassettes for new requests
	@NUM_EXISTING_CASSETTES=$$(find core/tests/fixtures/vcr_cassettes/ -type f | wc -l); \
	echo "Found $$NUM_EXISTING_CASSETTES existing cassettes!"; \
	echo "Running tests and recording new VCR cassettes..."; \
	VCR_RECORD=new_episodes uv run pytest -v ; \
	NUM_NEW_CASSETTES=$$(find core/tests/fixtures/vcr_cassettes/ -type f | wc -l); \
	echo "Recorded $$(( NUM_NEW_CASSETTES - NUM_EXISTING_CASSETTES )) new cassettes!"; \
	echo "Total cassettes: $$NUM_NEW_CASSETTES"

test-vcr-record-fresh:  check-env ## Run tests with pytest and record VCR cassettes
	@echo "Cleaning VCR cassettes..."
	@rm -rf core/tests/fixtures/vcr_cassettes/*
	@rm -rf server/tests/fixtures/vcr_cassettes/*
	@echo "Running tests and recording fresh VCR cassettes..."
	VCR_RECORD=all uv run pytest -v
	@NUM_NEW_CASSETTES=$$(find core/tests/fixtures/vcr_cassettes/ -type f | wc -l); \
	echo "Recorded $$NUM_NEW_CASSETTES cassettes!"

coverage:  ## Run tests with pytest and generate coverage report
	uv run coverage run -m pytest
	uv run coverage report
	uv run coverage html

check-pr:  ## Run common PR checks (format, lint, typecheck, unit tests)
	@echo "Running PR checks..."
	$(MAKE) check-format
	$(MAKE) lint
	$(MAKE) typecheck
	$(MAKE) test-unit
	$(MAKE) check-changes
	@echo "✅ All PR checks passed!"

lint:  ## Run ruff linting (check only)
	uv run ruff check

lint-fix:  ## Run ruff linting (fix violations)
	uv run ruff check --fix

typecheck:  ## Run typechecking with pyright
	uv run pyright

format:  ## Run formatting with ruff and prettier (node/npm must be in the path for npx to work).
	uv run ruff format
	npx prettier@3.5.3 . --write

check-format:  ## Run formatting check with ruff
	uv run ruff format --check
	npx prettier@3.5.3 . --check

change:  ## Run the change script
	uv run scripts/changes.py create-change

check-changes:  ## Run the check-changes part of the change script
	uv run scripts/changes.py check-changes --project ALL --error-on-missing

draft-changes-server:  ## Run the build-changes part of the change script in draft mode for the server project
	uv run scripts/changes.py build-changes --project server --draft

# --------------------------------------------------------------------
# Environment Validation
# --------------------------------------------------------------------
check-env-or-no-env:
	@if [ -f .env ]; then \
		echo "Found .env file, checking environment variables..."; \
		$(MAKE) check-env; \
	else \
		echo "No .env file found, skipping environment checks."; \
		echo "This is fine for targets like make test-unit and run-server, which don't require env vars."; \
		echo "If you want to record fresh VCR cassettes, env vars are required."; \
		echo "Run make new-empty-env to create a new .env file with all required variables set to empty strings."; \
	fi

check-env:  ## Check that all required environment variables are set in the .env file
	@if [ ! -f .env ]; then \
		echo "❌ .env file not found!"; \
		exit 1; \
	fi
	@echo "Checking that all required environment variables are set in .env file..."
	@( \
		set -a; \
		. ./.env; \
		set +a; \
		echo "Checking variables needed for OpenAI Model Platform Client..."; \
		if [ -z "$$OPENAI_API_KEY" ]; then \
			echo "❌ OPENAI_API_KEY is not set"; \
			exit 1; \
		fi; \
		echo "  ✅ All OpenAI variables are set!"; \
		\
		echo "Checking variables needed for Bedrock Model Platform Client..."; \
		if [ -z "$$AWS_ACCESS_KEY_ID" ]; then \
			echo "❌ AWS_ACCESS_KEY_ID is not set"; \
			exit 1; \
		fi; \
		if [ -z "$$AWS_SECRET_ACCESS_KEY" ]; then \
			echo "❌ AWS_SECRET_ACCESS_KEY is not set"; \
			exit 1; \
		fi; \
		if [ -z "$$AWS_DEFAULT_REGION" ]; then \
			echo "❌ AWS_DEFAULT_REGION is not set"; \
			exit 1; \
		fi; \
		echo "  ✅ All Bedrock variables are set!"; \
		echo "Checking variables for Groq Model Platform Client..."; \
		if [ -z "$$GROQ_API_KEY" ]; then \
			echo "❌ GROQ_API_KEY is not set"; \
			exit 1; \
		fi; \
		echo "Checking for Snowflake configuration..."; \
		if [ -f ~/.sema4ai/sf-auth.json ]; then \
			echo "  ✅ Snowflake linking file exists, no environment variables needed!"; \
		else \
			echo "  ℹ️ Linking file not found, checking for Snowflake credentials..."; \
			if [ -z "$$SNOWFLAKE_USERNAME" ]; then \
				echo "❌ SNOWFLAKE_USERNAME is not set"; \
				exit 1; \
			fi; \
			if [ -z "$$SNOWFLAKE_PASSWORD" ]; then \
				echo "❌ SNOWFLAKE_PASSWORD is not set"; \
				exit 1; \
			fi; \
			if [ -z "$$SNOWFLAKE_ACCOUNT" ]; then \
				echo "❌ SNOWFLAKE_ACCOUNT is not set"; \
				exit 1; \
			fi; \
			if [ -z "$$SNOWFLAKE_ROLE" ]; then \
				echo "❌ SNOWFLAKE_ROLE is not set"; \
				exit 1; \
			fi; \
			echo "    ✅ All Snowflake variables are set!"; \
		fi; \
		\
		echo "✅ Environment validation complete - all required credentials are available."; \
	)

new-empty-env:  ## Create a new empty .env file if one doesn't exist
	@if [ ! -f .env ]; then \
		echo "Creating new empty .env file..."; \
		touch .env; \
		echo "OPENAI_API_KEY=" >> .env; \
		echo "GROQ_API_KEY=" >> .env; \
		echo "AWS_ACCESS_KEY_ID=" >> .env; \
		echo "AWS_SECRET_ACCESS_KEY=" >> .env; \
		echo "AWS_DEFAULT_REGION=" >> .env; \
		echo "SNOWFLAKE_USERNAME=" >> .env; \
		echo "SNOWFLAKE_PASSWORD=" >> .env; \
		echo "SNOWFLAKE_ACCOUNT=" >> .env; \
		echo "SNOWFLAKE_ROLE=" >> .env; \
		echo "New empty .env file created!"; \
	else \
		echo "❌ .env file already exists!"; \
		exit 1; \
	fi

# --------------------------------------------------------------------
# Cleanup
# --------------------------------------------------------------------
clean:  ## Remove build/dist artifacts
	@echo "Cleaning build/dist..."
	@rm -rf server/build
	@rm -rf server/dist
	@rm -rf server/go-wrapper/agent-server
	@rm -rf server/go-wrapper/agent-server.exe
	@rm -rf build
	@rm -rf dist
	@rm -rf *.egg-info

# --------------------------------------------------------------------
# All
# --------------------------------------------------------------------
all: clean sync lint typecheck test build  ## Perform a clean build of everything

# --------------------------------------------------------------------
# End
# --------------------------------------------------------------------
