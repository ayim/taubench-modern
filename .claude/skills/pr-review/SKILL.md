---
name: pr-review
description: Guidelines for reviewing PRs in the agent-platform's workroom codebase. Use when reviewing code, addressing PR feedback, or writing new code to ensure consistency. Invoke this skill when the user is opening a PR. Keywords: "pr", "workroom", "review"
---

# PR Review Guidelines

**IMPORTANT**
- New learnings should be added to this list.
- Conflicting learnings should be raised.
- Formatting, linting and type-checking are part of the review process: a PR not passing the checks is not ready for review

Distilled learnings from code reviews. Use these as a checklist when reviewing or writing code.

## Shared

### Keep It Simple (and Readable)
- Readability trumps cleverness. Write code that's easy to understand at first glance.
- Avoid premature optimization. Performance matters WHEN it makes sense, not by default.
- Common over-engineering to avoid:
  - `useMemo`/`useCallback` for values that don't need memoization
  - IIFEs when a simple ternary suffices
  - Abstractions for one-time operations
- If complexity is truly needed, justify it with a comment or test.

### No Casting
- Never use `as` casts. Fix types at the source instead.
- If a branded type is needed (e.g., `SecretDataReference<string>`), update the database/interface types to use it directly.

### Constants
- Use `as const` for constant values to get literal types:
  ```typescript
  const API_KEY_PREFIX = 's4w' as const;
  ```

### Error Codes
- Use enums for error codes for better discoverability and refactoring:
  ```typescript
  export enum ApiKeyErrorCode {
    ApiKeyNotFound = 'api_key_not_found',
    FailedToCreateApiKey = 'failed_to_create_api_key',
  }
  ```
- Be explicit about which error codes each function can return:
  ```typescript
  // Good - explicit about possible errors
  ): Promise<Result<Data, { code: ApiKeyErrorCode.ApiKeyNotFound | ApiKeyErrorCode.FailedToDecryptApiKey; message: string }>>

  // Bad - too generic
  ): Promise<Result<Data, { code: ApiKeyErrorCode; message: string }>>
  ```

### Client vs Server Validation
- Client and server validation should be kept in sync
- Server is the source of truth for data integrity and protection
- Use `.trim()` on string validation to prevent whitespace-only values
- Field validation on the client should ALWAYS have meaningful error messages defined

_GOOD_
```typescript

// Client (frontend)
const schema = z.object({
  name: z.string().trim().min(1, 'Name is required').max(100, 'Name must be at most 100 characters'),
});

// Server (backend)
z.string().trim().min(1).max(100)
```
_BAD_
```typescript
// Client (frontend)
const schema = z.object({
  name: z.string().trim().min(1).max(100),
});

// Server (backend)
z.string()
```
### Extract Reusable Helpers
- When a pattern appears twice, extract it into a helper
- Place helpers in appropriate utils location based on usage scope
- Write unit tests for non-trivial helpers

### Function Naming
- Use descriptive names that indicate the action:
  ```typescript
  // Good
  setLastUsedAt

  // Less clear
  touchApiKey
  ```

## Backend

### Catching Errors
- Use `asError()` helper instead of casting:
  ```typescript
  // Bad
  } catch (err) {
    const error = err as Error;
  }

  // Good
  } catch (err) {
    const error = asError(err);
  }
  ```

### Result to Framework Error Conversion
- Create typed helpers to convert Result errors to framework errors:
  ```typescript
  const toTRPCError = (error: { code: ApiKeyErrorCode; message: string }): { code: TRPC_ERROR_CODE_KEY; message: string } => ({
    code: apiKeyErrorToTRPCCode[error.code],
    message: error.message,
  });

  // Usage
  throw new TRPCError(toTRPCError(result.error));
  ```

### Monitoring/Logging
- Always include both `errorMessage` and `errorName` in logger.error calls:
  ```typescript
  monitoring.logger.error('Failed to do something', {
    entityId: id,              // Include relevant identifiers
    errorMessage: result.error.message,
    errorName: result.error.code,
  });
  ```
- **User-facing error messages**: Don't leak internal error details. Use generic messages with identifiers:
  ```typescript
  // Bad - leaks internal details
  message: result.error.message

  // Good - generic with identifier
  message: `Failed to create API key "${name}"`
  message: `Failed to update API key (id: "${id}")`
  ```
- **Log at the right layer - avoid duplicates**:
  - Managers/services: Log errors internally, return user-friendly messages
  - TRPC routes calling managers: Don't log again, just convert error via `toTRPCError()`
  - TRPC routes calling database directly: Log at TRPC layer with generic user message
  - TRPC middleware: `errorLoggingMiddleware` in `trpc.ts` logs all error responses automatically
  ```typescript
  // Manager already logs → TRPC just converts
  const result = await apiKeysManager.createApiKey({ name });
  if (!result.success) {
    throw new TRPCError(toTRPCError(result.error));
  }

  // Database call → TRPC logs
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

### Database Access Through DatabaseClient
- All database operations must go through `DatabaseClient` methods, not raw Kysely queries
- Never pass `Kysely<Database>` to functions; pass `DatabaseClient` instead
- Database methods should return `Result<T>` using `asResult()` wrapper
  ```typescript
  // Bad - leaking Kysely
  const createThing = ({ database }: { database: Kysely<Database> }) => ...

  // Good - encapsulated
  const createThing = ({ database }: { database: DatabaseClient }) => ...

  // Good - DatabaseClient method
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

