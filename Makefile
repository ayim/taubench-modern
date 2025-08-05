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
VERSION   ?=

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
ifdef VERSION
	uv run python scripts/build_exe.py build-executable --go-wrapper --ci --version $(VERSION)
else
	uv run python scripts/build_exe.py build-executable --go-wrapper --ci
endif

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
# Observability
# --------------------------------------------------------------------

observability-up: ## Start the observability stack.
	@echo "Starting observability stack..."
	docker compose -f observability/docker-compose.observability.yml up -d

observability-down: ## Stop the observability stack.
	@echo "Stopping observability stack..."
	docker compose -f observability/docker-compose.observability.yml down

observability-logs: ## Show the logs of the observability stack.
	@echo "Showing observability stack logs..."
	docker compose -f observability/docker-compose.observability.yml logs -f

observability-ps: ## Show the status of the observability stack.
	@echo "Checking observability stack status..."
	docker compose -f observability/docker-compose.observability.yml ps

observability-clean: ## Clean the observability stack and volumes.
	@echo "Cleaning observability stack and volumes..."
	docker compose -f observability/docker-compose.observability.yml down -v
	docker volume rm agent-platform_prometheus_data 2>/dev/null || true

# --------------------------------------------------------------------
# Run & Test
# --------------------------------------------------------------------
run-server:  ## Run the agent server
	@echo "Running server from agent_platform.server..."
	@echo "💡 Tip: Set PORT=<port> to use a different port (default: 8000)"
	@echo ""
	PORT=$${PORT:-8000} uv run -m agent_platform.server --port $$PORT

run-server-exe:  ## Run the agent server executable
	@if [ ! -f dist/$(EXE_NAME) ]; then \
		echo "Executable not found in dist/"; \
		echo "Please build the executable first with 'make build-exe'"; \
		exit 1; \
	fi
	@echo "Running server from dist/..."
	@echo "💡 Tip: Set PORT=<port> to use a different port (default: 8000)"
	@echo ""
	./dist/$(EXE_NAME) --port $${PORT:-8000}

run-as-studio:  ## Run the agent server as in Studio
	@echo "Running server from agent_platform.server (as Studio)..."
	uv run -m agent_platform.server --host "127.0.0.1" --port 58885 --use-data-dir-lock --kill-lock-holder

run-server-hot-reload: sync  ## Run the agent server with hot reloading (uvicorn --reload)
	@echo "Starting agent server with hot reloading..."
	@echo "Server will automatically restart when you change files in:"
	@echo "  - server/src/"
	@echo "  - core/src/"
	@echo "  - architectures/*/src/ (any architecture)"
	@echo ""
	@echo "💡 Tip: Set PORT=<port> to use a different port (default: 8000)"
	@echo "       Set POSTGRES_HOST=localhost if you have local PostgreSQL running"
	@echo "       Or use docker compose up postgres to start containerized PostgreSQL"
	@echo ""
	SEMA4AI_AGENT_SERVER_DB_TYPE=postgres \
	LOG_LEVEL=DEBUG \
	POSTGRES_HOST=$${POSTGRES_HOST:-localhost} \
	POSTGRES_DB=$${POSTGRES_DB:-agents} \
	POSTGRES_USER=$${POSTGRES_USER:-agents} \
	POSTGRES_PASSWORD=$${POSTGRES_PASSWORD:-agents} \
	POSTGRES_PORT=$${POSTGRES_PORT:-5432} \
	uv run uvicorn agent_platform.server.dev:create_dev_app \
		--factory \
		--host 127.0.0.1 \
		--port $${PORT:-8000} \
		--reload \
		--reload-include server/src/**/*.py \
		--reload-include core/src/**/*.py \
		--reload-include architectures/*/src/**/*.py


test:  sync check-env-or-no-env ## Run all tests with pytest (VCR playback only)
	VCR_RECORD=none uv run pytest

test-unit: sync  ## Run only unit tests
ifeq ($(CI),true)
ifeq ($(IS_LINUX),true)
	VCR_RECORD=none uv run pytest -v -m "not integration"
else
	VCR_RECORD=none uv run pytest -v -m "not integration and not postgresql"
endif
else
	VCR_RECORD=none uv run pytest -v -m "not integration"
endif

test-integration:  sync check-env-or-no-env ## Run only integration tests
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

coverage:  sync ## Run tests with pytest and generate coverage report
	uv run coverage run -m pytest
	uv run coverage report
	uv run coverage html

check-pr:  sync ## Run common PR checks (format, lint, typecheck, unit tests)
	@echo "Running PR checks..."
	$(MAKE) check-format
	$(MAKE) lint
	$(MAKE) typecheck
	$(MAKE) test-unit
	@echo "✅ All PR checks passed!"

