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
ONEFILE   ?= true
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


# Notarization retry settings
MAX_RETRIES      ?= 5
RETRY_DELAY      ?= 10


# --------------------------------------------------------------------
# OSX Signing/Notarization
# --------------------------------------------------------------------
APPLE_ID         ?= 
APPLE_APP_PASS   ?= 
AC_TEAM_ID       ?= 
CODESIGN_ID      ?= -


# Certificate variables
CERT_B64          ?= 
KEYCHAIN_PASSWORD ?= 
P12_PASSWORD      ?= 

# --------------------------------------------------------------------
# Windows Signing
# --------------------------------------------------------------------
VAULT_URL          ?= 
CLIENT_ID          ?= 
TENANT_ID          ?= 
CLIENT_SECRET      ?= 
CERTIFICATE_NAME   ?= 

# --------------------------------------------------------------------
# Tools/paths
# --------------------------------------------------------------------
PYINSTALLER_SPEC ?= server/agent-server.spec
ENTITLEMENTS_FILE ?= server/entitlements.mac.plist
# CI environment variables, should be set by GitHub Actions
ifeq ($(IS_WINDOWS),true)
RUNNER_TEMP      ?= $(shell echo %TEMP%)
else
RUNNER_TEMP      ?= /tmp
endif
# Detect the keychain path if we're in CI
ifeq ($(CI),true)
KEYCHAIN := $(RUNNER_TEMP)/build.keychain-db
else
KEYCHAIN := $(HOME)/Library/Keychains/build.keychain-db
endif
# Notarization variables
NOTARIZE_ZIP_PATH := $(RUNNER_TEMP)/$(EXE_NAME).zip



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
	@echo "Building PyInstaller executable..."

# -------- assemble flag strings ---------------------------------
	$(eval PYI_FLAGS :=)
	$(eval SPEC_FLAGS :=)

ifneq ($(DEBUG),false)
	$(eval PYI_FLAGS += --log-level=DEBUG)
	$(eval SPEC_FLAGS += --debug)
endif
ifneq ($(CI),false)
	$(eval PYI_FLAGS += -y)
endif
ifneq ($(ONEFILE),false)
	$(eval SPEC_FLAGS += --onefile)
endif
ifeq ($(IS_MACOS),true)
	$(eval SPEC_FLAGS += --codesign-identity "$(CODESIGN_ID)" --osx-entitlements-file $(ENTITLEMENTS_FILE))
endif
	$(eval SPEC_FLAGS += --name=$(EXE_NAME))

	LD_LIBRARY_PATH=.venv/lib \
		uv run pyinstaller $(PYI_FLAGS) \
		--distpath=$(DIST_PATH) $(PYINSTALLER_SPEC) -- $(SPEC_FLAGS)

ifeq ($(IS_MACOS),true)
build: clean build-wheels setup-keychain build-exe codesign notarize ## Build, sign and notarize on macOS
	@echo "Build complete!"
else ifeq ($(IS_WINDOWS),true)
build: clean build-wheels build-exe codesign ## Build and sign on Windows platforms
	@echo "Build complete!"
else
build: clean build-wheels build-exe ## Build on non-Mac platforms
	@echo "Build complete!"
endif

# --------------------------------------------------------------------
# OSX Signing/Notarization
# --------------------------------------------------------------------
ifeq ($(IS_MACOS),true)
setup-keychain:  ## Setup macOS keychain for code signing
# Check required environment variables
ifndef CERT_B64
	$(error CERT_B64 environment variable is not set)
endif
ifndef KEYCHAIN_PASSWORD
	$(error KEYCHAIN_PASSWORD environment variable is not set)
endif
ifndef P12_PASSWORD
	$(error P12_PASSWORD environment variable is not set)
endif
	@echo "Setting up macOS keychain for code signing..."
	@echo "$(CERT_B64)" | base64 --decode > $(RUNNER_TEMP)/cert.p12
	
	@security create-keychain -p "$(KEYCHAIN_PASSWORD)" "$(KEYCHAIN)"
	@security set-keychain-settings -lut 21600 "$(KEYCHAIN)"
	@security unlock-keychain -p "$(KEYCHAIN_PASSWORD)" "$(KEYCHAIN)"
	
# Import the p12 and give codesign/non-interactive access
	@security import $(RUNNER_TEMP)/cert.p12 -P "$(P12_PASSWORD)" -A -t cert -f pkcs12 -k "$(KEYCHAIN)"
	@security set-key-partition-list -S apple-tool:,apple: -k "$(KEYCHAIN_PASSWORD)" "$(KEYCHAIN)"
	