### Co-locate TRPC Error Helpers
- Place shared TRPC error helpers in `trpc/routes/utils.ts`
- Don't export helpers from route files (they get spread into the router)
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

  // Usage in route files
  throw new TRPCError(toTRPCError(result.error));
  throw new TRPCError(notAvailableForConfiguration({ feature: 'API keys management' }));
  ```

## Frontend

### Error Handling
- Use `.mutate()` with `onSuccess`/`onError` callbacks close to usage:
  ```typescript
  updateMutation.mutate(
    { id, name },
    {
      onSuccess: () => onUpdated(),
      onError: (error) => addSnackbar({ message: error.message, variant: 'danger' }),
    },
  );
  ```
- Don't use `instanceof Error` checks - React Query returns QueryError which always has `.message`:
  ```typescript
  // Bad
  const errorMessage = error instanceof Error ? error.message : 'Failed';

  // Good
  addSnackbar({ message: error.message, variant: 'danger' });
  ```

### Props Should Be Required When Always Used
- If a prop is always passed by all consumers, make it required
- Optional props add unnecessary conditional logic and type guards
  ```typescript
  // Bad - always passed but optional
  type Props = {
    onCreate?: () => void;
    onDelete?: (item: Item) => void;
  };

  // Good - required when always used
  type Props = {
    onCreate: () => void;
    onDelete: (item: Item) => void;
  };
  ```

### Encapsulate Mutation Logic in Components
- Dialogs/components that are primary consumers of mutations should own them
- Don't pass mutation callbacks as props when the component can own the mutation
  ```typescript
  // Bad - parent owns mutation, passes callback
  <CreateDialog onSubmit={async (name) => {
    const result = await createMutation.mutateAsync({ name });
    return result;
  }} />

  // Good - dialog owns mutation internally
  <CreateDialog onClose={handleClose} tenantId={tenantId} />
  ```

### Route-Based Dialog Components Own Their Lifecycle
- Route-based dialogs should internalize all side effects: navigation, cache invalidation, snackbars
- Route files should only pass data props; the dialog component owns its lifecycle
- Use `useNavigate` and tRPC utils internally rather than exposing callbacks like `onClose` or `onUpdated`
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

### Use Loaders for Route Data
- Fetch required data in route loaders for immediate availability
- Use `ensureData` for TRPC queries in loaders
- Pass loader data as `initialData` to keep queries reactive to invalidations
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
    // Use initialData so query stays reactive to invalidations
    const { data } = trpc.entity.list.useQuery(undefined, { initialData });
  }
  ```

### Dialog Patterns
- **Single instance**: Never conditionally return different `<Dialog>` components. Use one `<Dialog>` with memoized content to preserve focus.
- **No content padding**: `Dialog.Content` handles its own padding. Don't wrap children in `<Box p="$4">`.

### Button Variants
- **Cancel**: `variant="secondary"`
- **Delete/destructive actions**: `variant="destructive"`


### Form patterns

- The `primary` button should always be first in the dialog actions

### Styling
- **Theme tokens over hardcoded values**: Use `theme.colors.*`, `theme.fonts.*` instead of `#1a1a1a`, `monospace`.

### Component Structure
- **Avoid unnecessary wrappers**: Don't wrap components in `<Box>` if it adds no styling.
- **Separate loading from empty states**: Split `if (isLoading || !data)` into distinct conditions with appropriate UI for each.
- **Pass objects directly**: Don't destructure and reconstruct objects when props match the shape. Pass the object directly.

### TableWithFilter
- Actions column should have `width: 32` and `required: true`:
  ```typescript
  columns: [
    { id: 'name', title: 'Name', sortable: true, required: true },
    { id: 'actions', title: '', sortable: false, required: true, width: 32 },
  ]
  ```

### Delete Confirmations
- Use `useDeleteConfirm` hook from `@sema4ai/layouts` instead of manual delete dialogs
- The hook handles the confirmation dialog automatically
  ```typescript
  const onDeleteConfirm = useDeleteConfirm(
    { entityName: item.name, entityType: 'API key' },
    [],
  );

  const onDelete = onDeleteConfirm(() => {
    deleteMutation.mutate({ id: item.id }, { onSuccess, onError });
  });
  ```

### Route Structure
- Parent routes with child dialogs should be at `path.tsx`, not `path/index.tsx`
- This prevents blank screens when navigating between parent and child routes
  ```
  // Good - parent at path.tsx, children in path/ folder
  configuration/api-keys.tsx          <- parent with <Outlet />
  configuration/api-keys/new.tsx      <- child dialog
  configuration/api-keys/$id.tsx      <- child dialog

  // Bad - parent as sibling to children
  configuration/api-keys/index.tsx    <- causes blank screen during navigation
  configuration/api-keys/new.tsx
  configuration/api-keys/$id.tsx
  ```
