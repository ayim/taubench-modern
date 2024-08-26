# Sema4.ai Agent Server API Typescript interface

This package provides Agent Server API interface.

## Usage

1. Install the package

```sh
npm i @sema4ai/agent-server-interface
```

2. Usage:

```ts
import { components, paths, meta } from "@sema4ai/agent-server-interface";

// Schema objects
type Agent = components["schemas"]["Agent"];

// Path params
type EndpointParams = paths["/api/v1/agents"]["parameters"];

// Agent Server meta
const version = meta.version;
```

## Release

1. Run the Agent Server locally, see [Developer Guide](/docs/developer.md)

2. Generate the types and build the package:

```sh
npm run generate
npm run build
```

3. Make sure the [package version](./package.json) matches the Agent Server version:

4. Publish the package:

```sh
npm publish
```
