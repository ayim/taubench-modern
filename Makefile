SHELL := /bin/bash

# --------------------------------------------------------------------
# Default variables for building
# You can override on the command line, e.g.:
#   make build-exe DEBUG=true CI=true
# --------------------------------------------------------------------
DEBUG     ?= false
CI        ?= false
ONEFILE   ?= true
NAME      ?= agent-server
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
	 | awk 'BEGIN {FS = ":.*?##"}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# --------------------------------------------------------------------
# Setup & Install
# --------------------------------------------------------------------
venv:  ## Create a new virtual environment with uv
	@if [ -n "$$VIRTUAL_ENV" ]; then \
		echo "Already in virtual environment: $$VIRTUAL_ENV"; \
	else \
		echo "Creating new virtual environment..."; \
		uv venv --python=python3.12 \
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

build-exe:  sync ## Build a PyInstaller executable
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
	$(eval SPEC_FLAGS += --name=$(NAME))

	uv run pyinstaller $(PYI_FLAGS) --distpath=$(DIST_PATH) $(PYINSTALLER_SPEC) -- $(SPEC_FLAGS)
ifeq ($(shell uname -s),Darwin)
	@# This should be happening anyway... but binary fails to run without it
	@# for me on OSX using adhoc signing.
	@if [ -z "$(MACOS_SIGNING_CERT_NAME)" ]; then \
		echo "No signing certificate specified, using ad-hoc signing..."; \
		codesign --force --deep --sign - ./$(DIST_PATH)/$(NAME); \
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
run-server:  ## Run the agent server with a custom PYTHONPATH
	@echo "Running server from agent_platform.server..."
	PYTHONPATH=core/src:architectures/default/src:server/src uv run -m agent_platform.server

run-server-exe:  ## Run the agent server executable
	@if [ ! -f dist/agent-server ]; then \
		echo "Executable not found in dist/"; \
		echo "Please build the executable first with 'make build-exe'"; \
		exit 1; \
	fi
	@echo "Running server from dist/..."
	./dist/agent-server

test:  ## Run tests with pytest
	uv run pytest core/ server/

lint:  ## Run ruff linting (check only)
	uv run ruff check

lint-fix:  ## Run ruff linting (fix violations)
	uv run ruff check --fix

typecheck:  ## Run typechecking with pyright
	uv run pyright

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
