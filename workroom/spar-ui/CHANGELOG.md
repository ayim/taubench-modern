# @sema4ai/spar-ui

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
