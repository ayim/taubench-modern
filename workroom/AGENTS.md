# Context

The Work Room folder is an app that comprises of 3 main pieces:

- `@backend`: backend (in express) responsible for routing request to the agent-server, located outside of this folder, both locally and in production
- `@frontend`: frontend (in react) responsible for displaying the UI.
- `@spar-ui`: re-usable react components consumed by the frontend and another service (Studio) located outside of this folder. The code written in spar-ui is run in an electron app and built using webapp. Keep that in mind for any implementation

# Glossary

- `thread` is the technical term, `conversation` should be used for customer facing errors and UIs

# High-level guidelines

## Type Safety

### API Types - Use Helper Types

Use `ServerRequest` and `ServerResponse` from `@spar-ui/src/queries/shared.ts` instead of raw path accessors:

```typescript
// ✅ Preferred
type McpServerCreate = ServerRequest<'post', '/api/v2/mcp-servers/', 'requestBody'>;
type ApiHeaders = ServerRequest<'put', '/api/v2/mcp-servers/{mcp_server_id}', 'requestBody'>['headers'];

// ❌ Avoid
type McpServerCreate = paths['/api/v2/mcp-servers/']['post']['requestBody']['content']['application/json'];
```

### Tie Types to Endpoints, Not Internal Components

Types should be derived from API endpoints (request/response payloads), not internal component schemas. API endpoints are stable; internal schemas can change without notice.

```typescript
// ✅ Types from endpoints
type McpServer = ServerResponse<'get', '/api/v2/mcp-servers/{mcp_server_id}'>;

// ❌ Avoid importing from internal component schemas
import { SomeInternalType } from './components/internal';
```

### No Type Casting

Avoid `as Type` casts - refactor code to not need them. If you find yourself casting, the types are likely wrong.

### No `instanceof Error` Checks for Query Errors

React Query returns `QueryError`, not generic `Error`. Checking `instanceof Error` is dead code:

```typescript
// ❌ Dead code - react-query returns QueryError
{
  error instanceof Error ? error.message : 'Unknown error';
}

// ✅ QueryError always has message
{
  error.message;
}
```

## Code Comments

### No AI-Generated Comments

Comments like `// Handle form submission` add zero value. If a section needs explanation, extract it into a named component or function instead.

### No Implementation Comments

Don't document "how" the code works - the code itself should be readable. Implementation comments age poorly and become incorrect when code changes.

### Linear Ticket References for TODOs

Always reference Linear tickets in TODO comments with the exact link to the ticket:

```typescript
// TODO https://linear.app/sema4ai/issue/ENG-24/ui-implementations-for-mcp-oauth-user-auth-and-client-credential: Add OAuth2 PKCE support
```

## Component Architecture

### Shared Logic Belongs in spar-ui

Logic needed by both SPAR (workroom/frontend) and Studio must live in `spar-ui`. Don't write business logic in `frontend` that will need to be reimplemented.

### Self-Contained Components

Shared components should fetch their own data when possible:

```typescript
// ✅ Preferred - component fetches its own data
<EditMcpServerDialog mcpServerId={id} onClose={handleClose} />

// ❌ Avoid - consumer must fetch and pass data
<EditMcpServerDialog server={fetchedServer} onClose={handleClose} />
```

### No Unnecessary Barrel Files

Don't create barrel files (index.ts) just to re-export. Export directly from the source file or the main component index.

### Explicit Props Over Defaults

Boolean props should be explicit at call sites, not rely on defaults:

```typescript
// ✅ Preferred - explicit
<Dialog showStdioTransport={false} />

// ❌ Avoid - relies on implicit default
<Dialog showStdioTransport />
```

### Export Constants for Shared Configuration

Export configuration constants from component index files:

```typescript
// In MCPServers/index.ts
export const DEFAULT_MCP_TYPE = 'generic_mcp';
export const SERVER_TYPE_LABELS = { ... };

// In consuming code
import { DEFAULT_MCP_TYPE } from '@spar-ui/components/MCPServers';
```

### Platform-Specific Features

When a feature is only available in one platform (Workroom vs Studio), document it clearly:

```typescript
/**
 * Create Hosted MCP Server mutation (with file upload)
 * Only available in Workroom (not Studio).
 */
export const useCreateHostedMcpServerMutation = ...
```

## Working in @spar-ui

### Scripts

- Run `npm run test` for type-checking

### Guidelines

- When adding new business logic for queries and mutations, there are two options:
  - A. Add the logic inside the handler of the query or mutation
  - B. Define a new [SparAPIClient interface](@spar-ui/src/api/index.ts) handler and call it from the query or mutation body
  - Pick A when you only need to call the `queryAgentServer`, there are no feature flag requirements nor electron-specific handling needed
  - Pick B as a fallback or when the operator explicitly asks you to do so
- Mutations and queries must be defined in [queries](@spar-ui/src/queries/) - find the most relevant place depending on the work at hand

### Query and Mutation Patterns

Use the `createSparQuery` and `createSparMutation` helpers from `shared.ts`:

```typescript
// Query options pattern
export const getMCPServerQueryOptions = createSparQueryOptions<{ mcpServerId: string }>()(
  ({ sparAPIClient, mcpServerId }) => ({
    queryKey: mcpServerQueryKey(mcpServerId),
    queryFn: async () => {
      const response = await sparAPIClient.queryAgentServer('get', '/api/v2/mcp-servers/{mcp_server_id}', {
        params: { path: { mcp_server_id: mcpServerId } },
      });
      if (!response.success) {
        throw new QueryError(response.message || 'Failed to fetch MCP server', {
          code: response.code,
          resource: ResourceType.McpServer,
        });
      }
      return response.data;
    },
  }),
);

// Create hook from options
export const useMcpServerQuery = createSparQuery(getMCPServerQueryOptions);
```

