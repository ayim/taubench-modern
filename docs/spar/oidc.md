# OIDC

## Introduction

SPAR supports OIDC providers as authentication targets, allowing users to log in via their preferred authentication service (such as Microsoft, Google, Okta etc.).

The target OIDC service must support the following features for it to be a viable target:

- Must provide a valid, public **discovery** URL (A `SEMA4AI_WORKROOM_OIDC_SERVER` of `https://test.com` would have a discovery URL at precisely `https://test.com/.well-known/openid-configuration`)
- Must support the following scopes under the provided client:
  - `openid`
  - `email`
  - `offline_access`

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

Environment variables:

```
SEMA4AI_WORKROOM_OIDC_CLIENT_ID=foo
SEMA4AI_WORKROOM_OIDC_CLIENT_SECRET=bar
SEMA4AI_WORKROOM_OIDC_SERVER=http://localhost:9000/default
```