lint:  sync ## Run ruff linting (check only)
	uv run ruff check

lint-fix:  sync ## Run ruff linting (fix violations)
	uv run ruff check --fix

lint-fix-unsafe:  sync ## Run ruff linting (fix violations)
	uv run ruff check --fix --unsafe-fixes

typecheck:  sync ## Run typechecking with pyright
	uv run pyright

format:  sync ## Run formatting with ruff and prettier (node/npm must be in the path for npx to work).
	uv run ruff format
	npx prettier@3.5.3 . --write

check-format:  sync ## Run formatting check with ruff
	uv run ruff format --check
	npx prettier@3.5.3 . --check

notebooks-check:  sync ## Check if notebooks have outputs that need stripping (dry-run)
	@echo "Checking notebooks for outputs that need stripping..."
	@if uv run nbstripout --verify $$(find . -name "*.ipynb" -type f); then \
		echo "✅ All notebooks are clean!"; \
	else \
		echo "❌ Some notebooks have outputs that need stripping!"; \
		echo "Run 'make notebooks-clean' to clean them."; \
		exit 1; \
	fi

notebooks-clean:  sync ## Strip outputs from all Jupyter notebooks
	@echo "Stripping outputs from all notebooks..."
	@uv run nbstripout $$(find . -name "*.ipynb" -type f)
	@echo "✅ All notebooks have been cleaned!"

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
# AWS Deployment
# --------------------------------------------------------------------

aws:  ## AWS operations: make aws deploy|status|destroy|logs|troubleshoot
	@if [ "$(filter-out $@,$(MAKECMDGOALS))" = "deploy" ]; then \
		echo "Deploying to AWS Fargate + RDS..."; \
		./aws-deployment/deploy.sh; \
	elif [ "$(filter-out $@,$(MAKECMDGOALS))" = "status" ]; then \
		echo "Checking AWS deployment status..."; \
		cd aws-deployment/terraform && terraform output; \
	elif [ "$(filter-out $@,$(MAKECMDGOALS))" = "destroy" ]; then \
		echo "Destroying AWS resources..."; \
		./aws-deployment/destroy.sh; \
	elif [ "$(filter-out $@,$(MAKECMDGOALS))" = "troubleshoot" ]; then \
		echo "Running AWS deployment troubleshooting..."; \
		./aws-deployment/troubleshoot.sh; \
	elif [ "$(filter-out $@,$(MAKECMDGOALS))" = "logs" ]; then \
		echo "Showing AWS ECS logs with task status..."; \
		cd aws-deployment/terraform && \
		PROJECT_NAME=$$(terraform output -raw ecs_cluster_name 2>/dev/null || echo "agent-platform") && \
		AWS_REGION=$$(terraform output -raw aws_region 2>/dev/null || echo "us-east-1") && \
		echo "📊 Current ECS Task Status:" && \
		aws ecs describe-services --cluster $$PROJECT_NAME --services $$PROJECT_NAME --region $$AWS_REGION --query 'services[0].{Running:runningCount,Pending:pendingCount,Desired:desiredCount}' --output table 2>/dev/null || true && \
		echo "" && \
		echo "📋 Live Application Logs:" && \
		aws logs tail /ecs/$$PROJECT_NAME --follow --region $$AWS_REGION; \
	else \
		echo "Usage: make aws [deploy|status|destroy|logs|troubleshoot]"; \
		echo ""; \
		echo "🚀 Agent Platform AWS Deployment"; \
		echo "   Fargate + RDS deployment with Terraform"; \
		echo ""; \
		echo "Available commands:"; \
		echo "  make aws deploy      - Deploy to AWS Fargate + RDS (builds image, creates infrastructure)"; \
		echo "  make aws status      - Show deployment status and URLs"; \
		echo "  make aws destroy     - Safely destroy all AWS resources"; \
		echo "  make aws logs        - Follow ECS container logs with task status"; \
		echo "  make aws troubleshoot - Diagnose deployment issues and show solutions"; \
		echo ""; \
		echo "Prerequisites:"; \
		echo "  • AWS CLI configured (aws configure)"; \
		echo "  • Terraform installed"; \
		echo "  • Docker running"; \
		echo ""; \
		echo "AWS Profile Usage:"; \
		echo "  • Default profile: make aws deploy"; \
		echo "  • Specific profile: AWS_PROFILE=production make aws deploy"; \
		echo "  • Check current: aws sts get-caller-identity"; \
		echo ""; \
		echo "Configuration:"; \
		echo "  • Edit aws-deployment/terraform/terraform.tfvars for custom settings"; \
		echo "  • Environment variables: AWS_PROFILE, PROJECT_NAME, AWS_REGION"; \
		echo "  • Build mode: Always local AMD64 (Fargate compatible)"; \
		echo "  • Default: us-east-1, db.t3.micro, 1 task, local builds"; \
		echo ""; \
		echo "Cost: ~$$30-50/month for minimal deployment"; \
	fi

