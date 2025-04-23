SHELL := /bin/bash

# --------------------------------------------------------------------
# Default variables for building
# You can override on the command line, e.g.:
#   make build-exe DEBUG=true CI=true
# --------------------------------------------------------------------
DEBUG     ?= false
CI        ?= false
ONEFILE   ?= true
EXE_NAME  ?= agent-server
DIST_PATH ?= dist

# --------------------------------------------------------------------
# Mac code signing variables
# (Only needed if you actually do code signing on macOS)
# --------------------------------------------------------------------
CERT          ?=
PASSWORD      ?=
KEYCHAIN_NAME ?= build.keychain

# --------------------------------------------------------------------
# Tools/paths
# --------------------------------------------------------------------
PYINSTALLER_SPEC ?= server/agent-server.spec

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
	uv sync --all-extras --all-groups --all-packages

# --------------------------------------------------------------------
# Building: Wheels & PyInstaller
# --------------------------------------------------------------------
build-wheels:  sync ## Build Python wheels into dist/ via uv
	@echo "Building wheels..."
	uv build --out-dir $(DIST_PATH) --package agent_platform_core
	uv build --out-dir $(DIST_PATH) --package agent_platform_architectures_default
	uv build --out-dir $(DIST_PATH) --package agent_platform_server

build-exe: setup-keychain sync ## Build a PyInstaller executable
	@echo "Building PyInstaller executable..."
	@# Construct PyInstaller flags based on DEBUG/CI/ONEFILE
	$(eval PYI_FLAGS :=)
	$(eval SPEC_FLAGS :=)
ifneq ($(DEBUG),false)
	@# Debug mode => set debug flags, no CI
	$(eval PYI_FLAGS += --log-level=DEBUG)
	$(eval SPEC_FLAGS += --debug)
endif
ifneq ($(CI),false)
	$(eval PYI_FLAGS += -y)
endif
ifneq ($(ONEFILE),false)
	$(eval SPEC_FLAGS += --onefile)
endif
	$(eval SPEC_FLAGS += --name=$(EXE_NAME))

	@# Set LD_LIBRARY_PATH to the uv's venv lib location
	@# This ensures PyInstaller can find the required libraries
	LD_LIBRARY_PATH=.venv/lib uv run pyinstaller $(PYI_FLAGS) --distpath=$(DIST_PATH) $(PYINSTALLER_SPEC) -- $(SPEC_FLAGS)
ifeq ($(shell uname -s),Darwin)
	@# This should be happening anyway... but binary fails to run without it
	@# for me on OSX using adhoc signing.
	@if [ -z "$(MACOS_SIGNING_CERT_NAME)" ]; then \
		echo "No signing certificate specified, using ad-hoc signing..."; \
		codesign --force --deep --sign - ./$(DIST_PATH)/$(EXE_NAME); \
	fi
endif

build: clean build-wheels build-exe  ## Build both wheels and PyInstaller executable

# --------------------------------------------------------------------
# Mac Code Signing Keychain Setup (Optional)
# --------------------------------------------------------------------
setup-keychain:  ## Setup macOS keychain for code signing (no-op on non-macOS)
ifeq ($(shell uname -s),Darwin)
	@if [ -z "$(CERT)" ] || [ -z "$(PASSWORD)" ]; then \
	  echo "Skipping keychain setup: CERT or PASSWORD not provided."; \
	else \
	  echo "Creating macOS build keychain..." ; \
	  security create-keychain -p $(PASSWORD) $(KEYCHAIN_NAME) ; \
	  security default-keychain -s $(KEYCHAIN_NAME) ; \
	  security unlock-keychain -p $(PASSWORD) $(KEYCHAIN_NAME) ; \
	  echo "$(CERT)" | base64 --decode > cert.p12 ; \
	  echo "Importing certificate..." ; \
	  ( \
	    security import cert.p12 -A -P $(PASSWORD) ; \
	    security set-key-partition-list -S apple-tool:,apple: -s -k $(PASSWORD) $(KEYCHAIN_NAME) ; \
	  ) ; \
	  rm -f cert.p12 ; \
	  echo "Keychain setup complete." ; \
	fi
