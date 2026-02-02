# Frontend Engineering Standards (React + TypeScript)

**Version:** 1.0  
**Last Updated:** 2026-01-21

_Same core principles as backend: KISS, YAGNI, type safety, fail fast._

---

## 1. TypeScript Standards

### 1.1 Strict Mode Required

Enable `strict`, `noUncheckedIndexedAccess`, and `noImplicitReturns` in `tsconfig.json`.

### 1.2 No `any`

**Rule:** Use `unknown` and narrow with type guards.

```typescript
// ❌ BAD
function process(data: any) {
  return data.value;
}

// ✅ GOOD
function process(data: unknown): string {
  if (isValidResponse(data)) return data.value;
  throw new Error('Invalid data');
}
```

### 1.3 Discriminated Unions for State

**Rule:** Model states explicitly — don't rely on boolean flag combinations.

```typescript
// ❌ BAD: Boolean flags
interface State {
  isLoading: boolean;
  isError: boolean;
  data: User | null;
}

// ✅ GOOD: Discriminated union
type State =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: User }
  | { status: 'error'; error: Error };
```

### 1.4 Zod for API Responses

**Rule:** API responses are `unknown` until validated.

```typescript
const UserSchema = z.object({
  id: z.string().uuid(),
  name: z.string().min(1),
  email: z.string().email(),
});

type User = z.infer<typeof UserSchema>;

async function fetchUser(id: string): Promise<User> {
  const res = await fetch(`/api/users/${id}`);
  return UserSchema.parse(await res.json());
}
```

---

## 2. Component Architecture

### 2.1 Composition over Configuration

**Rule:** Prefer composable components over prop-heavy "god components."

```typescript
// ❌ BAD: 20+ props
<DataTable data={d} sortable filterable paginated onSort={...} onFilter={...} />

// ✅ GOOD: Composable
<DataTable data={d}>
  <DataTable.SortableColumn field="name">Name</DataTable.SortableColumn>
  <DataTable.Pagination pageSize={20} />
</DataTable>
```

### 2.2 Container/Presentational Split

**Rule:** Separate data-fetching from presentation.

```typescript
// Container: handles data
function UserListContainer() {
  const { data, status } = useUsers();
  if (status === "loading") return <Spinner />;
  return <UserList users={data} />;
}

// Presentational: pure rendering
function UserList({ users }: { users: User[] }) {
  return <ul>{users.map(u => <UserItem key={u.id} user={u} />)}</ul>;
}
```

### 2.3 Explicit Props

**Rule:** Define `children` explicitly. Use `ComponentNameProps` naming.

```typescript
interface CardProps {
  children: React.ReactNode;
  title?: string;
}
```

---

## 3. State Management

### 3.1 State Hierarchy

1. **Local (useState):** UI-only state
2. **Server (React Query):** API data
3. **Global (Zustand/Context):** App-wide state (auth, theme)

**Rule:** Start local. Only lift when necessary.

### 3.2 Server State

**Rule:** Use React Query for all API data. Don't store API responses in Redux/Zustand.

### 3.3 No Prop Drilling Beyond 2 Levels

**Rule:** If passing through 3+ components, use Context or composition.

### 3.4 Forms + Mutations

**Rule:** Use `react-hook-form` + `zodResolver` for forms.
Show validation errors inline.

**Rule:** Use TRPC mutations for form submits. Invalidate caches on success and show
snackbar errors on failure.

```typescript
const form = useForm<FormValues>({
  resolver: zodResolver(schema),
  defaultValues,
  mode: 'onChange',
});

const mutation = trpc.resource.create.useMutation();

const onSubmit = form.handleSubmit((values) => {
  mutation.mutate(values, {
    onSuccess: () => trpcUtils.resource.list.invalidate(),
    onError: (error) => addSnackbar({ message: error.message, variant: 'danger' }),
  });
});
```

---

## 4. Error Handling

### 4.1 Error Boundaries Required

**Rule:** Wrap major UI sections in Error Boundaries.

### 4.2 React Query Errors

**Rule:** React Query returns `QueryError`. Don't use `instanceof Error` checks for query errors.

```typescript
// ❌ BAD
if (error instanceof Error) {
  return error.message;
}

// ✅ GOOD
return error.message;
```