### Query Key Conventions

Export query keys as functions for consistency and cache invalidation:

```typescript
// ✅ Preferred - functions for query keys
export const mcpServersQueryKey = () => ['mcp-servers'];
export const mcpServerQueryKey = (mcpServerId: string) => ['mcp-server', mcpServerId];

// Use in mutations for cache updates
onSuccess: () => {
  queryClient.invalidateQueries({ queryKey: mcpServersQueryKey() });
};
```

### Error Handling

- ALL errors thrown must use `QueryError` and be customer-facing. If unsure about how technical to get, ask the operator
- ALL mutations must have an `onError` handler defined. Use `addSnackbar` and `getSnackbarContent`
- For inline error display (not snackbar), add a no-op with explanation:
  ```typescript
  onError: () => {
    // No-op: Error displayed inline in form, not via snackbar
  };
  ```
- Use `mutation.error` directly instead of duplicating error state with useState

### Forms

- Separate form state from other state - don't mix react-hook-form with useState for related data
- Use `useFieldArray` for dynamic fields instead of manual `setValue` calls
- Split Dialog content from wrapper for automatic state cleanup on close:
  ```typescript
  export const NewDialog: FC<Props> = (props) => (
    <Dialog open={props.open} onClose={props.handleClose}>
      <NewDialogContent {...props} />
    </Dialog>
  );
  ```
- Extract complex conditional JSX to variables:
  ```typescript
  const errorMessage = validationError ?? form.formState.errors.root?.message ?? null;
  {errorMessage && <ErrorBanner>{errorMessage}</ErrorBanner>}
  ```
- Use switch with `satisfies never` for exhaustive state handling:
  ```typescript
  switch (state.type) {
    case 'pending': return <Pending />;
    case 'complete': return <Complete data={state.data} />;
    default: state.type satisfies never;
  }
  ```

### Naming Conventions

- Query options: use `getXxxQueryOptions` pattern (e.g., `getMCPServerQueryOptions`)
- Unused callback parameters: prefix with underscore (e.g., `(_files: File[]) => void`)

### Zod Schemas

When using `superRefine` for cross-field validation, question if the API types are correct. `superRefine` often indicates a mismatch between form and API types:

```typescript
// If you find yourself doing this a lot, the API types may need adjustment
.superRefine((values, ctx) => {
  if (values.type === 'hosted' && !values.url) {
    ctx.addIssue({ ... });
  }
});
```

Prefer discriminated unions in the API itself when possible.

### Document Intelligence

For detailed documentation on the Document Intelligence (DocIntel) feature, see [DocIntel README](spar-ui/src/components/DocIntel/README.md).

## Testing

### Unit Tests Required

All utility/transform functions must have unit tests.

### Use it.each for Parameterized Tests

```typescript
// ✅ Preferred
it.each([
  { input: 'a', expected: 'A' },
  { input: 'b', expected: 'B' },
])('transforms $input to $expected', ({ input, expected }) => {
  expect(transform(input)).toBe(expected);
});

// ❌ Avoid repeated test blocks
it('transforms a to A', () => { ... });
it('transforms b to B', () => { ... });
```

### Test Error Messages, Not Framework Internals

Test user-facing error messages, not Zod/framework internal structures:

```typescript
// ✅ Test user-facing message
expect(result.error.message).toBe('URL is required');

// ❌ Don't test framework internals
expect(result.error.issues[0].code).toBe('invalid_type');
```

### Explicit Test Data

Use explicit object syntax with no optional fields:

```typescript
// ✅ Preferred
createMockServer({ name: 'test', url: 'https://example.com' });

// ❌ Avoid positional args or undefined placeholders
createMockServer('test', undefined, 'https://example.com');
```

## File Organization

### Keep Related Code Together

Group related schemas, types, and utilities in the same directory as the component that uses them:

```
MCPServers/
├── index.ts              # Public exports + constants
├── schemas/
│   ├── mcpFormSchema.ts  # Form schemas + transform functions
│   └── mcpAuthSchema.ts  # Auth-specific schemas
├── MCPServerDialog/
│   ├── NewMcpServerDialog.tsx
│   └── EditMcpServerDialog.tsx
└── MCPServerAuth/
    └── MCPServerAuthFields.tsx
```

## Working in workroom

### Scripts

- Run `npm run build` for build

## Working in workroom frontend

### Scripts

- Run `npm run test:types` for type-checking

### Styling

**IMPORTANT**

- The UI follows strict conventions established by `@sema4ai/theme` `@sema4ai/components` and `@sema4ai/icons`.
- Custom styling (using styled components see below) should be avoided as much as possible and used as a very last resort, only after confirming with the user\*\*

Always reach for components from `@sema4ai/theme` `@sema4ai/components` and `@sema4ai/icons`.

_Prompt the user to leverage the `@sema4ai/design-system-mcp` MCP server - the documentation can be found here: https://github.com/Sema4AI/design-system/blob/master/mcp/README.md_

- **Never use inline `style` props** - Always use styled components from `@sema4ai/theme`
- **Always use tokens from the theme: this applies to most CSS properties: color, border-radius, gap, padding, background, background-color...**.

```
_BAD_
 background-color: #1a1a1a;
```

```
_GOOD_
color: ${({ theme }) => theme.colors.background.panels.color};
```

- Use `styled(Component)` to create styled versions of components
- For dynamic styles based on props, use transient props (prefixed with `$`) to avoid passing them to the DOM

```tsx
// Good
const MyButton = styled(Button)<{ $isActive?: boolean }>`
  opacity: ${({ $isActive }) => ($isActive ? 1 : 0.6)};
`;

// Bad
<Button style={{ opacity: isActive ? 1 : 0.6 }} />;
```
