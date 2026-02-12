# Work Room - Agent Runtime component

This folder contains the source code for the "Interaction UI" part of the agent runtime component

## Configuration

Workroom is run alongside the agent-server in SPAR configuration - a single container for the entire agent suite. Thusly configuration affects both services.

This is documented under [SPAR configuration](docs/spar/configuration.md).

## Local workspace note

`@sema4ai/data-interface` is now a workspace package under `workroom/packages/data-interface`. If you change its `src`, rebuild it so the `dist` output stays in sync:

```bash
cd workroom
npm run build --workspace @sema4ai/data-interface
```

If the UI renders blank after restarting, clear Vite’s prebundle cache so it re-optimizes dependencies:

```bash
rm -rf workroom/frontend/node_modules/.vite
```
