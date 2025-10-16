# SPAR Container Configuration

SPAR can be configured in a variety of manners to suit the enviroment that's hosting it. The configurations below align with the common environments we support for SPAR. You'll likely not find a global list of environment variables as we discriminate the configuration structure for SPAR quite aggressively, so not all environment variables make sense in all configurations.

## Base Environment Variables

The following variables are required in all following scenarios.

### Agent Server

These variables are agent-server related, and can be applied to the general SPAR docker image.

| Variable                                            | Example                      | Definition                         | Required  |
| --------------------------------------------------- | ---------------------------- | ---------------------------------- | --------- |
| `AGENT_SERVER_PORT`                                 | `8000`                       | Agent server listen port.          | Yes       |
| `LOG_LEVEL`                                         | `INFO`                       | Agent server log level.            | No [^3]   |
| `OTEL_COLLECTOR_URL`                                | `http://otel-collector:4318` | Open Telemetry collector URL.      | _No_ [^1] |
| `OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE` | `delta`                      | Open Telemetry metric temporality. | _No_ [^2] |
| `POSTGRES_DB`                                       | `agents`                     | Postgres database name.            | _No_ [^2] |
| `POSTGRES_HOST`                                     | `postgres`                   | Postgres database host.            | _No_ [^2] |
| `POSTGRES_PASSWORD`                                 | `agents`                     | Postgres database password.        | _No_ [^2] |
| `POSTGRES_PORT`                                     | `5432`                       | Postgres database port.            | _No_ [^2] |
| `POSTGRES_USER`                                     | `agents`                     | Postgres database username.        | _No_ [^2] |
| `SEMA4AI_AGENT_SERVER_DB_TYPE`                      | `postgres`                   | Agent server database type.        | _No_ [^2] |

> [!CAUTION]
> You should be running SPAR with a Postgres database in all production scenarios. Use of the built-in SQLite DB is not supported outside of brief demonstration scenarios.

The following variables can be added to enable authentication between the workroom and agent-server.

| Variable             | Example              | Definition                          | Required |
| -------------------- | -------------------- | ----------------------------------- | -------- |
| `AUTH_TYPE`          | `jwt_local`          | Authentication mode.                | Yes      |
| `JWT_ALG`            | `ES256`              | JWT algorithm.                      | Yes      |
| `JWT_AUD`            | `agent_server`       | The JWT audience.                   | Yes      |
| `JWT_DECODE_KEY_B64` | `LS0tLS1CRUdJTiB...` | The JWT public key, base64 encoded. | Yes      |
| `JWT_ISS`            | `spar`               | Token issuer.                       | Yes      |

### Workroom Backend

These variables are workroom related, and can be applied to the general SPAR docker image.

| Variable                                   | Example               | Definition                                          | Required |
| ------------------------------------------ | --------------------- | --------------------------------------------------- | -------- |
| `SEMA4AI_WORKROOM_AGENT_SERVER_URL`        | `http://agent-server` | URL to the agent server, non-public.                | Yes      |
| `SEMA4AI_WORKROOM_ALLOW_INSECURE_REQUESTS` | `true`                | Allow non-HTTPS requests (session/cookie handling). | No       |
| `SEMA4AI_WORKROOM_LOG_LEVEL`               | `INFO`                | Configure log level for the workroom backend.       | No [^3]  |
| `SEMA4AI_WORKROOM_PORT`                    | `8001`                | Workroom / gateway HTTP listen port.                | Yes      |
| `SEMA4AI_WORKROOM_PORT_INTERNAL`           | `8002`                | Internal (private) HTTP listen port.                | Yes      |
| `SEMA4AI_WORKROOM_TENANT_ID`               | `spar`                | Tenant identifier.                                  | Yes      |

The following variables can be added to enable authentication between the workroom and agent-server.

| Variable                               | Example             | Definition                                             | Required |
| -------------------------------------- | ------------------- | ------------------------------------------------------ | -------- |
| `SEMA4AI_WORKROOM_JWT_PRIVATE_KEY_B64` | `LS0tLS1CRUdJTi...` | Agent server token signing private key, base64 encoded | No       |

## Stand-alone installation w/ OIDC Authentication

The following environment variables should be configured for this setup:

| Variable                              | Example               | Definition                                          |
| ------------------------------------- | --------------------- | --------------------------------------------------- |
| `SEMA4AI_WORKROOM_AUTH_MODE`          | `oidc`                | The authentication mode to use.                     |
| `SEMA4AI_WORKROOM_OIDC_CLIENT_ID`     | `sema4ai-oidc-prod`   | OAuth 2.0 client identifier.                        |
| `SEMA4AI_WORKROOM_OIDC_CLIENT_SECRET` | `secret-value...`     | OAuth 2.0 client secret.                            |
| `SEMA4AI_WORKROOM_OIDC_SERVER`        | `http://dev.okta.com` | The OIDC compatible server URL. See **foot notes**. |
| `SEMA4AI_WORKROOM_SESSION_SECRET`     | `secret-value`        | Session secret for encoding session data.           |

> [!IMPORTANT]
> This setup implies the use of the **Base Environment Variables** listed earlier in this document.

## Foot Notes

[^1]: Not required but recommended for full functionality.

[^2]: Not required but _expected_ for Sema4.ai production applications.

[^3]: Logging can be configured using a variety of [verbosity levels](#logging).

### OIDC Provider Support

SPAR / Workroom can be connected to an OIDC-capable authentication provider, such as Okta, Google etc.

Redirect URIs:

| Environment | Redirect URI                                                |
| ----------- | ----------------------------------------------------------- |
| Development | `http://localhost:8001/tenants/spar/workroom/oidc/callback` |

### OIDC Server URL

OIDC authentication providers are _discovered_ automatically by our OIDC client. That means that a compatible service must provide a `.well-known/openid-configuration` endpoint. You **should not** specify the `.well-known` portion in this value - it is assumed to be available.

For instance, the correct value for the mock OIDC server we test with is `http://localhost:9000/default`, not `http://localhost:9000/default/.well-known/openid-configuration`.

### Logging

Logging can be configured for the Agent Server and Workroom backend separately, via the use of the following environment variables:

- `LOG_LEVEL` - Agent server log level. Defaults to `INFO`. Valid levels: `ERROR`, `INFO`, `DEBUG`, `TRACE`.
- `SEMA4AI_WORKROOM_LOG_LEVEL` - Workroom backend log level. Defaults to `INFO`. Valid levels: `ERROR`, `INFO`, `DEBUG`. Case insensitive.
