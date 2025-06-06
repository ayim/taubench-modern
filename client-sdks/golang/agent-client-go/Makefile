# Makefile for the Go project

# Variables
APP_NAME := "agent-client"
GO_FILES := $(shell find . -name '*.go' | grep -v /vendor/)
PKG := ./...
INTEGRATION_TEST_DIR := ./test/integration
DIST_DIR := dist
OS := $(shell go env GOOS)
ARCH := $(shell go env GOARCH)
BINARY_NAME := $(APP_NAME)-$(OS)-$(ARCH)
TARBALL := $(BINARY_NAME).tgz
ZIPFILE := $(BINARY_NAME).zip

# Commands
.PHONY: all run build test test-all test-integration test-integration-verbose deps clean tidy lint format init-project dist dist-all docs

all: test-all build

run: ## Run the application
	@echo "Running $(APP_NAME)..."
	@go run cmd/$(APP_NAME)/*.go

clean: ## Remove previous build artifacts and test cache
	@echo "Cleaning up..."
	go clean -modcache -cache -testcache -i -r
	rm -rf $(DIST_DIR)
	rm -rf $(APP_NAME)

build: ## Build the project and output distribution binaries
	@echo "Building $(APP_NAME)..."
	@go build -o $(APP_NAME) cmd/$(APP_NAME)/*.go

test: ## Run unit tests
	@echo "Running unit tests..."
	go test -count=1 $(PKG)

test-integration: ## Run integration tests
	@echo "Running integration tests..."
	go test -count=1 $(INTEGRATION_TEST_DIR) --tags=integration

test-integration-verbose: ## Run integration tests with verbose output
	@echo "Running integration tests (verbose)..."
	go test -count=1 $(INTEGRATION_TEST_DIR) --tags=integration -v

test-all: test test-integration ## Run all tests (unit and integration)
	@echo "Running all tests..."

deps: ## Fetch and update project dependencies
	@echo "Updating dependencies..."
	go get -u ./...
	go mod tidy

tidy: ## Tidy up go.mod and remove unused dependencies
	@echo "Tidying up go.mod..."
	go mod tidy

lint: ## Lint the Go source files
	@echo "Linting..."
	golangci-lint run

format: ## Format all Go source files
	@echo "Formatting Go source files..."
	gofmt -s -w $(GO_FILES)

init-project: ## Initialize the project by installing necessary tools
	@echo "Installing necessary Go tools..."
	go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest
	go install golang.org/x/tools/cmd/godoc@latest
	go get github.com/spf13/cobra
	go get github.com/spf13/viper

dist: clean ## Create a binary distribution for the current OS and architecture
	@echo "Creating distribution..."
	mkdir -p $(DIST_DIR)
	GOOS=$(OS) GOARCH=$(ARCH) go build -o $(DIST_DIR)/$(APP_NAME) cmd/$(APP_NAME)/*.go
	tar -czvf $(DIST_DIR)/$(TARBALL) -C $(DIST_DIR) $(APP_NAME)
	zip -j $(DIST_DIR)/$(ZIPFILE) $(DIST_DIR)/$(APP_NAME)
	rm $(DIST_DIR)/$(APP_NAME)
	@echo "Distribution created: $(DIST_DIR)/$(TARBALL) and $(DIST_DIR)/$(ZIPFILE)"

dist-all: clean ## Create binary distributions for common OS and architecture combinations
	@echo "Creating distributions for all supported OS/ARCH combinations..."
	mkdir -p $(DIST_DIR)
	for os in linux darwin windows; do \
		for arch in amd64 arm64; do \
			EXT=""; \
			if [ "$$os" = "windows" ]; then EXT=".exe"; fi; \
			GOOS=$$os GOARCH=$$arch go build -o $(DIST_DIR)/$(APP_NAME)$$EXT cmd/$(APP_NAME)/*.go; \
			tar -czvf $(DIST_DIR)/$(APP_NAME)-$$os-$$arch.tgz -C $(DIST_DIR) $(APP_NAME)$$EXT; \
			zip -j $(DIST_DIR)/$(APP_NAME)-$$os-$$arch.zip $(DIST_DIR)/$(APP_NAME)$$EXT; \
			rm $(DIST_DIR)/$(APP_NAME)$$EXT; \
		done; \
	done
	@echo "All distributions created in the $(DIST_DIR) directory."

docs: ## Serve Go documentation locally
	@echo "Serving Go documentation at http://localhost:6060..."
	@echo "Press Ctrl+C to stop."
	@open http://localhost:6060/pkg/$(shell go list -m)/ || xdg-open http://localhost:6060/pkg/$(shell go list -m)/ || echo "Open http://localhost:6060/pkg/$(shell go list -m)/ manually in your browser."
	godoc -http=:6060