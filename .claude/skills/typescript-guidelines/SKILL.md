---
name: typescript-guidelines
description: Guidelines for reviewing PRs in the agent-platform's workroom codebase. Use when reviewing code, addressing PR feedback, or writing new code to ensure consistency. Invoke this skill when the user is opening a PR. Keywords: "pr", "frontend", "typescript", "react", "workroom", "review"
---

# TypeScript & React Guidelines

Single source of truth for TypeScript/React code in the workroom codebase. Use as a checklist when reviewing or writing code.

## Maintaining This Document

- Add new learnings via PR to this file
- A PR not passing formatting, linting, and type-checking is not ready for review

## Table of Contents

1. [General Principles](#1-general-principles)
2. [TypeScript](#2-typescript)
3. [Control Flow](#3-control-flow)
4. [Functions](#4-functions)
5. [Variables & Mutation](#5-variables--mutation)
6. [Exports & Organization](#6-exports--organization)
7. [Zod](#7-zod)
8. [Error Handling](#8-error-handling)
9. [Validation](#9-validation)
10. [Backend](#10-backend)
11. [Frontend](#11-frontend)

---

## 1. General Principles

### Look Around First

- Before introducing a new helper or pattern, check for existing usage in the codebase
- Mimic existing patterns. If refactoring would improve things, raise it with clear PROs/CONs

### Keep It Simple

- Readability trumps cleverness. Write code that's easy to understand at first glance
- Avoid premature optimization. Performance matters when it makes sense, not by default
- Common over-engineering to avoid:
  - `useMemo`/`useCallback` for values that don't need memoization
  - IIFEs when a simple ternary suffices
  - Abstractions for one-time operations
- If complexity is truly needed, justify it with a comment or test
- Code should be self-explanatory. Only add comments when logic isn't self-evident
- Actively remove unused code. Don't leave commented-out code or unused imports/functions
- When installing new dependencies, always use the latest available version

---

## 2. TypeScript

### Strict Mode

- **No `as` casts**: Fix types at the source instead
- **No `any`**: Flag existing `any` types and offer to fix them. Never move an `any` around to fix type errors
- **Don't rewrite types**: Import from dependencies when available
- **Don't copy types**: Export from the owner's file location instead of duplicating

### Type Patterns

- Generics should be prefixed with `T` followed by a descriptive name: `TUserId`, `TPayload`
- Use `satisfies` when you need type checking without widening:
  ```typescript
  const config = { timeout: 1000 } satisfies Config;
  ```
- Use `as const` for constant values to get literal types:
  ```typescript
  const API_KEY_PREFIX = 's4w' as const;
  ```
- Prefer discriminated unions for type safety and inference:
  ```typescript
  type Result<T> =
    | { success: true; data: T }
    | { success: false; error: { code: string; message: string } };
  ```
- Prefer explicit `null` over `undefined` for absence of data in return types

### Branded Types

If a branded type is needed (e.g., `SecretDataReference<string>`), update the database/interface types to use it directly rather than casting at usage sites.

---

## 3. Control Flow

### Early Returns & Switch

- Always prefer early returns to reduce nesting
- Use exhaustive switch statements with `satisfies never` in default:
  ```typescript
  switch (status) {
    case 'pending':
      return handlePending();
    case 'completed':
      return handleCompleted();
    default:
      status satisfies never;
      throw new Error('Unknown status');
  }
  ```

### Readability

- Extract complex conditions into named variables: instead of `if (a && b && c)`, use `const isValid = a && b && c`
- Avoid rightward drift; refactor into smaller functions
- Encapsulate logic in self-contained functions. Use IIFEs for isolated error handling:
  ```typescript
  const result = await (async (): Promise<Result<Data>> => {
    // isolated logic with its own error handling
  })();
  ```

---

## 4. Functions

### Signatures

- Use arrow function notation
- Always type the function return explicitly
- Only use classes when state persistence is needed; otherwise prefer functions

### Arguments

- Use objects for arguments unless types can't be mistaken:
  ```typescript
  // Good
  const createApiKey = async ({ name }: { name: string }): Promise<ApiKey> => ...
  const processFile = (file: Buffer, type: string): Result => ...

  // Bad - two strings are easily swapped
  const createUser = (firstName: string, lastName: string): User => ...
  ```
- Inline argument types unless reused elsewhere. Don't create single-use type aliases:
  ```typescript
  // Good
  const updateUser = ({ name }: { name: string }): User => ...

  // Bad
  type UserInput = { name: string };
  const updateUser = (input: UserInput): User => ...
  ```
- Never use default argument values. Make arguments optional: `options?: { limit?: number }`
- If a `context` pattern exists (monitoring, database), it should be the first argument

### Naming

- Use descriptive names that indicate the action: `setLastUsedAt` not `touchApiKey`
- Avoid `res`, `result`, `data`. Prefer `userListResult`, `retrievedApiKey`
- camelCase for functions and variables
- snake_case for data in files (JSON, config)

---

## 5. Variables & Mutation

- Don't use `let` unless critical for performance. Prefer IIFE or ternary:
  ```typescript
  // Good
  const status = isActive ? 'active' : 'inactive';

  // Good (complex logic)
  const status = (() => {
    if (isActive) return 'active';
    if (isPending) return 'pending';
    return 'inactive';
  })();

  // Bad
  let status;
  if (isActive) status = 'active';
  else status = 'inactive';
  ```

---

## 6. Exports & Organization

### Exports

- Use barrel exports with explicit re-export
- Always use named exports
- Never export types or functions unless they have an existing consumer

### Ordering

- When adding keys to objects or enum values, follow existing conventions (often alphabetical)
- For new structures, prefer lexicographic order

### Utils Placement

Place at the lowest common ancestor of consumers:
- Single consumer: next to the consuming folder
- Sibling consumers: at the parent level
- Codebase-wide: at root level
- Use a single `utils.ts` unless multiple logical groups exist

### Discoverability

- Centralize code, types, and shared patterns to reduce fragmentation
- Cross-reference documentation to provide multiple paths to the same source
- Leave clear breadcrumbs: consistent naming, logical file structure, predictable locations

---

## 7. Zod

Schema and inferred type must share the same PascalCase name:

```typescript
const ApiKeyConfig = z.object({ ... });
type ApiKeyConfig = z.infer<typeof ApiKeyConfig>;
```

---

## 8. Error Handling

### Error Codes

Use enums for better discoverability and refactoring:

```typescript
export enum ApiKeyErrorCode {
  ApiKeyNotFound = 'api_key_not_found',
  FailedToCreateApiKey = 'failed_to_create_api_key',
}
```

Be explicit about which error codes each function can return:

```typescript
// Good - explicit about possible errors
): Promise<Result<Data, { code: ApiKeyErrorCode.ApiKeyNotFound | ApiKeyErrorCode.FailedToDecryptApiKey; message: string }>>

// Bad - too generic
): Promise<Result<Data, { code: ApiKeyErrorCode; message: string }>>
```

### Result Piping

Forward errors early instead of nesting:

```typescript
const userResult = await getUser({ id });
if (!userResult.success) {
  return userResult;
}
// continue with userResult.data
```

### Catching Errors

Use `asError()` helper (from `workroom/backend/src/utils/error.ts`) instead of casting:

```typescript
// Good
import { asError } from '../utils/error';

try {
  ...
} catch (err) {
  const error = asError(err);
  return {
    success: false,
    error: {
      code: 'failed_to_create',
      message: `Failed to create entity: ${error.name}: ${error.message}`,
    },
  };
}

// Bad
} catch (err) {
  const error = err as Error;
}
```

---

## 9. Validation

### Client vs Server

- Client and server validation must be kept in sync
- Server is the source of truth for data integrity
- Use `.trim()` on string validation to prevent whitespace-only values
- Client validation must have meaningful error messages

```typescript
// Client (frontend)
const schema = z.object({
  name: z.string().trim().min(1, 'Name is required').max(100, 'Name must be at most 100 characters'),
});

// Server (backend)
z.string().trim().min(1).max(100)
```

---

## 10. Backend

### Async

Never use blocking/sync calls, especially for file handling. Always use async.

### SQL

- Optimize for speed and simplicity
- Avoid N+1 queries; prefer joins or batch fetches
- Select only needed columns when performance matters

### Database Access

All database operations must go through `DatabaseClient` methods, not raw Kysely queries:

```typescript
// Bad - leaking Kysely
const createThing = ({ database }: { database: Kysely<Database> }) => ...

// Good - encapsulated
const createThing = ({ database }: { database: DatabaseClient }) => ...

// DatabaseClient method pattern
async selectThingById({ id }: { id: string }): Promise<Result<Thing | null>> {
  return asResult(() =>
    this.database
      .selectFrom('thing')
      .selectAll()
      .where('id', '=', id)
      .executeTakeFirst()
      .then((result) => result ?? null),
  );
}
```

### TRPC Error Helpers

Place shared TRPC error helpers in `trpc/routes/utils.ts`. Don't export helpers from route files (they get spread into the router):

```typescript
// trpc/routes/utils.ts
export const toTRPCError = (error: { code: ErrorCode; message: string }) => ({
  code: errorToTRPCCode[error.code],
  message: error.message,
});

export const notAvailableForConfiguration = ({
  feature,
}: {
  feature: 'API keys management' | 'User management';
}) => ({
  code: 'NOT_IMPLEMENTED' as const,
  message: `${feature} is not configured`,
});

// Usage
throw new TRPCError(toTRPCError(result.error));
```

### Logging

Always include both `errorMessage` and `errorName` in logger.error calls:

```typescript
monitoring.logger.error('Failed to do something', {
  entityId: id,
  errorMessage: result.error.message,
  errorName: result.error.code,
});
```

**User-facing error messages**: Don't leak internal error details. Use generic messages with identifiers:

```typescript
// Bad - leaks internal details
message: result.error.message

// Good - generic with identifier
message: `Failed to create API key "${name}"`
```

**Log at the right layer - avoid duplicates**:
- Managers/services: Log errors internally, return user-friendly messages
- TRPC routes calling managers: Don't log again, just convert via `toTRPCError()`
- TRPC routes calling database directly: Log at TRPC layer with generic user message
- TRPC middleware: `errorLoggingMiddleware` in `trpc.ts` logs all error responses automatically

```typescript
// Manager already logs -> TRPC just converts
const result = await apiKeysManager.createApiKey({ name });
if (!result.success) {
  throw new TRPCError(toTRPCError(result.error));
}

// Database call -> TRPC logs
const result = await database.getUser({ id });
if (!result.success) {
  monitoring.logger.error('Failed to get user', {
    userId: id,
    errorMessage: result.error.message,
    errorName: result.error.code,
  });
  throw new TRPCError({ code: 'INTERNAL_SERVER_ERROR', message: 'Failed to get user' });
}
```

---

## 11. Frontend

### React Handlers

- Handlers should be prefixed with `handle`: `handleSubmit`, `handleNameChange`
- Use `useCallback` only when there's a clear stability gain (passed to memoized children, used in dependency arrays). Don't wrap already-stable functions (React Query's `mutate`, `invalidate`)
- Props for callbacks should be descriptive: `onCardClick`, `onProviderFormSubmit`, `onApiKeyDelete`
- Never spread props. Always define them explicitly

### Props

- If a prop is always passed by all consumers, make it required
- Optional props add unnecessary conditional logic

```typescript
// Bad - always passed but optional
type Props = {
  onCreate?: () => void;
};

// Good - required when always used
type Props = {
  onCreate: () => void;
};
```

### Mutations

Use `.mutate()` with `onSuccess`/`onError` callbacks close to usage:

```typescript
updateMutation.mutate(
  { id, name },
  {
    onSuccess: () => onUpdated(),
    onError: (error) => addSnackbar({ message: error.message, variant: 'danger' }),
  },
);
```

Don't use `instanceof Error` checks - React Query returns QueryError which always has `.message`:

```typescript
// Bad
const errorMessage = error instanceof Error ? error.message : 'Failed';

// Good
addSnackbar({ message: error.message, variant: 'danger' });
```

### Component Ownership

**Dialogs/components that are primary consumers of mutations should own them**:

```typescript
// Bad - parent owns mutation, passes callback
<CreateDialog onSubmit={async (name) => {
  const result = await createMutation.mutateAsync({ name });
  return result;
}} />

// Good - dialog owns mutation internally
<CreateDialog onClose={handleClose} tenantId={tenantId} />
```

**Route-based dialogs should internalize all side effects**: navigation, cache invalidation, snackbars:

```typescript
// Bad - route orchestrates side effects
function View() {
  const navigate = useNavigate();
  const utils = trpc.useUtils();
  const handleClose = () => navigate({ to: '/list', params: { tenantId } });
  const handleUpdated = () => {
    utils.entity.list.invalidate();
    addSnackbar({ message: 'Updated', variant: 'success' });
    handleClose();
  };
  return <EditDialog data={data} onClose={handleClose} onUpdated={handleUpdated} />;
}

// Good - dialog owns its lifecycle
function View() {
  const { data } = trpc.entity.get.useQuery({ id });
  return <EditDialog data={data} tenantId={tenantId} />;
}

// Inside EditDialog
const EditDialog: FC<Props> = ({ data, tenantId }) => {
  const navigate = useNavigate();
  const trpcUtils = trpc.useUtils();
  const handleClose = useCallback(() => {
    navigate({ to: '/list', params: { tenantId } });
  }, [navigate, tenantId]);
  // mutation onSuccess: invalidate, snackbar, handleClose()
};
```

### Route Loaders

Fetch required data in route loaders for immediate availability. Pass loader data as `initialData` to keep queries reactive:

```typescript
export const Route = createFileRoute('/path/')({
  component: RouteComponent,
  loader: async ({ context: { trpc } }) => {
    const data = await trpc.entity.list.ensureData();
    return { data };
  },
});

function RouteComponent() {
  const { data: initialData } = Route.useLoaderData();
  const { data } = trpc.entity.list.useQuery(undefined, { initialData });
}
```

### Route Structure

Parent routes with child dialogs should be at `path.tsx`, not `path/index.tsx`. This prevents blank screens when navigating:

```
// Good
configuration/api-keys.tsx          <- parent with <Outlet />
configuration/api-keys/new.tsx      <- child dialog
configuration/api-keys/$id.tsx      <- child dialog

// Bad - causes blank screen during navigation
configuration/api-keys/index.tsx
configuration/api-keys/new.tsx
configuration/api-keys/$id.tsx
```

### Dialogs

- **Single instance**: Never conditionally return different `<Dialog>` components. Use one `<Dialog>` with memoized content to preserve focus
- **No content padding**: `Dialog.Content` handles its own padding. Don't wrap children in `<Box p="$4">`

### Forms

- The `primary` button should always be first in dialog actions

### Buttons

- Cancel: `variant="secondary"`
- Delete/destructive actions: `variant="destructive"`

### Styling

Use theme tokens over hardcoded values: `theme.colors.*`, `theme.fonts.*` instead of `#1a1a1a`, `monospace`.

### Component Structure

- Don't wrap components in `<Box>` if it adds no styling
- Separate loading from empty states: split `if (isLoading || !data)` into distinct conditions
- Pass objects directly when props match the shape; don't destructure and reconstruct

### TableWithFilter

Actions column should have `width: 32` and `required: true`:

```typescript
columns: [
  { id: 'name', title: 'Name', sortable: true, required: true },
  { id: 'actions', title: '', sortable: false, required: true, width: 32 },
]
```

### Delete Confirmations

Use `useDeleteConfirm` hook from `@sema4ai/layouts`:

```typescript
const onDeleteConfirm = useDeleteConfirm(
  { entityName: item.name, entityType: 'API key' },
  [],
);

const onDelete = onDeleteConfirm(() => {
  deleteMutation.mutate({ id: item.id }, { onSuccess, onError });
});
```
