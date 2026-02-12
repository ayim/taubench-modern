# OIDC

## Introduction

SPAR supports OIDC providers as authentication targets, allowing users to log in via their preferred authentication service (such as Microsoft, Google, Okta etc.).

The target OIDC service must support the following features for it to be a viable target:

- Must provide a valid, public **discovery** URL (A `SEMA4AI_WORKROOM_OIDC_SERVER` of `https://test.com` would have a discovery URL at precisely `https://test.com/.well-known/openid-configuration`)
- Must support the following scopes under the provided client:
  - `openid`
  - `email`
  - `offline_access`
  - `profile`

### Behaviour

When setting up a new OIDC-enabled SPAR instance, the **first user** to sign in will be granted the role of `admin`. All subsequent users will be granted the `knowledgeWorker` role, which has the lowest privilege level.

This behaviour can pose problems when those with development/infrastructure access need to login. An additional environment variable, `SEMA4AI_WORKROOM_AUTH_AUTO_PROMOTE`, can be used to automatically promote users to `admin` role status when the **server starts up**.

### Groups Claim

SPAR determines user roles from the OIDC token's groups claim. The expected values are `admin` and `knowledgeWorker`.

By default, SPAR reads from the `groups` claim. If your OIDC provider uses a different claim name (e.g. Auth0's `auth0_org_roles`), set `SEMA4AI_WORKROOM_OIDC_GROUPS_CLAIM_NAME` to the desired claim name.

**Future improvement**: currently, group names must match SPAR roles exactly (`admin`, `knowledgeWorker`). Two options to support arbitrary group-to-role mapping:

- _JSON config_ (low effort, worse UX) - a configuration-based mapping, requires redeployment on changes
- _SSO management view_ (bigger effort, better UX) - a runtime UI for mapping groups to roles, likely requires a dedicated role above `admin` to manage SSO settings

## Required Environment Variables

To run SPAR in OIDC mode, the following environment variables must be set:

| Variable                               | Description                                                               |
| -------------------------------------- | ------------------------------------------------------------------------- |
| `SEMA4AI_WORKROOM_AUTH_MODE`           | Must be set to `oidc`                                                     |
| `SEMA4AI_WORKROOM_OIDC_SERVER`         | OIDC provider URL (discovery at `<url>/.well-known/openid-configuration`) |
| `SEMA4AI_WORKROOM_OIDC_CLIENT_ID`      | OAuth client ID                                                           |
| `SEMA4AI_WORKROOM_OIDC_CLIENT_SECRET`  | OAuth client secret                                                       |
| `SEMA4AI_WORKROOM_JWT_PRIVATE_KEY_B64` | Base64-encoded private key for signing JWTs                               |

### Optional Environment Variables

| Variable                                        | Default                               | Description                                                       |
| ----------------------------------------------- | ------------------------------------- | ----------------------------------------------------------------- |
| `SEMA4AI_WORKROOM_OIDC_GROUPS_CLAIM_NAME`       | `groups`                              | Name of the token claim containing user roles                     |
| `SEMA4AI_WORKROOM_OIDC_SCOPES`                  | `offline_access openid email profile` | Space-separated list of OAuth scopes                              |
| `SEMA4AI_WORKROOM_OIDC_ORGANIZATION_AUTH_PARAM` | -                                     | Organization parameter passed to the auth request                 |
| `SEMA4AI_WORKROOM_AUTH_AUTO_PROMOTE`            | -                                     | Comma-separated emails to auto-promote to `admin` on server start |

## Auth Payload Examples

### Okta

Example token claims:

```js
{
  sub: '00uq7cqel80Oy1hwi5d7',
  email: 'perry@sema4.ai',
  ver: 1,
  iss: 'https://dev-50062150.okta.com/oauth2/ausqaqjuno07uMFam5d7',
  aud: '0oaqaqhsykN66WrcR5d7',
  iat: 1756388213,
  exp: 1756391813,
  jti: 'ID.5ziIZB_aL-u9MvU4Sl_yUIXbolqwXRIYo8ltHjpZ_Lk',
  amr: [ 'pwd' ],
  idp: '00o2x1u7gd9uyZmcJ5d7',
  auth_time: 1756386083,
  at_hash: 'MBzJcRhbfsWonWQpFxs7ag'
}
```

## Local Testing

You can test OIDC functionality by using this mock OIDC provider in `compose.yml`:

```yaml
oidc-provider:
  image: ghcr.io/navikt/mock-oauth2-server:2.1.9
  ports:
    - '9000:9000'
  environment:
    SERVER_PORT: 9000
    JSON_CONFIG: |
      {
          "interactiveLogin": true,
          "httpServer": "NettyWrapper",
          "tokenCallbacks": [
              {
                  "issuerId": "default",
                  "tokenExpiry": 120,
                  "requestMappings": [
                      {
                          "requestParam": "scope",
                          "match": ".*",
                          "claims": {
                              "sub": "user123",
                              "name": "Test User",
                              "email": "test@example.com",
                              "groups": ["users", "admins"]
                          }
                      }
                  ]
              }
          ]
      }
```

For required environment variables, see [Configuration](configuration.md).
