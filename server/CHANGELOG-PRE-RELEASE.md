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
