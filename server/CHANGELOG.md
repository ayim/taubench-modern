# Sema4.ai Agent Server 1.2.0 (2024-03-19)

## Agent Server

### Features

- Added Cortex AI as a new LLM provider in Agent Server
- Added end-to-end tool calling support (with parallel tool call support) for Cortex AI
- Added Agent Server as a binary deliverable for Studio and ACE platforms
- Added file support in Agent Server that enables Actions to access files in ACE and Studio

### Performance and Configuration Enhancements

- Added configurable log backup settings through environment variables
- Improved internationalization support with proper UTF-8 encoding for runbooks
- Added proper initialization of lifespan in root FastAPI app
- Enhanced agent-server executable binary handling with new startup features:
  - Parent process monitoring: Server can now exit when its parent process exits
  - Data directory locking: Prevents multiple instances from running in the same directory
  - Lock management: Option to forcefully terminate existing instances if needed

### Infrastructure and Build Process

- Improved build process with better PyInstaller integration and logging
- Streamlined build and release workflows
- Fixed macOS binary execution and signing issues

### File Management Improvements

- Fixed file upload confirmation process
- Added new endpoint for downloading files by reference
- Added control for file embedding during uploads
- Added embedding support for Cortex platform

### Bug Fixes

- Fixed streaming issues with empty tool calls
- Resolved authentication problems with User field
- Fixed PostgreSQL migration issues on startup
- Improved tool call processing for Claude Refactor
- Removed /openapi.json endpoint
- Updated Cortex context window limit to 200k
- Fixed agent package import failures on Windows when runbooks contain non-ASCII characters

## Public API

### Features

- Added new public API endpoints
- Implemented dedicated public API at `/api/public/v1` for Agents

## Private API

No significant changes.