# --------------------------------------------------------------------
# GCP Deployment
# --------------------------------------------------------------------

gcp:  ## GCP operations: make gcp setup|deploy|status|teardown|add-developer|iap
	@if [ "$(filter-out $@,$(MAKECMDGOALS))" = "setup" ]; then \
		echo "Setting up GCP environment..."; \
		./scripts/gcp/setup.sh; \
	elif [ "$(filter-out $@,$(MAKECMDGOALS))" = "deploy" ]; then \
		echo "Deploying to GCP..."; \
		./scripts/gcp/deploy.sh; \
	elif [ "$(filter-out $@,$(MAKECMDGOALS))" = "status" ]; then \
		echo "Checking GCP deployment status..."; \
		./scripts/gcp/status.sh; \
	elif [ "$(filter-out $@,$(MAKECMDGOALS))" = "teardown" ]; then \
		echo "Tearing down GCP resources..."; \
		./scripts/gcp/teardown.sh; \
	elif [ "$(filter-out $@,$(MAKECMDGOALS))" = "add-developer" ]; then \
		echo "Adding developer to GCP project..."; \
		./scripts/gcp/add-developer.sh; \
	elif [ "$(filter-out $@,$(MAKECMDGOALS))" = "iap" ]; then \
		echo "Managing IAP access..."; \
		./scripts/gcp/iap.sh; \
	else \
		echo "Usage: make gcp [setup|deploy|status|teardown|add-developer|iap]"; \
		echo ""; \
		echo "🚀 Agent Platform GCP Deployment"; \
		echo "   Multi-developer environment with user namespacing and IAP security"; \
		echo ""; \
		echo "Available commands:"; \
		echo "  make gcp setup        - Setup GCP environment (interactive, auto-detects missing components)"; \
		echo "  make gcp deploy       - Deploy services to Cloud Run (interactive, deployment profiles)"; \
		echo "  make gcp status       - Show deployment status, health, URLs, and logs"; \
		echo "  make gcp teardown     - Remove GCP resources (interactive, respects permissions)"; \
		echo "  make gcp add-developer - Add developers to project (admin only, grants necessary roles)"; \
		echo "  make gcp iap          - Manage Identity-Aware Proxy access control"; \
		echo ""; \
		echo "Your services: agent-server-$(CACHED_USER), workroom-$(CACHED_USER)"; \
		echo ""; \
		echo "Tips:"; \
		echo "  • All operations are user-namespaced for isolation"; \
		echo "  • Use 'Personal Isolated' profile for development (recommended)"; \
		echo "  • IAP provides secure Google-authenticated access"; \
		echo "  • For advanced usage: ./scripts/gcp/[script].sh --help"; \
	fi

# Dummy targets so make doesn't complain about "nothing to be done"
setup deploy status teardown add-developer iap destroy logs troubleshoot:
	@:

.PHONY: aws gcp setup deploy status teardown add-developer iap destroy logs troubleshoot

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
	@rm -rf workroom/**/dist
	@echo "Clean complete!"

force-clean: clean ## Force remove build/dist artifacts (use with caution)
	@echo "Force cleaning temp database..."
	@rm -rf uploads/
	@rm -rf agent-server.lock
	@rm -rf agent-server.log
	@rm -rf agent-server.pid
	@rm -rf agentserver.db
	@echo "Force clean complete!"

# --------------------------------------------------------------------
# Workitems
# --------------------------------------------------------------------

#  Run the workitems server, standalone (requires a remote agent-server via AGENT_SERVER_URL)
run-workitems-server:
	uv run -m agent_platform.workitems

# Run tests for workitems
test-workitems:
	uv run --package agent_platform_workitems pytest -v workitems/tests/

