# @sema4ai/spar-ui

## 0.15.0

### Minor Changes

- d2afade: add data transformation lib in DocIntel UI

### Patch Changes

- e2cbbc2: Allow to use DI parse results in conversation
- adc42ae: chore/add oauth_config support to MCP Server update endpoint
- 8ad2613: Preserve current active Chat sidebar when navigating between threads or workitems

## 0.14.0

### Minor Changes

- d581cfe: cleaner API for schema handling in DocIntel UI

### Patch Changes

- e9bd76e: Copy text edits for SDM UIs
- 1df130f: Make Semantic Data Model database connection "Change Connection" action more prominent

## 0.13.4

### Patch Changes

- b007e49: Display tooltips for longer filenames in Files sidepanel
- 93f13cd: Formatting and linting
- a9f7e3c: Add telemetry for SDM events.
- b007e49: Enforce 20Mb file size limit for file-based SDMs

## 0.13.3

### Patch Changes

- dc21781: chore: move ServerRequest and ServerResponse to agent-server-interface and deprecate them on spar-ui
- 2e0a87c: Hide transport and authentication fields for hosted MCP servers in EditMcpServerDialog. Add secret visibility toggle to ActionSecrets component.
- 0899ab2: Add relationships field to DataConnectionFormSchema and export Relationship type
- 0a91465: refactor: improve types and relocate queries and utils

## 0.13.2

### Patch Changes

- 524b8a3: fix: mcp oauth secret input not showing visibility toggle

## 0.13.1

### Patch Changes

- ec63750: fix: handle redacted OAuth credentials in MCP server edit dialog

## 0.13.0

### Minor Changes

- e757a39: check if extract, regenerate schema is running before closing dialog window

### Patch Changes

- d1e94ca: Show error details for Semantic Data Models data connection validation
- 66ee62b: Fix permission check for Semantic Data Model data connection configuration feature
- 15e7d6e: Add MCP create and edit dialogs

## 0.12.0

### Minor Changes

- ba6ed24: Fix non-PDF Document Intelligence UI messaging and layout

### Patch Changes

- d470b4a: Render DIv2 extractet results in chat conversation
- c402f4b: Fixing an issue where rows with optional/different fields weren't rendering properly in tables
- 9804b37: Rename schema regeneration in DIv2
- 65e7ee7: Parese and generate schema in DIv2 by file reference

## 0.11.0

### Minor Changes

- dfa49e7: check for cached schema before generating new one
- 6a34ceb: Snowflake observability EAI banner for updating network rules
- 56616db: fix: bounding citations boxes not showing up in Parse only mode document
- 30b7fc5: render nested table data correctly in extraction results
- 44b4ded: Show more info on intermediate steps to determine if evals are slow or stalled.

### Patch Changes

- c775dcf: Show Data Connection details for Semantic Data Models
- 90803ed: Make Tool call inputs/outputs collapsible
- 2ae7115: Update agent package inspection types
- 03a5cd6: Update Semantic Data Model synonym edition to a tag list
- 980d402: Changed the main navigation sorting, icons and labels.

## 0.10.0

### Minor Changes

- 3695eaf: Show warning when Semantic Data Model has missing/unconfigured data connection
- 67859e0: Add schema-aware recursive path resolution to schema-lib
- fb3ef1b: Add button to delete all scenarios for an agent
- 9a72bdf: Update Document Intelligence UI Button validation and user feedback
- ad19967: Implement soft delete with restore and strikethrough UI for schema fields
- 4c087f8: fix: array fields not showing nested properties in schema editor

### Patch Changes

- bf96bbe: Fix Semantic Data Model re-generation bug with disappearing values after model edition
- d431db9: Fix DIv2 file list tooltips
- 2d09af6: Update rules on allowed work item restart
- 72482ff: [Non-prod] Violet agent components/hidden page update for new UI widgets
- eebf909: Duped component subtrees for Violet agent, non-prod. New metadata-update endpoint, not intended for wider use.
- d506ee6: Autoexpand error panel in case of system errors for eval trials
- 5b71156: Add inner-thread view for SQL generation via agent
- 04217a4: it allows more concurrent scenario runs
- a80ebf6: Fix Semantic Data Model missing Data Connection status report
- a12fc8f: Allow to regenerate DIv2 generated schema with instructions
- 97546ba: more fine grained analytics events
- c10c3c5: Added gpt-5-2 and gpt-5-1-codex-max (removed gpt-5-1 and regular gpt-5-1-codex)
- 5ff57ca: Fix DI dialog double copy actions
- acddb2f: Allow to send extracted DIv2 results to conversation
- d5fb684: Changed the main navigation sorting, icons and labels.

## 0.9.1

### Patch Changes

- f18bfac: Remove link to thread if trial is not in a terminal state
- 49df17a: Improve Semantic Data Model error reporting
- b2b3ba5: Fix Semantic Data Model multi sheet/table selection issues
- c6287e0: Data frame design spec updates
- 0419faf: Align architecture version with Studio convention
- 7b6dc50: Fix and refactor spar-ui tests

## 0.9.0

### Minor Changes

- 7f5862d: Added hidden "chat" page to talk to the new pre-installed agent in agent-server.
- 2b7ec12: Fix array field deletion bug and add schema-lib tests
  - Fix deletion of nested array fields to preserve array structure
  - Add 88 tests for schema-lib covering all API functions and edge cases
