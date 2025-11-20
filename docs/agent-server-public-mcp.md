# Agent-Server "as an MCP server"

We're trialing an idea to expose some limited surface of the agent-server as an MCP server hosted under a given route.

## How to use

We've implemented an MCP server at `http://agent-server-url:port/api/v2/public-mcp`. This MCP server supports one
transport: the more recent "Streamable HTTP" transport. It's implementd as part of the agent-server using `FastMCP`.

## Tools

For now, we're exposing three really basic tools:

- `list_agents()`: List all agents hosted on the server.
- `chat_with_agent(agent_id: str, message: str, thread_name: str, existing_thread_id: str | None)`: Chat with an agent on a new or existing thread.
- `list_threads_for_agent(agent_id: str)`: List all threads for a given agent.

We're also exposing an MCP resource for `agents://{name}`. This resource returns a JSON object representing an agent. (NOTE: not all MCP clients support resources yet, so your mileage may vary.)

## Examples

See [docs/create-agent-examples.md](create-agent-examples.md) for current payload examples that show how to POST an agent that talks to MCP servers and uses the "agent server as an MCP server" pattern for agent-to-agent communication. Try sending chats like "list the agents" or "chat with agent X and ask it to give you a fun fact about science".

## Using Other MCP Servers

We've upgraded the agent-server to both _expose_ an MCP server under a certain route and _create agents referencing MCP servers_. For now, if you want to use other MCP servers with your agents, you'll need to POST them during agent create and make sure they're running before you try and chat. You can utilize servers that support either the "Streamable HTTP" or "Server-Sent Events" transports. We do _not_ yet support Auth for MCP, as that's been fast evolving (and had major changes as of a few weeks ago). If you know of a good MCP server with Auth to test, please share!
