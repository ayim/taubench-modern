# Context

The Work Room folder is an app that comprises of 4 main pieces:

- `@backend`: backend (in express) responsible for routing request to the agent-server, located outside of this folder, both locally and in production
- `@frontend`: frontend (in react) responsible for displaying the UI.
- `@spar-ui`: re-usable react components consumed by the frontend and another service (Studio) located outside of this folder. The code written in spar-ui is run in an electron app and built using webapp. Keep that in mind for any implementation
- `@mcp-runtime`: the service responsible for provisioning and running action servers as MCP servers. It exposes an API to provision, deprovision and list existing deployments (among other things)

# Glossary

- `thread` is the technical term, `conversation` should be used for customer facing errors and UIs

# High-level guidelines

## Working in @spar-ui

### Scripts

- Run `npm run test` for type-checking

### Guidelines

- When adding new business logic for queries and mutations, there are two options:
  - A. Add the logic inside the handler of the query or mutation
  - B. Define a new [SparAPIClient interface](@spar-ui/src/api/index.ts) handler and call it from the query or mutation body
  - Pick A when you only need to call the `queryAgentServer`, there are no feature flag requirements nor electron-specific handling needed
  - Pick B as a fallback or when the operator explicitly asks you to do so
- Mutations and queries must be defined in [queries](@spar-ui/src/queries/) - find the most relevant place depending on the work at hand
- ALL errors thrown in `QueryError` should be customer-facing. If unsure about how technical you should get, ask the operator
- ALL mutations must have an `onError` handler defined. It uses the `addSnackbar` and `getSnackbarContent`

## Working in workroom

### Scripts

- Run `npm run build` for build

## Working in workroom frontend

### Scripts

- Run `npm run test:types` for type-checking
