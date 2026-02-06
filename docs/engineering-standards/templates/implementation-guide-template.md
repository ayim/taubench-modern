# Implementation Guide: [Feature Name]

> **For AI Assistants:** Map each user story to implementation sections. Include ASCII diagrams for architecture/flows, design decisions with rationale, data structures with code, and deployment steps. Keep it concise.

**Date:** YYYY-MM-DD  
**Specification:** See [feature-specification.md](./feature-specification.md) for requirements

---

## Table of Contents

1. [Story-to-Implementation Mapping](#story-to-implementation-mapping)
2. [System Architecture](#system-architecture)
3. [Sequence Diagrams](#sequence-diagrams)
4. [Data Flow](#data-flow)
5. [Design Decisions](#design-decisions)
6. [Data Structures](#data-structures)
7. [API Design](#api-design)
8. [Core Algorithm](#core-algorithm)
9. [Migration Strategy](#migration-strategy)

---

## Story-to-Implementation Mapping

| Story | Implementation Sections |
| ----- | ----------------------- |
| A-1   | §7 Data Structures, §8 API Design |
| A-2   | §8 Core Algorithm |
| B-1   | §2 System Architecture, §6 Design Decisions |

---

## System Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌──────────────┐
│   API       │────→│   Service    │
└─────────────┘     └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │   Database   │
                    └──────────────┘
```

**Components:**

| Component | Purpose | Technology |
| --------- | ------- | ---------- |
| API | [Purpose] | [Tech] |
| Service | [Purpose] | [Tech] |
| Database | [Purpose] | [Tech] |

---

## Sequence Diagrams

### [Primary Flow]

```
User    API    Service    DB
 │       │        │        │
 │──────→│        │        │
 │       │───────→│        │
 │       │        │───────→│
 │       │        │←───────│
 │       │←───────│        │
 │←──────│        │        │
```

**Steps:**
1. [Step 1]
2. [Step 2]
3. [Step 3]

---

## Data Flow

```
Input → Validate → Process → Store → Output
```

**Transformations:**
- Input → Validated: [What happens]
- Validated → Processed: [What happens]
- Processed → Stored: [What happens]

---

## Design Decisions

### Decision 1: [Title]

**Problem:** [What problem does this solve?]

**Options:**

| Option | Pros | Cons |
| ------ | ---- | ---- |
| A | [Pro] | [Con] |
| B | [Pro] | [Con] |

**Chosen:** Option A

**Rationale:** [Why this was chosen, trade-offs accepted]

---

### Decision 2: [Title]

**Chosen:** [Approach]

**Rationale:** [Why]

---

## Data Structures

### Database Schema

```sql
CREATE TABLE [table_name] (
    id SERIAL PRIMARY KEY,
    [field] TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_[table]_[field] ON [table_name]([field]);
```

### Domain Models

```python
from pydantic import BaseModel

class [ModelName](BaseModel):
    """[Description]."""
    id: str
    field: str
    items: list[str] = []
```

---

## API Design

### REST Endpoints

**POST /api/[resource]**

```json
{
  "param": "value"
}
```

Response:
```json
{
  "id": "123",
  "status": "success"
}
```

### TRPC Procedures

```typescript
export const router = {
  create: protectedProcedure
    .input(z.object({ param: z.string() }))
    .mutation(async ({ input }) => {
      // Implementation
    }),
};
```

---

## Core Algorithm

### [Algorithm Name]

```
Step 1: [Description]
Step 2: [Description]
Step 3: [Description]
```

**Implementation:**

```python
async def algorithm(input: Input) -> Output:
    """[Description]."""
    # Step 1
    validated = validate(input)
    
    # Step 2
    processed = process(validated)
    
    # Step 3
    return store(processed)
```

---

## Migration Strategy

### Phases

**Phase 1: Core Implementation**
- [ ] Data structures and models
- [ ] API endpoints
- [ ] Unit tests

**Phase 2: Integration**
- [ ] Integrate with existing systems
- [ ] Integration tests

**Phase 3: Deployment**
- [ ] Feature flag: `ENABLE_[FEATURE]` (default: false)
- [ ] Deploy to staging
- [ ] Enable for beta users
- [ ] Enable for all users

### Rollback

1. Disable feature flag: `ENABLE_[FEATURE]=false`
2. Check logs for errors
3. Rollback DB migrations if needed

### Database Migrations

```sql
-- Up
CREATE TABLE ...

-- Down
DROP TABLE ...
```

---

## References

- [Specification](./feature-specification.md)
- [Testing Guide](./testing-guide.md)
