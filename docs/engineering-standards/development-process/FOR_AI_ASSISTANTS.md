# AI Implementation Guide

**Process:** `READ DESIGN → BRANCH → STORY LOOP → REVIEW → MERGE`

---

## Prerequisites

1. Read `@AGENTS.md` (root), `@server/AGENTS.md` (Python), or `@workroom/AGENTS.md` (TypeScript)
2. **Invoke skill**: `python-guidelines` (Python) or `typescript-guidelines` (TypeScript)
3. Read feature spec in `docs/features/[category]/`

**CRITICAL - Understanding Specifications:**

- Each user story has detailed Context (2-3 paragraphs) explaining WHY and background
- Read the full Context section to understand the problem before implementing
- If a story only has one-line descriptions, ask for clarification—proper specs have multi-paragraph Context sections
- Both you (AI) and humans need to understand the full picture from the Context alone

---

## Project Structure

```
moonraker/
├── server/              # Python agent server (FastAPI)
├── core/                # Core Python platform
├── workroom/
│   ├── frontend/        # React/TypeScript UI
│   ├── spar-ui/         # SPAR UI components
│   └── backend/         # Express/TypeScript proxy (TRPC)
└── document-intelligence/  # DI module
```

**SPAR** = agent-server (Python) + workroom (TypeScript frontend + Express backend)

---

## Implementation Loop

**For EACH story**: Implement → Test → Review → Get Signoff

### Python (server/core)

Follow `python-guidelines` skill. Run from root only:

```bash
make test-unit
make lint typecheck check-format
```

### TypeScript (workroom)

Follow `typescript-guidelines` skill. Run from workroom/:

```bash
npm run test        # Component tests
npm run test:e2e    # E2E (critical paths only)
npm run lint typecheck
```

### Commit Format

```
<type>: <subject> (#issue)

- Detail 1
- Detail 2

Closes #issue
```

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`

---

## Code Patterns

### Python

```python
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent_platform_server.database import DatabaseClient

async def get_user(database: DatabaseClient, user_id: str) -> User | None:
    """Get user by ID."""
    from agent_platform_server.models import User  # Import inside method
  
    result = await database.selectUser({'id': user_id})
    return result.data if result.success else None
```

### TypeScript

```typescript
import { z } from 'zod';

// Schema + type from same definition
const UserSchema = z.object({
  id: z.string().uuid(),
  name: z.string().min(1),
});
type User = z.infer<typeof UserSchema>;

// Discriminated union for state
type State =
  | { status: 'loading' }
  | { status: 'success'; data: User }
  | { status: 'error'; error: Error };

// TRPC query
const { data } = trpc.users.get.useQuery({ id });

// TRPC mutation with cache invalidation
const mutation = trpc.users.update.useMutation({
  onSuccess: () => trpcUtils.users.list.invalidate(),
});
```

---

## Common Pitfalls


| Python                                     | TypeScript                                             |
| -------------------------------------------- | -------------------------------------------------------- |
| ❌ Run from subdirectories (use root)      | ❌`any` types (use `unknown` + guards)                 |
| ❌ Blocking I/O (use`async`/`await`)       | ❌ Boolean flags for state (use discriminated unions)  |
| ❌ Top-level imports (move inside methods) | ❌ Prop spreading (define explicitly)                  |
| ❌ Missing type hints                      | ❌ Hardcoded values (use theme tokens)                 |
| ❌ Import cycles (use`TYPE_CHECKING`)      | ❌ Mock internal hooks (mock at API boundary with MSW) |

---

## Development Commands

### Python (from root)

```bash
make sync                    # Sync dependencies
make run-server-hot-reload   # Start server
make test-unit              # Run tests
make lint typecheck         # Quality checks
```

### TypeScript (from workroom/)

```bash
npm install    # Install dependencies
npm run dev    # Start dev server
npm run test   # Run tests
npm run lint typecheck  # Quality checks
```

### Full Stack (from root)

```bash
docker compose up  # Start everything
# Frontend: http://localhost:8001
# API: http://localhost:8000
```

---

## Testing


|                   | Python                 | TypeScript                  |
| ------------------- | ------------------------ | ----------------------------- |
| **Unit**          | pytest, mocked deps    | Vitest, isolated            |
| **Integration**   | Real Postgres/services | MSW (mock API)              |
| **E2E**           | Integration tests      | Playwright (critical paths) |
| **Coverage**      | >80%                   | >80%                        |
| **Accessibility** | N/A                    | jest-axe (WCAG)             |

**Always run Python tests from repository root.**

---

## Resources

### Essential Docs

- `@AGENTS.md` - Root guide
- `@server/AGENTS.md` - Python patterns
- `@workroom/AGENTS.md` - TypeScript patterns

### Skills (Invoke for Code Review)

- `python-guidelines` - Python engineering standards
- `typescript-guidelines` - TypeScript/React standards
- `agent-browser` - Frontend testing automation

### Templates

- `feature-specification-template.md` - Requirements
- `implementation-guide-template.md` - Technical implementation
- `backend-testing-guide-template.md` - Python testing
- `frontend-testing-guide-template.md` - React testing
- `react-app-template.md` - React app structure

### Examples

- `docs/features/sdm/` - SDM features
- `docs/features/di/` - DI features

---

## Quick Start

1. Read `@AGENTS.md` + component AGENTS.md
2. Invoke `python-guidelines` or `typescript-guidelines` skill
3. Read feature spec
4. Create branch: `feature-<name>`
5. For each story:
   - Implement + test
   - Run quality checks
   - Get user signoff
6. Create PR → merge → update docs
