# Frontend Testing Guide: [Feature Name]

> **For AI Assistants:** Invoke `typescript-guidelines` skill. Map each story to tests: component (React Testing Library), E2E (Playwright for critical paths), accessibility (jest-axe). Mock at API with MSW.

**Related:** [Specification](./feature-specification.md) | [Implementation](./implementation-guide.md)

---

## Story-to-Test Mapping

| Story | Test Type | Test File |
| ----- | --------- | --------- |
| A-1 | Component | `[Component].test.tsx` |
| A-2 | Component + E2E | `[Component].test.tsx`, `[feature].spec.ts` |
| B-1 | E2E | `[feature].spec.ts` |

---

## Component Tests

```typescript
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

describe('[Component]', () => {
  it('should [test story A-1]', async () => {
    // Arrange
    render(<Component {...props} />);
    
    // Act
    await userEvent.click(screen.getByRole('button', { name: /submit/i }));
    
    // Assert
    expect(screen.getByText(/success/i)).toBeInTheDocument();
  });
});
```

---

## E2E Tests (Playwright)

```typescript
import { test, expect } from '@playwright/test';

test('should [test story B-1]', async ({ page }) => {
  // Navigate
  await page.goto('/feature');
  
  // Interact
  await page.getByRole('button', { name: /action/i }).click();
  
  // Assert
  await expect(page.getByText(/result/i)).toBeVisible();
});
```

---

## Accessibility Tests

```typescript
import { axe } from 'jest-axe';

it('should have no a11y violations', async () => {
  const { container } = render(<Component />);
  const results = await axe(container);
  expect(results).toHaveNoViolations();
});
```

---

## API Mocking (MSW)

```typescript
import { http, HttpResponse } from 'msw';

export const handlers = [
  http.get('/api/resource', () => {
    return HttpResponse.json({ data: [...] });
  }),
];
```

---

## Running Tests

```bash
# From workroom/
npm run test              # Component tests
npm run test:e2e          # E2E tests
npm run lint typecheck    # Linting & types
```
