# Sema4.ai Data Typescript Interface

This package contains the typescript interface for the Sema4.ai Data related services.

## Installation

```bash
npm install @sema4ai/data-interface
```

## Usage

```typescript
import { DataSources } from '@sema4ai/data-interface';

const schema = DataSources.redshift;
```

## Development

When you create a feature PR, you must include a Changelog entry and the target change scope by running:

```bash
npm run changeset
```

Then follow the steps to create a changeset entry and commit it to your PR.

### Local build

This package publishes dual ESM/CJS output via `tsup`. After changing `src/`, rebuild:

```bash
cd workroom
npm run build --workspace @sema4ai/data-interface
```

If the Workroom UI renders blank after changing exports or build output, clear Vite's prebundle cache:

```bash
rm -rf workroom/frontend/node_modules/.vite
```

### Publishing a Version

A PR named `Typescript Interface Release` will be auto created, that contains all unreleased changes. Once this PR is merged, a release will be created and published.