# Make the temp keychain the default so `codesign` will find the identity
	@security list-keychain -d user -s "$(KEYCHAIN)"
	@echo "Keychain setup complete."
else
setup-keychain:
	$(error setup-keychain target is only supported on macOS)
endif

ifeq ($(IS_MACOS),true)
codesign:  ## Codesign the agent server executable (macOS only)
ifeq ($(CI),true)
ifeq ($(CODESIGN_ID),-)
	$(error CODESIGN_ID cannot be "-" in CI environment)
endif
endif
	@echo "Codesigning executable..."
	codesign --force --deep --timestamp --options runtime \
	         --entitlements $(ENTITLEMENTS_FILE) \
	         --sign "$(CODESIGN_ID)" $(EXE_PATH)
else ifeq ($(IS_WINDOWS),true)
codesign:
ifeq ($(CI),true)
ifndef VAULT_URL
	$(error VAULT_URL environment variable is not set)
endif
ifndef CLIENT_ID
	$(error CLIENT_ID environment variable is not set)
endif
ifndef TENANT_ID
	$(error TENANT_ID environment variable is not set)
endif
ifndef CLIENT_SECRET
	$(error CLIENT_SECRET environment variable is not set)
endif
ifndef CERTIFICATE_NAME
	$(error CERTIFICATE_NAME environment variable is not set)
endif
endif
	@echo "Codesigning Windows executable..."
	@# Check if AzureSignTool is already installed
	@if ! command -v azuresigntool >/dev/null 2>&1; then \
		echo "Installing AzureSignTool..."; \
		dotnet tool install --global AzureSignTool --version 3.0.0; \
	fi
	@# Sign the executable using Azure Key Vault
	@azuresigntool sign \
		--description-url "https://sema4.ai" \
		--file-digest sha256 \
		--azure-key-vault-url "$(VAULT_URL)" \
		--azure-key-vault-client-id "$(CLIENT_ID)" \
		--azure-key-vault-tenant-id "$(TENANT_ID)" \
		--azure-key-vault-client-secret "$(CLIENT_SECRET)" \
		--azure-key-vault-certificate "$(CERTIFICATE_NAME)" \
		--timestamp-rfc3161 http://timestamp.digicert.com \
		--timestamp-digest sha256 \
		$(EXE_PATH)

else
codesign:
	$(error codesign target is only supported on macOS and Windows)
endif

notarize:  ## Notarize the agent server executable (macOS only)
ifndef APPLE_ID
	$(error APPLE_ID environment variable is not set)
endif
ifndef APPLE_APP_PASS
	$(error APPLE_APP_PASS environment variable is not set)
endif
ifndef AC_TEAM_ID
	$(error AC_TEAM_ID environment variable is not set)
endif
	@echo "Submitting for notarization..."
	zip -qr $(NOTARIZE_ZIP_PATH) $(EXE_PATH)

# Submit for notarization with retry mechanism
	@RETRY_COUNT=0; SUCCESS=false; \
	while [ $$RETRY_COUNT -lt $(MAX_RETRIES) ] && [ "$$SUCCESS" = "false" ]; do \
		echo "Notarization attempt $$((RETRY_COUNT+1)) of $(MAX_RETRIES)..."; \
		if xcrun notarytool submit $(NOTARIZE_ZIP_PATH) \
			--apple-id "$(APPLE_ID)" \
			--password "$(APPLE_APP_PASS)" \
			--team-id "$(AC_TEAM_ID)" \
			--wait; then \
			SUCCESS=true; \
			echo "Notarization submitted successfully!"; \
		else \
			RETRY_COUNT=$$((RETRY_COUNT+1)); \
			if [ $$RETRY_COUNT -lt $(MAX_RETRIES) ]; then \
				echo "Notarization submission failed. Retrying in $(RETRY_DELAY) seconds..."; \
				sleep $(RETRY_DELAY); \
				RETRY_DELAY=$$((RETRY_DELAY*2)); \
			else \
				echo "Notarization submission failed after $(MAX_RETRIES) attempts."; \
				exit 1; \
			fi \
		fi \
	done

# Clean up
	@rm -f $(RUNNER_TEMP)/$(EXE_NAME).zip
	@echo "Notarization process completed."

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

format:  ## Run formatting with ruff
	uv run ruff format

check-format:  ## Run formatting check with ruff
	uv run ruff format --check

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
