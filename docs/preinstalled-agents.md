# Pre-installed agents

This server bootstraps a single hidden “pre-installed” agent at startup so that clients always have a ready-to-use assistant without manual setup.

## What happens on server start

- During FastAPI lifespan, `ensure_preinstalled_agents()` runs after storage and migrations are ready.
- It creates a system user if needed and upserts one agent with:
  - Description: `Internal zero-config agent.`
  - Architecture: `experimental_1` version `2.0.0`
  - Version: `1.0.0` (bumped when we ship changes)
  - Runbook: `"You are a helpful assistant."`
  - Metadata (in `agent.extra["metadata"]`): `{"project": "violet", "visibility": "hidden"}`
- If the agent already exists, we **update in place** (no deletion) when:
  - Required metadata keys are missing
  - Name/description/architecture/mode differ
  - Version is older than the desired version
  - Platform configs are present (pre-installed agent should have none)

## Visibility rules

- The agent is marked hidden via metadata (`visibility: hidden`).
- Standard agent listings filter out hidden agents:
  - Public: `GET /api/public/v1/agents`
  - Private: `GET /api/v2/agents` and `GET /api/v2/agents/raw`
- You can still fetch it directly by ID (`GET /api/v2/agents/{aid}`) or via metadata search (below).

## Discovering the pre-installed agent by metadata

Use the private search endpoint to match metadata key/value pairs supplied as query parameters:

```bash
curl -s "http://localhost:8000/api/v2/agents/search/by-metadata?project=violet&visibility=hidden" \
  | jq '.[0] | {id, name, description, mode, metadata, extra_metadata: .extra.metadata, model}'
```

Expected shape (subset):

```json
{
  "id": "69f868e2-ab3c-44af-8a68-b2c8cd0a300f",
  "name": "My Associate [4f4a8c4e-4e8d-4e9d-9f2b-0c8b4a3b5c6d]",
  "description": "Internal zero-config agent.",
  "mode": "conversational",
  "metadata": {
    "mode": "conversational",
    "worker_config": {},
    "welcome_message": "",
    "question_groups": []
  },
  "extra_metadata": {
    "project": "violet",
    "visibility": "hidden",
    "extra": "keep"
  },
  "model": {
    "provider": "OpenAI",
    "name": "gpt-4o",
    "config": {}
  }
}
```

You can then call the standard fetch endpoint with the returned `id`:

```bash
curl -s "http://localhost:8000/api/v2/agents/<agent-id>" | jq .
```

## Updating the pre-installed agent

- To roll out a new definition, bump `PREINSTALLED_AGENT_VERSION` (and any desired fields) in `server/src/agent_platform/server/preinstalled_agents.py`.
- On next startup, `ensure_preinstalled_agents()` will update the existing agent in place if the new version is higher, preserving IDs and avoiding cascade deletes.
- Metadata merging is additive: required keys are enforced, but extra metadata on the agent is preserved.
- Hidden status remains enforced by the metadata filter.