test-workitems-judge:  sync ## Test work item judge stability by running multiple times (NUM_RUNS=20, TEST_PATTERN=test_work_item_judge_with_recorded_threads)
	@if [ -z "$$OPENAI_API_KEY" ]; then \
		echo "❌ OPENAI_API_KEY is not set!"; \
		echo "This test requires an OpenAI API key to run."; \
		echo "Please set OPENAI_API_KEY in your environment or .env file."; \
		exit 1; \
	fi
	@NUM_RUNS=$${NUM_RUNS:-20}; \
	TEST_PATTERN=$${TEST_PATTERN:-test_work_item_judge_with_recorded_threads}; \
	TIMESTAMP=$$(date +"%Y%m%d_%H%M%S"); \
	RESULTS_DIR="judge_test_results/$$TIMESTAMP"; \
	SUMMARY_FILE="$$RESULTS_DIR/summary.txt"; \
	mkdir -p "$$RESULTS_DIR"; \
	echo "Starting judge stability test..."; \
	echo "Number of runs: $$NUM_RUNS"; \
	echo "Test pattern: $$TEST_PATTERN"; \
	echo "Results directory: $$RESULTS_DIR"; \
	echo "=========================================="; \
	PASSED=0; \
	FAILED=0; \
	FAILED_RUNS=""; \
	for i in $$(seq 1 $$NUM_RUNS); do \
		echo ""; \
		echo "=========================================="; \
		echo "🔄 RUN $$i/$$NUM_RUNS - $$(date '+%H:%M:%S')"; \
		echo "=========================================="; \
		OUTPUT_FILE="$$RESULTS_DIR/run_$$i.log"; \
		if VCR_RECORD=none uv run pytest -k "$$TEST_PATTERN" -v --tb=long 2>&1 | tee "$$OUTPUT_FILE"; then \
			echo "  ✅ PASSED"; \
			PASSED=$$((PASSED + 1)); \
			rm "$$OUTPUT_FILE"; \
		else \
			echo "  ❌ FAILED - saved to $$OUTPUT_FILE"; \
			FAILED=$$((FAILED + 1)); \
			FAILED_RUNS="$$FAILED_RUNS $$i"; \
			FAILURE_FILE="$$RESULTS_DIR/failure_$$i.txt"; \
			echo "=== FAILURE DETAILS FOR RUN $$i ===" > "$$FAILURE_FILE"; \
			echo "Timestamp: $$(date)" >> "$$FAILURE_FILE"; \
			echo "" >> "$$FAILURE_FILE"; \
			grep -A 50 -B 10 "FAILED\|AssertionError\|ERROR" "$$OUTPUT_FILE" >> "$$FAILURE_FILE" 2>/dev/null || tail -100 "$$OUTPUT_FILE" >> "$$FAILURE_FILE"; \
		fi; \
	done; \
	echo "=========================================="; \
	echo "TEST STABILITY SUMMARY"; \
	echo "=========================================="; \
	echo "Total runs: $$NUM_RUNS"; \
	echo "Passed: $$PASSED"; \
	echo "Failed: $$FAILED"; \
	if command -v bc >/dev/null 2>&1; then \
		SUCCESS_RATE=$$(echo "scale=2; $$PASSED * 100 / $$NUM_RUNS" | bc -l); \
	else \
		SUCCESS_RATE="N/A (bc not available)"; \
	fi; \
	echo "Success rate: $$SUCCESS_RATE%"; \
	{ \
		echo "Judge Test Stability Report"; \
		echo "Generated: $$(date)"; \
		echo "Test: $$TEST_PATTERN"; \
		echo "=========================================="; \
		echo "Total runs: $$NUM_RUNS"; \
		echo "Passed: $$PASSED"; \
		echo "Failed: $$FAILED"; \
		echo "Success rate: $$SUCCESS_RATE%"; \
		echo ""; \
		if [ $$FAILED -gt 0 ]; then \
			echo "Failed runs:$$FAILED_RUNS"; \
			echo ""; \
			echo "Failure patterns (if any):"; \
			echo "----------------------------------------"; \
			if ls "$$RESULTS_DIR"/failure_*.txt >/dev/null 2>&1; then \
				echo "=== Common error patterns ==="; \
				grep -h "AssertionError\|ERROR\|Expected.*but got" "$$RESULTS_DIR"/failure_*.txt | sort | uniq -c | sort -nr; \
			fi; \
		else \
			echo "🎉 All tests passed! The judge appears to be stable."; \
		fi; \
	} > "$$SUMMARY_FILE"; \
	echo ""; \
	echo "Full summary saved to: $$SUMMARY_FILE"; \
	if [ $$FAILED -gt 0 ]; then \
		echo "Failed run details saved in: $$RESULTS_DIR/"; \
		echo ""; \
		echo "To analyze failures:"; \
		echo "  cat $$SUMMARY_FILE"; \
		echo "  ls $$RESULTS_DIR/failure_*.txt"; \
		exit 1; \
	else \
		echo "🎉 All tests passed! Judge appears stable."; \
	fi

# --------------------------------------------------------------------
# All
# --------------------------------------------------------------------
all: clean sync lint typecheck test build  ## Perform a clean build of everything

# --------------------------------------------------------------------
# End
# --------------------------------------------------------------------