- 57684b6: Fix schema editor: enable nested field deletion in arrays and add cascading deletion UI

### Patch Changes

- 5c0d0bd: Provide only supported Data Connection types to Semantic Data Model creation dialog
- b9d0a59: Add possibility to enable and disable existing observability integration, fixing zod resolver for react-hook-form usages
- 8d7a7e3: Expose new extract-only UI for docint.
- b96ee53: Swap import/export evaluation icons
- 9676e5f: fix: remove reset filters from work items overview table
- 28c0202: Move Create Verified Query creation from Data Frames sidebar to Action envelope
- 701674e: Fix Semantic Data Model YAML file empty file reference does not trigger import
- 8581866: Optimize scenario run fetching during batch run
- f578a3b: chore: update border colors
- 7d7dd3b: Fix attachment rendering duplicates between threads

## 0.8.0

### Minor Changes

- 63ad632: Refactor DocIntel ExtractOnly components for better state management and DRY principles
  - Consolidate duplicate loading states into shared constants
  - Remove redundant state tracking (schemaResult, canReExtract, disabled prop)
  - Replace raw state setters with semantic actions (initializeFromExisting)
  - Improve "Add Field" UX with empty placeholder instead of auto-generated names
  - Remove unused mock data files
  - Add clear comments documenting state purpose

### Patch Changes

- 4cd62b7: Display Data Frames query in Tool Call result envelope
- 82aeba9: Update observability components to account for new REST API shape
- de14d40: Semantic Data model related view and functionality fixes

## 0.7.1

### Patch Changes

- e567e1c: Remove Semantic Data model background validation interval
- 3379e79: Semantic Data Model related layout fixes and updates
- 1780916: Include hidden UI for work-items execution
- 786dd8d: feat: add user facing metrics UI

## 0.7.0

### Minor Changes

- ec5f1a0: Fix `DataConnectionForm` to support Snowflake credential types

### Patch Changes

- 0995907: chore: hide chat input if evaluation thread
- 35a23ca: chore: add illustratoin to empty eval state and remove learn more link
- ad58d91: Update chat code block line height restrictions
- d91227b: adding Observability settings to SPAR Workroom, preserving original OTEL config state when switching back to original OTEL vendor
- defa2ae: Support boolean values in Data Frames
- defa2ae: Semantic Data Model related view layout fixes
- b08b015: Add error banner display in evaluation thread view for execution failures. Shows thread.metadata.evaluation_error when evaluation trials fail due to agent tool mismatches, configuration drift, or runtime errors.
- 26cb39e: Surface metadata field for batch runs
- 77b5c37: feat: add user facing metrics UI
- 3f656c2: Fix `RenameDialog` selecting the value on value changes
- fe8c3a4: chore: make evals sidebar texts copyable

## 0.6.0

### Minor Changes

- 56b4b29: Add icon to show when scenario/trial are throttled because of platform rate limits
- e760557: Added "plan card" that renders agent plans on messages w/ the right metadata. Plans only generated by new: experimental_2 architecture.
- f5471fc: Update Data Connections views to support required Studio functionallity

### Patch Changes

- f9912ee: fix: isolate expanded state between different eval runs
- d3164c8: Semantic Data Models related layout updates and fixes

## 0.5.0

### Minor Changes

- 2d4ab51: Added support for verified queries in the semantic data model.

### Patch Changes

- 7c262c5: ensuring more strict payload for observability integrations POST and PUT
- ffa7cd2: Fix some bugs in eval polling, UI got stuck on "running" state
- 81afbf3: Use a different endpoint to cancel eval batches

## 0.4.0

### Minor Changes

- 47da9a9: Show overall test results in evals
- a191a23: Send the thread ID along with the agent ID when validating semantic data models to allow files to be resolved as part of validation
- 5e27025: Allow to define the name of the Semantic Data Model name before model generation
- e475e96: Adding LiteLLM platform client
- e853a92: adding observability integration views and logic to handle API driven OTEL configurations in Agent Server
- 5ccd5b4: Consolidate the parse.json output in Parse Only Dialog
- 7e6e3f1: Add `SchemaFormFields` component to render react-hook-form connected form fields based on a Zod schema

### Patch Changes

- 7cf3890: When evals are created, set live runs as default value
- 65f8519: Fix Semantic Data Model view user experience bugs

## 0.3.0

### Minor Changes

- 9790827: Add agent_id as a required query param to /documents/parse
- 721b786: Semantic Data Model data source selection change triggers Model regeneration with new data source structure
- 4bddf45: Refactor DocIntel components into shared structure
- d4c1adf: Add telemetry metrics
- 721b786: Add Semantic Data Model validation
- 6d96ea2: Add feature to remove individual table or column definitions from existing Semantic Data Model

### Patch Changes

- c3123f5: Edit some text copies
- 7312b6d: Display individual actions for Semantic Data Model validation errors
- e974cdf: Add mutation to inspect agent package, moved here from frontend

## 0.2.2

### Patch Changes

- 97ee6eb: fix quick options state overwrite

## 0.2.1

### Minor Changes

- 21c8587: Readme update, adding initial Changelog and CI release publish workflow.
