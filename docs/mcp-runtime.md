# MCP Runtime

We can now run actions in SPAR. This is possible thanks to a service `mcp-runtime` that builds and runs MCP servers and actions.

#### Running `mcp-runtime` in Docker with local agent platform

The first time you start `mcp-runtime` you might need a clean slate and a restart of SPAR stack.

> running this command will drop all data, **including the database**

```bash
docker compose down -v --remove-orphans; docker network prune -f; docker container prune -f; COMPOSE_PROFILES=mcp-runtime docker compose up --build
```

Then, when you start the agent server, prepend `SEMA4AI_AGENT_SERVER_MCP_RUNTIME_API_URL` with the `mcp-runtime` url.

```bash
SEMA4AI_AGENT_SERVER_MCP_RUNTIME_API_URL=http://localhost:8003 make run-server-hot-reload
```
