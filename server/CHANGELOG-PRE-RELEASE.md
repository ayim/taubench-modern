# Sema4.ai Agent Server Pre-Release 2.0.0-beta.2 (2025-05-23)

## Agent Server

### Bugfixes

- Increase tool definition caching sophistication (for MCP and Action servers); allow clients to disable tool caching using the SEMA4AI_AGENT_SERVER_TOOL_CACHE_ENABLED=false environment variable. ([GPT-858](https://linear.app/sema4ai/issue/GPT-858))
- Made tool error handling more reliable with clearer error messages when tools encounter problems during execution ([GPT-860](https://linear.app/sema4ai/issue/GPT-860))
- Use env variables to setup langsmith for back compat ([GPT-865](https://linear.app/sema4ai/issue/GPT-865))
- Fixed issue where Agent Server wouldn't start because it presumed a port was being used while it was actually free. ([GPT-870](https://linear.app/sema4ai/issue/GPT-870))

### Improved Documentation

- Added vscode launch profile for testing jwt local and postgres config

### Additional Information Not Pertinent to Client Users

- [GPT-866](https://linear.app/sema4ai/issue/GPT-866), [GPT-866](https://linear.app/sema4ai/issue/GPT-866)


## Public API

No significant changes.


## Private API

### Features

- Add PUT /threads api ([GPT-861](https://linear.app/sema4ai/issue/GPT-861))
- Patch openapi spec with an endpoint for websocket streaming

### Bugfixes

- Fix missing model name for legacy api ([GPT-864](https://linear.app/sema4ai/issue/GPT-864))
- Fixed file upload errors that could occur when files were successfully uploaded but the system incorrectly reported them as failed ([GPT-868](https://linear.app/sema4ai/issue/GPT-868))


# Sema4.ai Agent Server Pre-Release 2.0.0-beta.1 (2025-05-21)

## Agent Server

### Features

- Faster agent-server startup, no longer leaving leftover files in temp dir when agent-server is killed (using go-wrapper instead of pyinstaller --onefile mode). ([GPT-854](https://linear.app/sema4ai/issue/GPT-854))

### Bugfixes

- Fix for cortex authentication: some internal configuration changes altered expected contract between us, Studio, space-client, etc. This PR introduces a fix and more logging for future troubleshooting. ([GPT-856](https://linear.app/sema4ai/issue/GPT-856))

### Miscellaneous

- Code formatting for non-python files (.json, .yaml, .ts, .tsx, .md) with prettier. ([GPT-855](https://linear.app/sema4ai/issue/GPT-855))


## Public API

No significant changes.


## Private API

No significant changes.


# Sema4.ai Agent Server Pre-Release 2.0.0-beta (2025-05-20)

## Agent Server

### Bugfixes

- Disconnect handled more carefully now for clients using WebSocket streaming; Bedrock platform parameters serialization/deserialization upgraded for robustness ([GPT-844](https://linear.app/sema4ai/issue/GPT-844))
- Increase test robustness by checking in test data file instead of fetching it ([GPT-847](https://linear.app/sema4ai/issue/GPT-847))
- Use polling API to interact with Reducto. ([GPT-851](https://linear.app/sema4ai/issue/GPT-851))
- Token counting now gracefully handles invalid model names by falling back to a default model instead of failing with an error ([GPT-853](https://linear.app/sema4ai/issue/GPT-853))

### Miscellaneous

- Improved reliability when processing large documents and tool outputs by automatically preserving the most important information while avoiding model context limits. ([GPT-842](https://linear.app/sema4ai/issue/GPT-842))
- Adds classify prompt for Reducto


## Public API

No significant changes.


## Private API

### Features

- Surface MCP servers in package endpoint

### Bugfixes

- Adding action context headers required for Ace integration
- url join strips the last segment


# Sema4.ai Agent Server Pre-Release 2.0.0-alpha.13 (2025-05-14)

## Agent Server

No significant changes.


## Public API

No significant changes.


## Private API

No significant changes.


# Sema4.ai Agent Server Pre-Release 2.0.0-alpha.12 (2025-05-14)

## Agent Server

### Bugfixes

- Fix typo in package endpoint; cache tools and add /api/v2/agents/{aid}/refresh-tools ([GPT-843](https://linear.app/sema4ai/issue/GPT-843))

### Additional Information Not Pertinent to Client Users

- [GPT-839](https://linear.app/sema4ai/issue/GPT-839)


## Public API

No significant changes.


## Private API

No significant changes.


# Sema4.ai Agent Server Pre-Release 2.0.0-alpha.11 (2025-05-14)

## Agent Server

No significant changes.


## Public API

No significant changes.


## Private API

No significant changes.


# Sema4.ai Agent Server Pre-Release 2.0.0-alpha.10 (2025-05-14)

## Agent Server

### Miscellaneous

- Start of Agent Server v2 changelog in the Agent Platform repo! ([GPT-839](https://linear.app/sema4ai/issue/GPT-839))


## Public API

No significant changes.


## Private API

No significant changes.
