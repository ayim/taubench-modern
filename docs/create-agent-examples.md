# Private create-agent payload examples

The private agent APIs are registered under `/api/v2/agents` and are not part of the public OpenAPI surface, so you need private access (and auth configured on your server) to hit them directly. These examples mirror the payload shapes used by our tests and helpers and are intended to be runnable without relying on deprecated notebooks.

## Base request setup

All of the payloads below expect the same required fields enforced by `UpsertAgentPayload` (`name`, `description`, `version`, and `runbook`).

## OpenAI chat agent

This is the minimal payload shape we use in tests for a conversational agent that talks to the OpenAI Chat Completions API.

```python
from agent_platform.core.platforms.openai import OpenAIPlatformParameters

openai_config = OpenAIPlatformParameters(
    openai_api_key=os.environ["OPENAI_API_KEY"],
    # Remember, models allowlist is:
    # { "provider": ["the", "allowed", "models"] }
    models={"openai": ["gpt-4.1"]},
).model_dump()

payload = {
    "mode": "conversational",
    "name": "Docs OpenAI Agent",
    "description": "Uses GPT-4.1 with the default architecture",
    "version": "1.0.0",
    "runbook": "Answer concisely and cite sources when possible.",
    "agent_architecture": {
        "name": "agent_platform.architectures.default",
        "version": "1.0.0",
    },
    "platform_configs": [openai_config],
    "action_packages": [],
    "mcp_servers": [],
    "mcp_server_ids": [],
    "question_groups": [],
    "observability_configs": [],
    "extra": {},
}

resp = requests.post(f"{BASE_URL}/agents", headers=headers, json=payload)
resp.raise_for_status()
agent_id = resp.json()["agent_id"]
```

## Attaching existing MCP servers

If you have already registered MCP servers through the private `/api/v2/mcp-servers` endpoints, you can attach them to an agent by ID instead of embedding the full server definition. The rest of the payload matches the OpenAI example.

```python
mcp_enabled_payload = {
    **payload,  # reuse a base payload like the OpenAI example above
    "name": "Docs MCP-enabled Agent",
    "mcp_server_ids": ["demo-mcp-server-id"],
}

resp = requests.post(f"{BASE_URL}/agents", headers=headers, json=mcp_enabled_payload)
resp.raise_for_status()
```

You can also inline full MCP server definitions via `mcp_servers` if you need to provide connection details on creation time; the server will merge `mcp_server_ids` and `mcp_servers` before exposing tool definitions.
