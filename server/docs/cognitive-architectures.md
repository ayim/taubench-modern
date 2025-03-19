# Agent Architectures

Agent architectures used by the Agent Server are plugins loaded via the Python entrypoint system. These are dynamically loaded based on the plugin group called `agent_architectures`. Currently, these plugins must be installed globally to be properly imported during loading. Additionally, the Agent Server will dynamically update the OpenAPI schema to include the endpoints for each agent architecture.
