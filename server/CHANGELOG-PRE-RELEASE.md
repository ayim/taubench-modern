# Sema4.ai Agent Server Pre-Release 2.0.2-alpha (2025-06-16)

## Agent Server

### Features

- Adding new quality benchmarking project for assessing quality of agents in aggregate ([GPT-923](https://linear.app/sema4ai/issue/GPT-923))
- Update the events infrastructure to prepare for the concept of client-side tools and further clarify the separation between incoming and outgoing events. ([GPT-966](https://linear.app/sema4ai/issue/GPT-966))
- Support client-side tools (and tag tool defs with their category so we know if they're actions, or from MCP servers, or client-side, etc.) ([GPT-971](https://linear.app/sema4ai/issue/GPT-971))

### Bugfixes

- Converted ResponseToolUseContent messages in LangSmith traces to tool calls rendered by LangSmith. ([GPT-903](https://linear.app/sema4ai/issue/GPT-903))
- Implemented ConditionalLangSmithProcessor to route LangSmith traces to the right exporters for a given configuration. ([GPT-972](https://linear.app/sema4ai/issue/GPT-972))
- Use Control Room User ID instead of internal user ID while emitting OTEL events ([GPT-975](https://linear.app/sema4ai/issue/GPT-975))

### Removals and Deprecations

- Removed llm.model and llm.provider attributes from OTEL events to be added back at a later date. ([GPT-936](https://linear.app/sema4ai/issue/GPT-936))

### Miscellaneous

- Added check for LangSmith env vars to use as a global config over agent config. ([GPT-988](https://linear.app/sema4ai/issue/GPT-988))

### Additional Information Not Pertinent to Client Users

- [GPT-973](https://linear.app/sema4ai/issue/GPT-973), [GPT-978](https://linear.app/sema4ai/issue/GPT-978), [GPT-990](https://linear.app/sema4ai/issue/GPT-990)


## Public API

### Features

- Add auth to MCP endpoints ([GPT-911](https://linear.app/sema4ai/issue/GPT-911))
- Typescript Public SDK - surface endpoint for streaming conversations

### Bugfixes

- Remove trailing slash to make it compatible with legacy api

### Miscellaneous

- Change public api prefix to v1


## Private API

### Features

- Add POST /tid/fork endpoint to fork thread messages ([GPT-907](https://linear.app/sema4ai/issue/GPT-907))
- Implement edit thread message endpoint ([GPT-908](https://linear.app/sema4ai/issue/GPT-908))
- Allow the prompt endpoint to take either a platform_config_raw (as it does today) or an agent_id or a thread_id; if agent or thread IDs are provided, the endpoint will grab the first platform config from the agent (or agent associated with the thread). ([GPT-921](https://linear.app/sema4ai/issue/GPT-921))
- Add new ephemeral agent stream endpoint to private API (allows you to stream against an agent created in an ephemeral way --- not persisted to storage) ([GPT-967](https://linear.app/sema4ai/issue/GPT-967))

### Bugfixes

- Added sync and async endpoints to Typescript SDK.


# Sema4.ai Agent Server Pre-Release 2.0.1-alpha (2025-06-06)

## Agent Server

### Bugfixes

- Restore INSERT .. ON CONFLICT logic to match agentserver v1 to try to mitigate a files issue in ACE ([GPT-938](https://linear.app/sema4ai/issue/GPT-938))

### Additional Information Not Pertinent to Client Users

- [GPT-959](https://linear.app/sema4ai/issue/GPT-959)


## Public API

### Features

- Porting public API to v2: sse streaming for agent conversations. ([GPT-913](https://linear.app/sema4ai/issue/GPT-913))


## Private API

### Bugfixes

- Fix package import failing to handle UNSET legacy Azure fields correctly ([GPT-964](https://linear.app/sema4ai/issue/GPT-964))


# Sema4.ai Agent Server Pre-Release 2.0.0-rc.4 (2025-06-06)

## Agent Server

### Bugfixes

- Modify attributes emitted in OTEL spans so ACE does not block them. ([GPT-936](https://linear.app/sema4ai/issue/GPT-936))
- Restore INSERT .. ON CONFLICT logic to match agentserver v1 to try to mitigate a files issue in ACE ([GPT-938](https://linear.app/sema4ai/issue/GPT-938))

### Additional Information Not Pertinent to Client Users

- [GPT-962](https://linear.app/sema4ai/issue/GPT-962)


## Public API

### Features

- Porting public API to v2: sse streaming for agent conversations. ([GPT-913](https://linear.app/sema4ai/issue/GPT-913))


## Private API

No significant changes.


# Sema4.ai Agent Server Pre-Release 2.0.0-rc.3 (2025-06-06)

## Agent Server

### Bugfixes

- Restore INSERT .. ON CONFLICT logic to match agentserver v1 to try to mitigate a files issue in ACE ([GPT-938](https://linear.app/sema4ai/issue/GPT-938))
- Revert locking changes in LangSmithContext and updated collector url checking in telemtry. ([GPT-960](https://linear.app/sema4ai/issue/GPT-960))


## Public API

### Features

- Porting public API to v2: sse streaming for agent conversations. ([GPT-913](https://linear.app/sema4ai/issue/GPT-913))


## Private API

No significant changes.


# Sema4.ai Agent Server Pre-Release 2.0.0-rc.2 (2025-06-06)

## Agent Server

### Bugfixes

- Restore INSERT .. ON CONFLICT logic to match agentserver v1 to try to mitigate a files issue in ACE ([GPT-938](https://linear.app/sema4ai/issue/GPT-938))
- Clean up OTEL logs to remove logs related to 409 conflicts and warnings. ([GPT-956](https://linear.app/sema4ai/issue/GPT-956))
- Fixed action metadata not coming through for more complex action definitions ([GPT-957](https://linear.app/sema4ai/issue/GPT-957))

### Additional Information Not Pertinent to Client Users

- [GPT-927](https://linear.app/sema4ai/issue/GPT-927)


## Public API

### Features

- Porting public API to v2: sse streaming for agent conversations. ([GPT-913](https://linear.app/sema4ai/issue/GPT-913))

### Miscellaneous

- Public API v1 tweaks, cleanup, and some observations while testing agent connector.


## Private API

No significant changes.


# Sema4.ai Agent Server Pre-Release 2.0.0-rc.1 (2025-06-05)

## Agent Server

### Bugfixes

- Restore INSERT .. ON CONFLICT logic to match agentserver v1 to try to mitigate a files issue in ACE ([GPT-938](https://linear.app/sema4ai/issue/GPT-938))
- Fix handling of whitelist for separate action packages on same server ([GPT-950](https://linear.app/sema4ai/issue/GPT-950))
- A faulty env variable was changed to make cloud file manager tests work again. Also, the cloud server file had its request parameters changed. ([GPT-951](https://linear.app/sema4ai/issue/GPT-951))

### Additional Information Not Pertinent to Client Users

- [GPT-939](https://linear.app/sema4ai/issue/GPT-939)


## Public API

### Features

- Porting public API to v2: sse streaming for agent conversations. ([GPT-913](https://linear.app/sema4ai/issue/GPT-913))
- Typescript SDK for public API


## Private API

### Features

- Update Typescript SDK to 2.0.0-rc.

### Bugfixes

- Missing thread rename support; current UX uses GET and PUT but after we stopped sending thread message contents, this pattern leads to deleting thread messages on rename! ([GPT-952](https://linear.app/sema4ai/issue/GPT-952))
- Messages are not persisted when a file is created


# Sema4.ai Agent Server Pre-Release 2.0.0-rc (2025-06-04)

## Agent Server

No significant changes.


## Public API

No significant changes.


## Private API

### Bugfixes

- Missing endpoints for file uploading; porting from v1 to v2.


# Sema4.ai Agent Server Pre-Release 2.0.0-beta.9 (2025-06-04)

## Agent Server

No significant changes.


## Public API

No significant changes.


## Private API

### Bugfixes

- Bug fix in the route name ([GPT-928](https://linear.app/sema4ai/issue/GPT-928))

### Miscellaneous

- improve type tests for v1 compatibility in Typescript SDK


# Sema4.ai Agent Server Pre-Release 2.0.0-beta.8 (2025-06-04)

## Agent Server

### Bugfixes

- Backup prompt to ensure output format adherance updated to also pass tools (shouldn't be necessary, but Cortex seems to need it) ([GPT-942](https://linear.app/sema4ai/issue/GPT-942))


## Public API

No significant changes.


## Private API

No significant changes.


# Sema4.ai Agent Server Pre-Release 2.0.0-beta.7 (2025-06-03)

## Agent Server

### Features

- Added OTEL counters for token usage with attributes for filtering. ([GPT-901](https://linear.app/sema4ai/issue/GPT-901))
- Implemented a comprehensive metrics observability stack using Prometheus and Jaeger for our OTEL setup. ([GPT-930](https://linear.app/sema4ai/issue/GPT-930))

### Bugfixes

- Prompt scaffold and step parsing upgrades for robustness in default agent arch ([GPT-918](https://linear.app/sema4ai/issue/GPT-918))
- Correct uniqueness constraint over file uploads to allow the same filename to be uploaded across threads in an agent. ([GPT-938](https://linear.app/sema4ai/issue/GPT-938))
- Second round of prompt scaffold updates; Gemini still shaky, other platforms should have improved behavior in less looping and more consistent correct use of tools. ([GPT-940](https://linear.app/sema4ai/issue/GPT-940))

### Improved Documentation

- Added developer guide and updated the readme for recent changes

### Miscellaneous

- Improving otel with message counter ([GPT-915](https://linear.app/sema4ai/issue/GPT-915))
- OTEL: Remove 'user' field from OTEL logs implementation ([GPT-915](https://linear.app/sema4ai/issue/GPT-915))
- Remove old collector files and create new make targets for observability purporses ([GPT-930](https://linear.app/sema4ai/issue/GPT-930))
- Updates to the Makefile and README to list all make targets. ([GPT-937](https://linear.app/sema4ai/issue/GPT-937))
- More tests for files fixes ([GPT-941](https://linear.app/sema4ai/issue/GPT-941))


## Public API

### Features

- Porting public API to v2. ([GPT-913](https://linear.app/sema4ai/issue/GPT-913), [GPT-913](https://linear.app/sema4ai/issue/GPT-913))


## Private API

### Features

- Implement async invoke endpoint in runs ([GPT-928](https://linear.app/sema4ai/issue/GPT-928))
- Implement GET run status endpoint ([GPT-928](https://linear.app/sema4ai/issue/GPT-928))

### Bugfixes

- Ignore thread messages from all GET thread endpoints ([GPT-885](https://linear.app/sema4ai/issue/GPT-885))
- Hide sensitive variables from get agents api and post agents api ([GPT-886](https://linear.app/sema4ai/issue/GPT-886))
- Roundtripping of legacy worker config was broken, fix and tests introduced ([GPT-934](https://linear.app/sema4ai/issue/GPT-934))
- Fix masking: /agents/{aid}/raw needs to _not_ mask sensitive info ([GPT-935](https://linear.app/sema4ai/issue/GPT-935))
- Hotfix to include in UploadedFile structure so that the GET file-by-ref endpoint works. ([GPT-939](https://linear.app/sema4ai/issue/GPT-939))


# Sema4.ai Agent Server Pre-Release 2.0.0-beta.6 (2025-06-02)

## Agent Server

### Features

- Add sema4ai otel metrics.

### Bugfixes

- Fix tool call rendering in LangSmith input history. ([GPT-876](https://linear.app/sema4ai/issue/GPT-876))
- Migrations for Cortex agents and threads may be missing a few small things; fixed migrations for these niche cases. ([GPT-917](https://linear.app/sema4ai/issue/GPT-917))

### Additional Information Not Pertinent to Client Users

- [GPT-920](https://linear.app/sema4ai/issue/GPT-920)


## Public API

No significant changes.


## Private API

### Bugfixes

- When agent is created via package endpoint, mode is always conversational and worker agent metadata are lost.


# Sema4.ai Agent Server Pre-Release 2.0.0-beta.5 (2025-05-30)

## Agent Server

### Features

- Improved conversation management with smart content truncation: When conversations become too long for the AI model, the system now intelligently manages content by selectively truncating tool outputs rather than cutting all content equally. Larger tool outputs are reduced more than smaller ones, ensuring important conversation context is preserved while maintaining readability. This results in better conversation quality and more predictable behavior when dealing with long threads containing extensive tool results. ([GPT-849](https://linear.app/sema4ai/issue/GPT-849))
- Added token usage information for OpenAI and Azure OpenAI Platform Clients ([GPT-909](https://linear.app/sema4ai/issue/GPT-909))

### Bugfixes

- Update json parsing for action-server response and check for MCP result. ([GPT-869](https://linear.app/sema4ai/issue/GPT-869))
- Enable propagation of token usage information to LangSmith ([GPT-877](https://linear.app/sema4ai/issue/GPT-877))
- Fix to get parallel tool calls operational for Cortex platform client, parsing was sligtly off. New test and fresh VCR fixtures to verify fix. ([GPT-910](https://linear.app/sema4ai/issue/GPT-910))

### Miscellaneous

- Updated debug widget used for quick internal testing to have fresh build of widget UX and more recent deps. ([GPT-898](https://linear.app/sema4ai/issue/GPT-898))
- Move orchestrator repo for our integration tests in. Misc, should have no downstream effects, purely for ease of testing and to unblock Codex setup. ([GPT-904](https://linear.app/sema4ai/issue/GPT-904))


## Public API

No significant changes.


## Private API

### Bugfixes

- Make threads name filter case insensitive ([GPT-893](https://linear.app/sema4ai/issue/GPT-893))


# Sema4.ai Agent Server Pre-Release 2.0.0-beta.4 (2025-05-29)

## Agent Server

### Features

- Updated approximate token counting to use a fast heuristic method by default instead of tiktoken. Set SEMA4AI_AGENT_SERVER_TOKEN_COUNTING_ENABLE_TIKTOKEN=true to restore tiktoken-based counting or use the similar configuration option. ([GPT-891](https://linear.app/sema4ai/issue/GPT-891))

### Bugfixes

- Improved error handling for action server tools that return errors in the {result: None, error: message} format. Users will now see clear error messages when external tools fail rather than receiving malformed responses or generic errors. ([GPT-867](https://linear.app/sema4ai/issue/GPT-867))
- More robust output format parsing to convert LLM replies into thoughts/responses/processing status. Prompt changes to come in a separate PR. Before prompt changes are in, this still wont be quite enough to solve the behavior we're seeing, but it's a start. ([GPT-883](https://linear.app/sema4ai/issue/GPT-883))

### Additional Information Not Pertinent to Client Users

- [GPT-889](https://linear.app/sema4ai/issue/GPT-889), [GPT-890](https://linear.app/sema4ai/issue/GPT-890)


## Public API

No significant changes.


## Private API

### Features

- Trace name in LangSmith has been changed to the thread name for better searchability. Added new metadata as well. ([GPT-879](https://linear.app/sema4ai/issue/GPT-879))
- Update Typescript Client with spec 2.0.0-beta.3.

### Miscellaneous

- Start foundational work for patching types that are not correctly generated by tools


# Sema4.ai Agent Server Pre-Release 2.0.0-beta.3 (2025-05-27)

## Agent Server

### Bugfixes

- Fixed an issue where results from tools could be reports as malformed when they are not. ([GPT-875](https://linear.app/sema4ai/issue/GPT-875))
- Increased the default maximum content limit when truncation is triggered on long tool results to approximately 10,000 tokens. ([GPT-882](https://linear.app/sema4ai/issue/GPT-882))

### Miscellaneous

- Fixes some dev related settings and a broken integration tests. Nothing user facing.
- If the agent server binary does not exist, the built Docker image is broken because curl does not fail and we don't know in advance that no actual file was downloaded. We change the Dockerfile in order to fail early and not ship broken images.


## Public API

No significant changes.


## Private API

### Bugfixes

- agents are wrongly created with conversational mode even if worker mode is specified ([GPT-872](https://linear.app/sema4ai/issue/GPT-872))
- Action invocation user id should be control room `user_id` and not the database `id`.
- Expires for presigned urls are controlled by Ace. Agent Platorm side we should always refresh the url otherwise we may found out that a cached url is already expired.


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
