# SPAR Security

## Trust Model

SPAR runs two internal services inside a single container, exposing three ports:

| Port   | Service                     | Audience              | Auth                                |
| ------ | --------------------------- | --------------------- | ----------------------------------- |
| `8001` | Workroom Backend (public)   | End users             | OIDC / Snowflake sessions, API keys |
| `8002` | Workroom Backend (internal) | Infrastructure only   | None                                |
| `8000` | Agent Server                | Workroom backend only | Unsigned JWT                        |

- **Agent Server** (`8000`) - Python backend handling agent orchestration and data
- **Workroom Backend - public** (`8001`) - Node.js/Express server handling user-facing requests, authentication, and proxying to the agent server
- **Workroom Backend - internal** (`8002`) - Unauthenticated HTTP server used for health/readiness probes (`/healthz`, `/ready`) and the file management API (`/files`) consumed by the agent server

Only port `8001` should be reachable by end users. Ports `8000` and `8002` carry no authentication and must remain on internal/private networks.

### Unsigned JWTs (Internal Only)

> [!CAUTION]
> Authentication between the workroom backend and agent server uses **unsigned JWTs** (`alg: "none"`). These tokens carry the `sub` claim (user identity) but have no cryptographic signature.

This is acceptable **only** because:

1. The agent server is reachable only from within the container's internal network (or the Docker Compose network in dev)
2. No external client should ever be able to send requests directly to the agent server
3. The workroom backend is the sole producer of these tokens after authenticating users through OIDC

If the agent server were exposed to the public internet, any client could forge identity tokens. **Never expose the agent server port (8000) to untrusted networks.**

## Network Isolation Requirements

### Production

- **Only the workroom public port (`8001`) should be reachable by end users**
- The agent server port (`8000`) must **not** be exposed to the public internet
- The workroom internal port (`8002`) must **not** be exposed to the public internet. It has no authentication and is intended only for orchestrator health probes and agent server callbacks (file management)

### Local Development (Docker Compose)

The `compose.yml` exposes port `8000` on the host for developer convenience. This is acceptable for local development only. Do not use the development compose configuration in production.
