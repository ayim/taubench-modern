# Makefile for the Go project

# Variables
APP_NAME := agent-cli
GO_FILES := $(shell find . -name '*.go' | grep -v /vendor/)
PKG := ./...
DIST_DIR := dist
BUILD_DIR := build
OS := $(shell go env GOOS)
ARCH := $(shell go env GOARCH)
BINARY_NAME := $(APP_NAME)-$(OS)-$(ARCH)
TARBALL := $(BINARY_NAME).tgz
ZIPFILE := $(BINARY_NAME).zip
EXECUTABLE := $(APP_NAME)$(if $(filter windows,$(OS)),.exe,)

# Commands
.PHONY: all run build test deps clean tidy lint format init-project dist dist-all docs

all: test build

run: ## Run the application
	@echo "Running $(APP_NAME)..."
	@go run main.go

clean: ## Remove previous build artifacts and test cache
	@echo "Cleaning up..."
	go clean -modcache -cache -testcache -i -r
	rm -rf $(BUILD_DIR)
	rm -rf $(DIST_DIR)
	rm -rf $(APP_NAME)

build: ## Build the project and output distribution binaries
	@echo "Building $(APP_NAME)..."
	mkdir -p $(DIST_DIR)
	@go build -o $(DIST_DIR)/$(EXECUTABLE) main.go

test: ## Run tests
	@echo "Running tests..."
	go test ./tests -v -run "$(TEST)"

deps: ## Fetch and update project dependencies
	@echo "Updating dependencies..."
	go get -u ./...
	go mod tidy

tidy: lint-fix ## Tidy up go.mod and remove unused dependencies
	@echo "Tidying up go.mod..."
	go mod tidy

lint: ## Lint the Go source files
	@echo "Linting..."
	golangci-lint run

lint-fix:
	@echo "Fixing Linting..."
	golangci-lint run --fix

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
	GOOS=$(OS) GOARCH=$(ARCH) go build -o $(DIST_DIR)/$(APP_NAME) main.go
	tar -czvf $(DIST_DIR)/$(TARBALL) -C $(DIST_DIR) $(APP_NAME)
	zip -j $(DIST_DIR)/$(ZIPFILE) $(DIST_DIR)/$(APP_NAME)
	@echo "Distribution created: $(DIST_DIR)/$(TARBALL) and $(DIST_DIR)/$(ZIPFILE)"

dist-all: clean ## Create binary distributions for common OS and architecture combinations
	@echo "Creating distributions for all supported OS/ARCH combinations..."
	mkdir -p $(DIST_DIR)
	for os in linux darwin windows; do \
		for arch in amd64 arm64; do \
			EXT=""; \
			if [ "$$os" = "windows" ]; then EXT=".exe"; fi; \
			GOOS=$$os GOARCH=$$arch go build -o $(DIST_DIR)/$(APP_NAME)$$EXT main.go; \
			tar -czvf $(DIST_DIR)/$(APP_NAME)-$$os-$$arch.tgz -C $(DIST_DIR) $(APP_NAME)$$EXT; \
			zip -j $(DIST_DIR)/$(APP_NAME)-$$os-$$arch.zip $(DIST_DIR)/$(APP_NAME)$$EXT; \
		done; \
	done
	@echo "All distributions created in the $(DIST_DIR) directory."

docs: ## Serve Go documentation locally
	@echo "Serving Go documentation at http://localhost:6060..."
	@echo "Press Ctrl+C to stop."
	@open http://localhost:6060/pkg/$(shell go list -m)/ || xdg-open http://localhost:6060/pkg/$(shell go list -m)/ || echo "Open http://localhost:6060/pkg/$(shell go list -m)/ manually in your browser."
	godoc -http=:6060
