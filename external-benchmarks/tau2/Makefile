TAU2_BENCH_REPO ?= https://github.com/sierra-research/tau2-bench.git
TAU2_BENCH_DIR ?= tau2-bench
TAU2_BENCH_REF ?= main
UV ?= uv

ROOT_DIR := $(abspath $(CURDIR)/../..)
TAU2_BENCH_ABS := $(abspath $(TAU2_BENCH_DIR))
WORKSPACE_VENV ?= $(ROOT_DIR)/.venv
TAU2_DATA_DIR ?= $(TAU2_BENCH_ABS)/data
TAU2_GIT_DIR ?= $(TAU2_BENCH_ABS).git
TAU2_RUNNER := $(abspath $(CURDIR)/run_tau2.py)

TAU2_DOMAIN ?=
TAU2_AGENT ?= llm_agent
TAU2_AGENT_LLM ?=
TAU2_AGENT_LLM_ARGS ?=
TAU2_USER ?= user_simulator
TAU2_USER_LLM ?=
TAU2_USER_LLM_ARGS ?=
TAU2_TASK_SET ?=
TAU2_TASK_SPLIT ?= base
TAU2_TASK_IDS ?=
TAU2_NUM_TASKS ?=
TAU2_NUM_TRIALS ?= 1
TAU2_MAX_STEPS ?=
TAU2_MAX_ERRORS ?=
TAU2_MAX_CONCURRENCY ?=
TAU2_SEED ?=
TAU2_LOG_LEVEL ?=
TAU2_SAVE_TO ?=
TAU2_ENFORCE_PROTOCOL ?= false
TAU2_EXTRA_ARGS ?=

ifeq ($(OS),Windows_NT)
WORKSPACE_PYTHON := $(WORKSPACE_VENV)/Scripts/python.exe
else
WORKSPACE_PYTHON := $(WORKSPACE_VENV)/bin/python
endif

.DEFAULT_GOAL := help

.PHONY: help setup sync install run run-airline run-retail run-telecom run-mock

define REQUIRE_DOMAIN_MESSAGE
Set TAU2_DOMAIN when invoking this target, e.g.
  make run TAU2_DOMAIN=airline TAU2_AGENT_LLM=gpt-4o-mini
or use a convenience target like make run-airline.
endef

TAU2_RUN_ARGS = --domain $(TAU2_DOMAIN) \
	--agent $(TAU2_AGENT) \
	--user $(TAU2_USER) \
	--num-trials $(TAU2_NUM_TRIALS) \
	--task-split $(TAU2_TASK_SPLIT)
TAU2_RUN_ARGS += $(if $(TAU2_AGENT_LLM),--agent-llm $(TAU2_AGENT_LLM))
TAU2_RUN_ARGS += $(if $(TAU2_AGENT_LLM_ARGS),--agent-llm-args $(TAU2_AGENT_LLM_ARGS))
TAU2_RUN_ARGS += $(if $(TAU2_USER_LLM),--user-llm $(TAU2_USER_LLM))
TAU2_RUN_ARGS += $(if $(TAU2_USER_LLM_ARGS),--user-llm-args $(TAU2_USER_LLM_ARGS))
TAU2_RUN_ARGS += $(if $(TAU2_TASK_SET),--task-set-name $(TAU2_TASK_SET))
TAU2_RUN_ARGS += $(if $(TAU2_TASK_IDS),--task-ids $(TAU2_TASK_IDS))
TAU2_RUN_ARGS += $(if $(TAU2_NUM_TASKS),--num-tasks $(TAU2_NUM_TASKS))
TAU2_RUN_ARGS += $(if $(TAU2_MAX_STEPS),--max-steps $(TAU2_MAX_STEPS))
TAU2_RUN_ARGS += $(if $(TAU2_MAX_ERRORS),--max-errors $(TAU2_MAX_ERRORS))
TAU2_RUN_ARGS += $(if $(TAU2_MAX_CONCURRENCY),--max-concurrency $(TAU2_MAX_CONCURRENCY))
TAU2_RUN_ARGS += $(if $(TAU2_SEED),--seed $(TAU2_SEED))
TAU2_RUN_ARGS += $(if $(TAU2_LOG_LEVEL),--log-level $(TAU2_LOG_LEVEL))
TAU2_RUN_ARGS += $(if $(TAU2_SAVE_TO),--save-to $(TAU2_SAVE_TO))
TAU2_RUN_ARGS += $(if $(filter true,$(TAU2_ENFORCE_PROTOCOL)),--enforce-communication-protocol)
TAU2_RUN_ARGS += $(TAU2_EXTRA_ARGS)

