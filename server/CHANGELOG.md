# Sema4.ai Agent Server 2.0.0 (2025-06-06)

## Agent Server

### Features

- Improved conversation management with smart content truncation: When conversations become too long for the AI model, the system now intelligently manages content by selectively truncating tool outputs rather than cutting all content equally. Larger tool outputs are reduced more than smaller ones, ensuring important conversation context is preserved while maintaining readability. This results in better conversation quality and more predictable behavior when dealing with long threads containing extensive tool results. ([GPT-849](https://linear.app/sema4ai/issue/GPT-849))
- Faster agent-server startup, no longer leaving leftover files in temp dir when agent-server is killed (using go-wrapper instead of pyinstaller --onefile mode). ([GPT-854](https://linear.app/sema4ai/issue/GPT-854))
- Automatically upgrade existing agents and conversations to the latest format on server startup. Users will not need to take any action - existing agents and conversations should continue to work as expected. ([GPT-862](https://linear.app/sema4ai/issue/GPT-862))
- Updated approximate token counting to use a fast heuristic method by default instead of tiktoken. Set SEMA4AI_AGENT_SERVER_TOKEN_COUNTING_ENABLE_TIKTOKEN=true to restore tiktoken-based counting or use the similar configuration option. ([GPT-891](https://linear.app/sema4ai/issue/GPT-891))
- Added OTEL counters for token usage with attributes for filtering. ([GPT-901](https://linear.app/sema4ai/issue/GPT-901))
- Added token usage information for OpenAI and Azure OpenAI Platform Clients ([GPT-909](https://linear.app/sema4ai/issue/GPT-909))
- Implemented a comprehensive metrics observability stack using Prometheus and Jaeger for our OTEL setup. ([GPT-930](https://linear.app/sema4ai/issue/GPT-930))
- Add sema4ai otel metrics.

### Bugfixes

- Fix typo in package endpoint; cache tools and add /api/v2/agents/{aid}/refresh-tools ([GPT-843](https://linear.app/sema4ai/issue/GPT-843))
- Disconnect handled more carefully now for clients using WebSocket streaming; Bedrock platform parameters serialization/deserialization upgraded for robustness ([GPT-844](https://linear.app/sema4ai/issue/GPT-844))
- Increase test robustness by checking in test data file instead of fetching it ([GPT-847](https://linear.app/sema4ai/issue/GPT-847))
- Use polling API to interact with Reducto. ([GPT-851](https://linear.app/sema4ai/issue/GPT-851))
- Token counting now gracefully handles invalid model names by falling back to a default model instead of failing with an error ([GPT-853](https://linear.app/sema4ai/issue/GPT-853))
- Fix for cortex authentication: some internal configuration changes altered expected contract between us, Studio, space-client, etc. This PR introduces a fix and more logging for future troubleshooting. ([GPT-856](https://linear.app/sema4ai/issue/GPT-856))
- Increase tool definition caching sophistication (for MCP and Action servers); allow clients to disable tool caching using the SEMA4AI_AGENT_SERVER_TOOL_CACHE_ENABLED=false environment variable. ([GPT-858](https://linear.app/sema4ai/issue/GPT-858))
- Made tool error handling more reliable with clearer error messages when tools encounter problems during execution ([GPT-860](https://linear.app/sema4ai/issue/GPT-860))
- Use env variables to setup langsmith for back compat ([GPT-865](https://linear.app/sema4ai/issue/GPT-865))
- Improved error handling for action server tools that return errors in the {result: None, error: message} format. Users will now see clear error messages when external tools fail rather than receiving malformed responses or generic errors. ([GPT-867](https://linear.app/sema4ai/issue/GPT-867))
- Update json parsing for action-server response and check for MCP result. ([GPT-869](https://linear.app/sema4ai/issue/GPT-869))
- Fixed issue where Agent Server wouldn't start because it presumed a port was being used while it was actually free. ([GPT-870](https://linear.app/sema4ai/issue/GPT-870))
- Fixed an issue where results from tools could be reports as malformed when they are not. ([GPT-875](https://linear.app/sema4ai/issue/GPT-875))
- Fix tool call rendering in LangSmith input history. ([GPT-876](https://linear.app/sema4ai/issue/GPT-876))
- Enable propagation of token usage information to LangSmith ([GPT-877](https://linear.app/sema4ai/issue/GPT-877))
- Increased the default maximum content limit when truncation is triggered on long tool results to approximately 10,000 tokens. ([GPT-882](https://linear.app/sema4ai/issue/GPT-882))
- More robust output format parsing to convert LLM replies into thoughts/responses/processing status. Prompt changes to come in a separate PR. Before prompt changes are in, this still wont be quite enough to solve the behavior we're seeing, but it's a start. ([GPT-883](https://linear.app/sema4ai/issue/GPT-883))
- Fix to get parallel tool calls operational for Cortex platform client, parsing was sligtly off. New test and fresh VCR fixtures to verify fix. ([GPT-910](https://linear.app/sema4ai/issue/GPT-910))
- Migrations for Cortex agents and threads may be missing a few small things; fixed migrations for these niche cases. ([GPT-917](https://linear.app/sema4ai/issue/GPT-917))
- Prompt scaffold and step parsing upgrades for robustness in default agent arch ([GPT-918](https://linear.app/sema4ai/issue/GPT-918))
- Modify attributes emitted in OTEL spans so ACE does not block them. ([GPT-936](https://linear.app/sema4ai/issue/GPT-936))
- Correct uniqueness constraint over file uploads to allow the same filename to be uploaded across threads in an agent. ([GPT-938](https://linear.app/sema4ai/issue/GPT-938))
- Second round of prompt scaffold updates; Gemini still shaky, other platforms should have improved behavior in less looping and more consistent correct use of tools. ([GPT-940](https://linear.app/sema4ai/issue/GPT-940))
- Backup prompt to ensure output format adherance updated to also pass tools (shouldn't be necessary, but Cortex seems to need it) ([GPT-942](https://linear.app/sema4ai/issue/GPT-942))
- Fix handling of whitelist for separate action packages on same server ([GPT-950](https://linear.app/sema4ai/issue/GPT-950))
- A faulty env variable was changed to make cloud file manager tests work again. Also, the cloud server file had its request parameters changed. ([GPT-951](https://linear.app/sema4ai/issue/GPT-951))
- Clean up OTEL logs to remove logs related to 409 conflicts and warnings. ([GPT-956](https://linear.app/sema4ai/issue/GPT-956))
- Fixed action metadata not coming through for more complex action definitions ([GPT-957](https://linear.app/sema4ai/issue/GPT-957))
- Revert locking changes in LangSmithContext and updated collector url checking in telemtry. ([GPT-960](https://linear.app/sema4ai/issue/GPT-960))

### Improved Documentation

- Added developer guide and updated the readme for recent changes
- Added vscode launch profile for testing jwt local and postgres config

### Miscellaneous

- Start of Agent Server v2 changelog in the Agent Platform repo! ([GPT-839](https://linear.app/sema4ai/issue/GPT-839))
- Improved reliability when processing large documents and tool outputs by automatically preserving the most important information while avoiding model context limits. ([GPT-842](https://linear.app/sema4ai/issue/GPT-842))
- Code formatting for non-python files (.json, .yaml, .ts, .tsx, .md) with prettier. ([GPT-855](https://linear.app/sema4ai/issue/GPT-855))
- Updated debug widget used for quick internal testing to have fresh build of widget UX and more recent deps. ([GPT-898](https://linear.app/sema4ai/issue/GPT-898))
- Move orchestrator repo for our integration tests in. Misc, should have no downstream effects, purely for ease of testing and to unblock Codex setup. ([GPT-904](https://linear.app/sema4ai/issue/GPT-904))
- Improving otel with message counter ([GPT-915](https://linear.app/sema4ai/issue/GPT-915))
- OTEL: Remove 'user' field from OTEL logs implementation ([GPT-915](https://linear.app/sema4ai/issue/GPT-915))
- Remove old collector files and create new make targets for observability purporses ([GPT-930](https://linear.app/sema4ai/issue/GPT-930))
- Updates to the Makefile and README to list all make targets. ([GPT-937](https://linear.app/sema4ai/issue/GPT-937))
- More tests for files fixes ([GPT-941](https://linear.app/sema4ai/issue/GPT-941))
- Adds classify prompt for Reducto
- Fixes some dev related settings and a broken integration tests. Nothing user facing.
- If the agent server binary does not exist, the built Docker image is broken because curl does not fail and we don't know in advance that no actual file was downloaded. We change the Dockerfile in order to fail early and not ship broken images.

### Additional Information Not Pertinent to Client Users

- [GPT-839](https://linear.app/sema4ai/issue/GPT-839), [GPT-866](https://linear.app/sema4ai/issue/GPT-866), [GPT-866](https://linear.app/sema4ai/issue/GPT-866), [GPT-889](https://linear.app/sema4ai/issue/GPT-889), [GPT-890](https://linear.app/sema4ai/issue/GPT-890), [GPT-920](https://linear.app/sema4ai/issue/GPT-920), [GPT-927](https://linear.app/sema4ai/issue/GPT-927), [GPT-939](https://linear.app/sema4ai/issue/GPT-939), [GPT-962](https://linear.app/sema4ai/issue/GPT-962)


## Public API

### Features

- Porting public API to v2. ([GPT-913](https://linear.app/sema4ai/issue/GPT-913), [GPT-913](https://linear.app/sema4ai/issue/GPT-913))
- Typescript SDK for public API

### Miscellaneous

- Public API v1 tweaks, cleanup, and some observations while testing agent connector.


## Private API

### Features

- Add PUT /threads api ([GPT-861](https://linear.app/sema4ai/issue/GPT-861))
- Trace name in LangSmith has been changed to the thread name for better searchability. Added new metadata as well. ([GPT-879](https://linear.app/sema4ai/issue/GPT-879))
- Implement async invoke endpoint in runs ([GPT-928](https://linear.app/sema4ai/issue/GPT-928))
- Implement GET run status endpoint ([GPT-928](https://linear.app/sema4ai/issue/GPT-928))
- Patch openapi spec with an endpoint for websocket streaming
- Surface MCP servers in package endpoint
- Update Typescript Client with spec 2.0.0-beta.3.
- Update Typescript SDK to 2.0.0-rc.

### Bugfixes

- Fix missing model name for legacy api ([GPT-864](https://linear.app/sema4ai/issue/GPT-864))
- Fixed file upload errors that could occur when files were successfully uploaded but the system incorrectly reported them as failed ([GPT-868](https://linear.app/sema4ai/issue/GPT-868))
- agents are wrongly created with conversational mode even if worker mode is specified ([GPT-872](https://linear.app/sema4ai/issue/GPT-872))
- Ignore thread messages from all GET thread endpoints ([GPT-885](https://linear.app/sema4ai/issue/GPT-885))
- Hide sensitive variables from get agents api and post agents api ([GPT-886](https://linear.app/sema4ai/issue/GPT-886))
- Make threads name filter case insensitive ([GPT-893](https://linear.app/sema4ai/issue/GPT-893))
- Bug fix in the route name ([GPT-928](https://linear.app/sema4ai/issue/GPT-928))
- Roundtripping of legacy worker config was broken, fix and tests introduced ([GPT-934](https://linear.app/sema4ai/issue/GPT-934))
- Fix masking: /agents/{aid}/raw needs to _not_ mask sensitive info ([GPT-935](https://linear.app/sema4ai/issue/GPT-935))
- Hotfix to include in UploadedFile structure so that the GET file-by-ref endpoint works. ([GPT-939](https://linear.app/sema4ai/issue/GPT-939))
- Missing thread rename support; current UX uses GET and PUT but after we stopped sending thread message contents, this pattern leads to deleting thread messages on rename! ([GPT-952](https://linear.app/sema4ai/issue/GPT-952))
- Action invocation user id should be control room `user_id` and not the database `id`.
- Adding action context headers required for Ace integration
- Expires for presigned urls are controlled by Ace. Agent Platorm side we should always refresh the url otherwise we may found out that a cached url is already expired.
- Messages are not persisted when a file is created
- Missing endpoints for file uploading; porting from v1 to v2.
- When agent is created via package endpoint, mode is always conversational and worker agent metadata are lost.
- url join strips the last segment

### Miscellaneous

- Start foundational work for patching types that are not correctly generated by tools
- improve type tests for v1 compatibility in Typescript SDK
