.PHONY: all lint format test help publish start migrate-postgres test_watch spell_check spell_fix install-hooks uninstall-hooks

SHELL := /bin/bash

# Default target executed when no arguments are given to make.
all: help

######################
# TESTING AND COVERAGE
######################

# Define a variable for the test file path.
TEST_FILE ?= tests/unit_tests/

start:
	poetry run uvicorn sema4ai_agent_server.server:app --port 8100 --log-config log_config.json

migrate-postgres:
	migrate -database postgres://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@$(POSTGRES_HOST):$(POSTGRES_PORT)/$(POSTGRES_DB)?sslmode=disable -path ./sema4ai_agent_server/migrations/postgres up

test:
	poetry run pytest $(TEST_FILE)

test_watch:
	poetry run ptw . -- $(TEST_FILE)

######################
# LINTING AND FORMATTING
######################

# Define a variable for Python and notebook files.
PYTHON_FILES=.
lint format: PYTHON_FILES=.
lint_diff format_diff: PYTHON_FILES=$(shell git diff --relative=. --name-only --diff-filter=d master | grep -E '\.py$$|\.ipynb$$')

lint lint_diff:
	poetry run ruff .
	poetry run ruff format $(PYTHON_FILES) --check

format format_diff:
	poetry run ruff format $(PYTHON_FILES)
	poetry run ruff --select I --fix $(PYTHON_FILES)

spell_check:
	poetry run codespell --toml pyproject.toml

spell_fix:
	poetry run codespell --toml pyproject.toml -w

######################
# GIT HOOKS
######################

ifeq ($(OS),Windows_NT)
install-hooks:
	@echo "Installing Git hooks..."
	copy scripts\pre-commit.bat .git\hooks\pre-commit.bat
	copy scripts\pre-push.bat .git\hooks\pre-push.bat
	@echo "Git hooks installed successfully!"

uninstall-hooks:
	@echo "Uninstalling Git hooks..."
	del /Q .git\hooks\pre-commit.bat
	del /Q .git\hooks\pre-push.bat
	@echo "Git hooks uninstalled successfully!"
else
install-hooks:
	@echo "Installing Git hooks..."
	cp scripts/pre-commit .git/hooks/pre-commit
	cp scripts/pre-push .git/hooks/pre-push
	chmod +x .git/hooks/pre-commit .git/hooks/pre-push
	@echo "Git hooks installed successfully!"

uninstall-hooks:
	@echo "Uninstalling Git hooks..."
	rm -f .git/hooks/pre-commit
	rm -f .git/hooks/pre-push
	@echo "Git hooks uninstalled successfully!"
endif

######################
# HELP
######################

help:
	@echo '===================='
	@echo '-- LINTING AND FORMATTING --'
	@echo 'format                       - run code formatters'
	@echo 'lint                         - run linters'
	@echo 'spell_check                  - run codespell on the project'
	@echo 'spell_fix                    - run codespell on the project and fix the errors'
	@echo '-- TESTS --'
	@echo 'test                         - run unit tests'
	@echo 'test TEST_FILE=<test_file>   - run all tests in file'
	@echo 'test_watch                   - run tests in watch mode'
	@echo '-- GIT HOOKS --'
	@echo 'install-hooks                - install Git pre-commit and pre-push hooks'
	@echo 'uninstall-hooks              - uninstall Git hooks'
	@echo '-- OTHER --'
	@echo 'start                        - start the application server'
	@echo 'migrate-postgres             - run PostgreSQL migrations'
	@echo '-- DOCUMENTATION tasks are from the top-level Makefile --'