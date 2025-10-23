Model Support Updates – Step‑By‑Step Guide

This guide explains exactly what to change (and where) when adding support for a new model. It covers the common steps that apply to all providers, but provider‑specific changes may be needed. In future releases, we may change how the UI uses model paths to align with the OpenAI spec. As of `v2.1.13` provider specific mappings are still in effect. Check agent-server version when updating support.

Canonical IDs and flow

- UI uses a shorthand like `bedrock:claude-4-5-haiku-thinking-high`.
  - **_NOTE_ plans to have the UI use the OpenAPI spec soon**
- Backend uses canonical generic IDs `platform/provider/model`, e.g. `bedrock/anthropic/claude-4-5-haiku-thinking-high`.
- We map canonical IDs → provider‑specific IDs (what the vendor expects) in `core/src/agent_platform/core/platforms/configs.py` under `models_to_platform_specific_model_ids`.
- The model selector filters candidates by the platform allowlist from the saved platform config (`PlatformParameters.models`), then by `model_type`, then sorts and selects.

Common steps (all providers)

1. Add/verify LLM metadata

- File: `core/src/agent_platform/core/platforms/llms.json`
- Auto-generate the `llms.json` file. Use: `curl -X GET https://artificialanalysis.ai/api/v2/data/llms/models -H "x-api-key: KEY_HERE"`. Check api key in 1pass. Copy/paste the resulting json into this file, and ensure the model you are adding is included.

2. Map canonical → provider IDs

- File: `core/src/agent_platform/core/platforms/configs.py`
- Update `PlatformModelConfigs.models_to_platform_specific_model_ids` with a canonical key and provider‑specific value.
  - Example (Bedrock Anthropic):
    - Key: `"bedrock/anthropic/claude-4-5-haiku"`
    - Value: `"anthropic.claude-haiku-4-5-20251001-v1:0"`

3. Classify the model (type/family/context)

- Same file: `configs.py`
- Update:
  - `models_to_model_types`: set the canonical ID to `"llm"` (or `"embedding"`, etc.). Missing type causes filtering to drop the candidate.
  - `models_to_families`: add the canonical ID to an appropriate family (e.g., `"claude"`, `"openai-gpt"`). This is used for prompt specialization and display.
  - `models_to_context_window_sizes`: set an approximate or documented context window.
  - (Optional) `models_to_architecture_overrides`: if a model requires a specific agent architecture, add it here.
  - (Optional) `models_capable_of_driving_agents`: if this model should be allowable as a primary “agent‑driving” model, add its canonical ID.

4. Frontend selector list

- **_NOTE_ plans to obviate this soon**
  - Plan to have frontend load directly from agent-server-interface, which is generated from OpenAPI specs
- File: `workroom/frontend/src/components/platforms/llms/components/llmSchemas.ts`
- Add a new UI value to the correct list (e.g., `BEDROCK_MODEL_VALUES`) using the shorthand `"<kind>:<slug>"` (e.g., `"bedrock:claude-4-5-haiku"`).
- The UI strips the `<kind>:` prefix before saving and sends: `models: { <provider>: [<slug>] }`.

5. Capability test endpoint (optional but recommended)

- Endpoint: `POST /api/v2/capabilities/platforms/{kind}/test`
- The UI can validate credentials/model before saving. Usually no server code change is needed for a new model if step (2) mapping is present and credentials grant access.

6. Parsers, stop reasons, and sampling constraints (as needed)

- If the provider introduces new stop reasons (e.g., `"refusal"`) or changes in response shape, ensure the platform parser handles them:
  - Bedrock: `core/src/agent_platform/core/platforms/bedrock/parsers.py`
  - OpenAI: `core/src/agent_platform/core/platforms/openai/parsers.py`
  - Google: `core/src/agent_platform/core/platforms/google/parsers.py`
- If the provider introduces sampling constraints (e.g., “temperature XOR top_p”), enforce them where prompts/converters build the request for that provider.

7. Tests and validation

- Run: `make test-unit`, `make lint`, `make typecheck`, `make check-format`.
- Ensure `core/tests/platforms/test_configs.py` passes; it validates that canonical IDs have families/types/metadata.
- Start a conversation or use `/prompt/generate` with `model` to confirm selection resolves to the new model.
- Re-generate vcr cassettes for testing. `make test-vcr-record-new` will add recordings for new models without losing existing ones. `make test-vcr-record-fresh` will record everything from scratch.

Frontend checklist

- Add new option to the appropriate constant list in:
  - `workroom/frontend/src/components/platforms/llms/components/llmSchemas.ts` (e.g., `BEDROCK_MODEL_VALUES`).
- Ensure the provider selection logic in `EditPlatformDialog.tsx` matches the provider you’re adding (e.g., Bedrock → `provider = 'anthropic'`).

Server checklist

- No new endpoints are required. Use `/api/v2/platforms/` to create/update configs and `/api/v2/capabilities/platforms/{kind}/test` to validate connectivity.

Troubleshooting tips

- Candidate filtered out by allowlist: Ensure the saved platform config looks like `models: { "<provider>": ["<slug>"] }` (slug only; no `platform:` prefix). Provider must be lowercase (e.g., `"anthropic"`).
- Candidate dropped by model_type filter: Ensure the canonical ID exists in `models_to_model_types` as `"llm"`.
- Resolution failed (not available): Verify your credentials/region can access the provider model ID and that `get_available_models()` lists it.

Quick checklist for a new LLM

- [ ] Add (autogen) entry to `llms.json` (slug, pricing, context, metrics)
- [ ] Add canonical → provider mapping in `configs.py/models_to_platform_specific_model_ids`
- [ ] Add to `models_to_model_types` (usually `"llm"`)
- [ ] Add to `models_to_families` (e.g., `"claude"`)
- [ ] Add to `models_to_context_window_sizes`
- [ ] (Optional) Add to `models_to_architecture_overrides` and `models_capable_of_driving_agents`
- [ ] Update UI lists in `llmSchemas.ts`
- [ ] Validate with applicable tests