else
	@echo "Not macOS; skipping keychain setup."
endif

notarize:  ## Notarize the agent server executable (macOS only)
ifeq ($(shell uname -s),Darwin)
	@if [ ! -f $(DIST_PATH)/$(EXE_NAME) ]; then \
		echo "Error: Executable not found at $(DIST_PATH)/$(EXE_NAME)"; \
		echo "Please build the executable first with 'make build-exe'"; \
		exit 1; \
	fi
	@if [ -z "$(APPLEID)" ] || [ -z "$(APPLETEAMID)" ] || [ -z "$(APPLEIDPASS)" ]; then \
		echo "Error: Apple ID credentials not provided."; \
		echo "Usage: make notarize APPLEID=your.apple.id@example.com APPLETEAMID=YOUR_TEAM_ID APPLEIDPASS=your_app_specific_password"; \
		exit 1; \
	fi
	@echo "Verifying code signature..."
	codesign --verify --verbose=2 --deep $(DIST_PATH)/$(EXE_NAME)
	@echo "Displaying signature information..."
	codesign --verify --verbose=2 --display $(DIST_PATH)/$(EXE_NAME)
	@echo "Submitting for notarization..."
	@# Create a temporary directory for the zip file
	@mkdir -p $(DIST_PATH)/notarize_temp
	@# Zip the executable (notarization doesn't allow executable files directly)
	cd $(DIST_PATH) && zip notarize_temp/$(EXE_NAME).zip $(EXE_NAME)
	@# Submit for notarization with retry mechanism
	@# Define retry parameters
	@MAX_RETRIES=5; \
	RETRY_COUNT=0; \
	RETRY_DELAY=10; \
	SUCCESS=false; \
	while [ $$RETRY_COUNT -lt $$MAX_RETRIES ] && [ "$$SUCCESS" = "false" ]; do \
		echo "Notarization attempt $$((RETRY_COUNT+1)) of $$MAX_RETRIES..."; \
		if xcrun notarytool submit --apple-id $(APPLEID) --team-id $(APPLETEAMID) --password $(APPLEIDPASS) $(DIST_PATH)/notarize_temp/$(EXE_NAME).zip; then \
			SUCCESS=true; \
			echo "Notarization submitted successfully!"; \
		else \
			RETRY_COUNT=$$((RETRY_COUNT+1)); \
			if [ $$RETRY_COUNT -lt $$MAX_RETRIES ]; then \
				echo "Notarization submission failed. Retrying in $$RETRY_DELAY seconds..."; \
				sleep $$RETRY_DELAY; \
				RETRY_DELAY=$$((RETRY_DELAY*2)); \
			else \
				echo "Notarization submission failed after $$MAX_RETRIES attempts."; \
				exit 1; \
			fi \
		fi \
	done
	@# Clean up
	@rm -rf $(DIST_PATH)/notarize_temp
	@echo "Notarization process completed."
else
	@echo "Notarization is only supported on macOS."
endif

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

test:  check-env-or-no-env ## Run all tests with pytest (VCR playback only)
	VCR_RECORD=none uv run pytest

test-unit:  ## Run only unit tests
	VCR_RECORD=none uv run pytest -v -m "not integration"

test-integration:  check-env-or-no-env ## Run only integration tests
	VCR_RECORD=none uv run pytest -v -m integration

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

lint:  ## Run ruff linting (check only)
	uv run ruff check

lint-fix:  ## Run ruff linting (fix violations)
	uv run ruff check --fix

typecheck:  ## Run typechecking with pyright
	uv run pyright

format:  ## Run formatting with ruff
	uv run ruff format

check-format:  ## Run formatting check with ruff
	uv run ruff format --check

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
		\
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