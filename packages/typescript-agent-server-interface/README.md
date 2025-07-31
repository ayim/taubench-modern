# Agent Server Interface (Typescript)

## Retrieving the latest OpenAPI spec for the Private AND Public API

1. Run the server (`COMPOSE_PROFILES=agent-server-no-auth docker compose up --build` at the root)
2. Navigate to the [PRIVATE API Open API spec page](http://localhost:8000/api/v2/openapi.json)
3. Copy the content into [private.openapi.json](./private.openapi.json)
4. Navigate to the [PUBLIC API Open API spec page](http://localhost:8000/api/public/v1/openapi.json)
5. Copy the content into [public.openapi.json](./public.openapi.json)

### Releasing a new version

_The process is currently manual - the north star is for it to be fully automated:_
_The agent server API changes should trigger an automatic publishing of the interface, without any engineer intervention_

1. Update the version of the interface to match the current version of the Agent Server (present in the `info.version` of the `openapi.json`)
2. Run the following command:

```sh
# !!! The version must match the version of the agent-server: see step 1 !!!
npm version 2.0.22
```

3. Open a PR and get it merged
4. Create a new release with the following format:
   _Notice the version appended after -v_

```sh
sema4ai-agent-server-interface-v2.0.22
```

### Releasing a prerelease version

_Used to test changes that happened between two `agent-server` releases_

```sh
npm version prerelease --preid=marco
npm publish    # you need to setup your .npmrc with a gh token
```

## Generating types and schema.

```sh
npm run generate
```

## Public API usage example

Streaming conversations.

```typescript
const client = createAgentPublicApiSDK({
  baseUrl: 'http://localhost:8000',
});

client.stream(
  '/api/public/v2/agents/{aid}/conversations/{cid}/stream',
  {
    body: {
      content: 'Hello World',
    },
    params: {
      path: {
        aid: 'c1bb70de-5bd1-4922-9085-5adf2b963fbb',
        cid: '25ca6c93-f265-4d57-b2f8-70c144be1e34',
      },
    },
  },
  {
    onError(error) {
      console.log(error);
    },
    onMessage(message) {
      console.log(message);
    },
    onDone() {
      // nothing else in the stream
    },
  }
);
```