help: ## Show this help
	@echo "Usage: make [target]"
	@echo
	@echo "Available targets:"
	@grep -E '^[a-zA-Z0-9_-]+:.*?##' $(MAKEFILE_LIST) \
	 | sort \
	 | awk 'BEGIN {FS = ":.*?##"}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup: sync install ## Clone/update tau2-bench and install it into the workspace environment

sync: ## Ensure the tau2-bench source is exported locally without nested git metadata
	@if [ ! -d "$(TAU2_GIT_DIR)" ]; then \
		echo "Initializing bare clone of $(TAU2_BENCH_REPO) at $(TAU2_GIT_DIR)"; \
		git clone --bare $(TAU2_BENCH_REPO) $(TAU2_GIT_DIR); \
	fi
	echo "Fetching $(TAU2_BENCH_REF) from upstream..."
	git --git-dir=$(TAU2_GIT_DIR) fetch origin $(TAU2_BENCH_REF)
	echo "Exporting tau2-bench working tree without .git metadata..."
	rm -rf $(TAU2_BENCH_DIR)
	mkdir -p $(TAU2_BENCH_DIR)
	git --git-dir=$(TAU2_GIT_DIR) archive FETCH_HEAD | tar -x -C $(TAU2_BENCH_DIR)

install: ## Install tau2-bench into the workspace uv virtual environment
	@if [ ! -x "$(WORKSPACE_PYTHON)" ]; then \
		echo "Unable to find workspace virtualenv at $(WORKSPACE_PYTHON)."; \
		echo "Run 'make sync' from the repo root to create it, then retry."; \
		exit 1; \
	fi
	cd $(ROOT_DIR) && $(UV) pip install --python "$(WORKSPACE_PYTHON)" -e $(TAU2_BENCH_ABS)

run: ## Run tau2-bench simulations with the configured environment variables
	$(if $(strip $(TAU2_DOMAIN)),,$(error $(REQUIRE_DOMAIN_MESSAGE)))
	@if [ ! -x "$(WORKSPACE_PYTHON)" ]; then \
		echo "Workspace virtualenv not found at $(WORKSPACE_PYTHON). Run 'make sync' from the repo root first."; \
		exit 1; \
	fi
	@$(WORKSPACE_PYTHON) -c "import tau2" >/dev/null 2>&1 || { \
		echo "tau2 not found in $(WORKSPACE_VENV); running 'make -C external-benchmarks/tau2 install'..."; \
		$(MAKE) --no-print-directory install; \
	}
	TAU2_DATA_DIR="$(TAU2_DATA_DIR)" \
	cd $(ROOT_DIR) && "$(WORKSPACE_PYTHON)" $(TAU2_RUNNER) run $(TAU2_RUN_ARGS)

run-airline: ## Run tau2-bench against the airline domain
	@$(MAKE) run TAU2_DOMAIN=airline

run-retail: ## Run tau2-bench against the retail domain
	@$(MAKE) run TAU2_DOMAIN=retail

run-telecom: ## Run tau2-bench against the telecom domain
	@$(MAKE) run TAU2_DOMAIN=telecom

run-mock: ## Run tau2-bench against the mock domain
	@$(MAKE) run TAU2_DOMAIN=mock
