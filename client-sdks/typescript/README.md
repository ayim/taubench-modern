## Agent Server Interface (Typescript)

### Retrieving the latest OpenAPI spec for the PRIVATE API

1. Run the server (`docker compose up` at the root)
2. Navigate to the [API Open API spec page](http://localhost:8000/openapi.json)
3. Copy the content into [private.openapi.json](./private.openapi.json)

### Releasing a new version
_The process is currently manual - the north star is for it to be fully automated:_
_The agent server API changes should trigger an automatic publishing of the interface, without any engineer intervention_

1. Update the version of the interface to match the current version of the Agent Server (present in the `info.version` of the `openapi.json`)
2. Run the following command:
_The pre-release should start with 1 if there has not been any new release of that specific version, or incremented by 1 if that version has already been released_
```
npm version 2.0.17-2
```
3. Open a PR and get it merged
4. Create a new release with the following format:
_Notice the version appended after -v_
```
sema4ai-agent-server-interface-v2.0.17-2
```

### Generating types and schema.

```
npm run generate
```

Publish prerelease version.

```
npm version prerelease --preid=marco
npm publish    # you need to setup your .npmrc with a gh token
```

### Public API

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
