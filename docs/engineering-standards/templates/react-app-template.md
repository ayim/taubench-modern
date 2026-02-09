# React App Template

> **For AI Assistants:** Invoke `typescript-guidelines` skill. Use: discriminated unions, Zod, TRPC, no `any`. Follow workroom structure.

**Applies to**: `workroom/frontend/`, `workroom/spar-ui/`

---

## Project Structure

```
workroom/frontend/
├── src/
│   ├── features/[feature-name]/
│   │   ├── components/
│   │   ├── hooks/
│   │   └── types.ts
│   ├── shared/
│   │   ├── components/
│   │   ├── hooks/
│   │   └── utils/
│   └── trpc/client.ts
└── package.json
```

---

## Key Dependencies

```json
{
  "dependencies": {
    "@sema4ai/components": "latest",
    "@tanstack/react-router": "latest",
    "@tanstack/react-query": "latest",
    "@trpc/client": "latest",
    "react": "latest",
    "zod": "latest",
    "zustand": "latest",
    "immer": "latest"
  }
}
```

---

## Component Pattern

```typescript
import { z } from 'zod';

// Schema
const schema = z.object({
  id: z.string(),
  status: z.enum(['idle', 'loading', 'success', 'error']),
});

type Props = z.infer<typeof schema>;

// Component
export function Component({ id, status }: Props) {
  return <div>{/* Implementation */}</div>;
}
```

---

## State Management

### TRPC Query (Server State)

```typescript
import { trpc } from '@/trpc/client';

export function useData() {
  const { data, isLoading } = trpc.getData.useQuery();
  return { data, isLoading };
}
```

### Zustand (Client State)

```typescript
import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';

type State = {
  items: Item[];
  addItem: (item: Item) => void;
};

export const useStore = create<State>()(
  immer((set) => ({
    items: [],
    addItem: (item) =>
      set((state) => {
        state.items.push(item);
      }),
  })),
);
```

---

## Discriminated Union Pattern

```typescript
type State =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: Data }
  | { status: 'error'; error: Error };

function Component({ state }: { state: State }) {
  switch (state.status) {
    case 'idle': return <div>Idle</div>;
    case 'loading': return <div>Loading...</div>;
    case 'success': return <div>{state.data}</div>;
    case 'error': return <div>Error: {state.error.message}</div>;
  }
}
```

---

## Testing

```typescript
import { render, screen } from '@testing-library/react';

describe('Component', () => {
  it('should render', () => {
    render(<Component />);
    expect(screen.getByRole('button')).toBeInTheDocument();
  });
});
```

---

## Styling

```typescript
import styled from 'styled-components';

const Container = styled.div`
  padding: ${({ theme }) => theme.spacing.md};
`;
```

---

## Implementation Checklist

- [ ] Invoke `typescript-guidelines` skill
- [ ] Create feature folder in `features/[name]/`
- [ ] Define types with Zod schemas
- [ ] Use TRPC for API calls
- [ ] Use Zustand for global state
- [ ] Use discriminated unions for component state
- [ ] Write component tests
- [ ] No `any` types
- [ ] Query by role in tests