### 4.3 Fail Fast

**Rule:** Don't silently return empty arrays on error.

```typescript
// ❌ BAD: Masking errors
async function fetchUsers(): Promise<User[]> {
  try {
    return await api.get('/users');
  } catch {
    return [];
  } // Silent failure!
}

// ✅ GOOD: Let errors propagate
async function fetchUsers(): Promise<User[]> {
  const res = await fetch('/api/users');
  if (!res.ok) throw new ApiError(`Failed: ${res.status}`);
  return UserArraySchema.parse(await res.json());
}
```

---

## 5. Performance

### 5.1 Memoization

**Rule:** Don't `useMemo`/`useCallback` everything. Profile before optimizing.

### 5.2 Virtualization

**Rule:** Lists > 100 items must use virtualization (`@tanstack/react-virtual`).

### 5.3 Code Splitting

**Rule:** Lazy-load routes and heavy components.

```typescript
const Dashboard = lazy(() => import('./pages/Dashboard'));
```

---

## 6. Testing

### 6.1 Test Behavior, Not Implementation

**Rule:** Use React Testing Library. Query by role/label, not test IDs.

```typescript
// ❌ BAD
screen.getByTestId('submit-btn');

// ✅ GOOD
screen.getByRole('button', { name: /submit/i });
```

### 6.2 Mock API Layer, Not Hooks

```typescript
// ❌ BAD: Mocking internal hook
vi.mock('./useUser', () => ({ useUser: () => ({ data: mockUser }) }));

// ✅ GOOD: Mock at API boundary (MSW)
server.use(http.get('/api/users/:id', () => HttpResponse.json(mockUser)));
```

### 6.3 Accessibility

**Rule:** Include `jest-axe` checks in component tests.

```typescript
test("no a11y violations", async () => {
  const { container } = render(<UserCard user={mockUser} />);
  expect(await axe(container)).toHaveNoViolations();
});
```

---

## 7. Styling

### 7.1 Theme + Design System

**Rule:** Use `@sema4ai/theme`, `@sema4ai/components`, and `@sema4ai/icons`.
Avoid inline `style` props.

### 7.2 Styled Components + Tokens

**Rule:** Use `styled(Component)` with theme tokens. No raw hex values.

```typescript
// ❌ BAD
<div style={{ backgroundColor: "#1a1a1a" }} />

// ✅ GOOD
const Panel = styled.div`
  background-color: ${({ theme }) => theme.colors.background.panels.color};
`;
```

### 7.3 Motion Preferences

**Rule:** Respect reduced motion preferences in animations/transitions.

---

## 8. Code Organization

### 8.1 Feature-Based Structure

```
src/
├── features/
│   ├── users/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── api/
│   │   └── types.ts
│   └── dashboard/
├── shared/          # Reusable components, hooks, utils
└── app/             # Shell, routing, providers
```

### 8.2 Import Order

```typescript
// 1. React
// 2. External libraries
// 3. Internal shared (@/)
// 4. Feature-local (./)
```

---

## 9. PR Checklist (Frontend-Specific)

- [ ] No `any` types
- [ ] Zod schemas for API responses
- [ ] Error boundaries for new routes
- [ ] Loading and error states handled
- [ ] Create/CTA flows are functional (no dead ends)
- [ ] Tables use `TableWithFilter` and destructive actions use `useDeleteConfirm`
- [ ] Forms use `react-hook-form` + `zodResolver`, mutations handle cache + snackbar errors
- [ ] Secrets are masked by default and revealed only on explicit user action
- [ ] Responsive (mobile + desktop)
- [ ] Keyboard navigation works
- [ ] No axe violations

---

## Summary: Frontend Commandments

1. **Strict TypeScript** — No `any`, discriminated unions for state
2. **Validate at boundaries** — Zod for API responses
3. **Composition > configuration** — Small, composable components
4. **Server state in React Query** — Not Redux
5. **Fail fast** — Don't mask API errors
6. **Test behavior** — Query by role, mock at API layer
7. **Virtualize long lists** — > 100 items
8. **Lazy-load routes** — Code split by default
9. **Theme + tokens** — `@sema4ai/theme` and design system only
10. **Accessibility always** — axe tests, keyboard nav
