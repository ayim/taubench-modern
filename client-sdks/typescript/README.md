## Agent Server Interface (Typescript)

Generate types and schema.

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
