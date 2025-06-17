# Using `/api/v2/capabilities/mcp/tools` – Example Requests

This page collects battle-tested payloads you can copy-paste into `curl` (or your favourite REST client)
to verify that the **list tools** endpoint works for a mix of remote and local MCP servers.

All examples assume your agent-platform server is running locally and reachable at
`http://localhost:8000`. Adjust the host/port as needed.

---

## 1. Remote servers (no auth)

### 1-a DeepWiki – SSE transport

```bash
curl -X POST http://localhost:8000/api/v2/capabilities/mcp/tools \
     -H 'Content-Type: application/json' \
     -d '{
           "mcp_servers": [
             {
               "name": "deepwiki-sse",
               "transport": "sse",
               "url": "https://mcp.deepwiki.com/sse"
             }
           ]
         }' | jq
```

### 1-b DeepWiki – Streamable-HTTP transport

```bash
curl -X POST http://localhost:8000/api/v2/capabilities/mcp/tools \
     -H 'Content-Type: application/json' \
     -d '{
           "mcp_servers": [
             {
               "name": "deepwiki-sse",
               "transport": "sse",
               "url": "https://mcp.deepwiki.com/sse"
             }
           ]
         }' | jq
```

---

## 2. Local (stdio) servers

The platform can spin up MCPs as local subprocesses. These examples show how to
reference them in the payload – no network needed.

> **Prerequisite:** enable stdio targets by setting the env-var
> `SEMA4AI_AGENT_SERVER_MCP_ALLOW_STDIO=1` before starting the agent-platform server.

### 2-a DeepWiki – via `npx`

```bash
curl -X POST http://localhost:8000/api/v2/capabilities/mcp/tools \
     -H 'Content-Type: application/json' \
     -d '{
           "mcp_servers": [
             {
               "name": "deepwiki-local",
               "transport": "stdio",
               "command": "npx",
               "args": ["-y", "mcp-deepwiki@latest"]
             }
           ]
         }' | jq
```

---

## 3. Batch – mix & match

Pass multiple servers in a single call – the endpoint returns a `results` array
in the same order.

```bash
curl -X POST http://localhost:8000/api/v2/capabilities/mcp/tools \
     -H 'Content-Type: application/json' \
     -d '{
           "mcp_servers": [
             { "name": "deepwiki-sse", "transport": "sse", "url": "https://mcp.deepwiki.com/sse" },
             { "name": "deepwiki-stream", "transport": "streamable-http", "url": "https://mcp.deepwiki.com/mcp" },
             { "name": "deepwiki-local", "transport": "stdio", "command": "npx", "args": ["-y", "mcp-deepwiki@latest"] }
           ]
         }' | jq
```

---

### Tips & Troubleshooting

- If the request hangs for stdio transports, confirm `SEMA4AI_AGENT_SERVER_MCP_ALLOW_STDIO=1` is set **before** the server starts.
- A server that needs serialisation (can't handle concurrent tool calls) can be forced via `"force_serial_tool_calls": true` in the entry.
- Use `jq` for pretty-printing JSON responses (`brew install jq` on macOS).
- Timeout errors are surfaced per-server in the `issues` list – handy for flaky remotes.
