# AI Prompting Guide

**Purpose:** How to prompt AI assistants for feature implementation

---

## Document Structure

```
docs/engineering-standards/
├── development-process/
│   ├── FOR_AI_ASSISTANTS.md           # Workflow guide
│   └── PROMPTING_GUIDE.md             # This file
└── templates/                          # Feature templates
    ├── feature-specification-template.md
    ├── implementation-guide-template.md
    ├── backend-testing-guide-template.md
    ├── frontend-testing-guide-template.md
    └── react-app-template.md

.claude/skills/                         # Engineering standards (invoke as skills)
├── python-guidelines/SKILL.md
├── typescript-guidelines/SKILL.md
└── agent-browser/SKILL.md
```

---

## Prompt Templates

### 1. Python Feature (Server/Core)

```
Implement [Feature Name] in the agent server.

Context:
- @docs/engineering-standards/development-process/FOR_AI_ASSISTANTS.md
- @AGENTS.md
- @server/AGENTS.md
- @docs/features/[category]/[feature-name]-specification.md
- @docs/features/[category]/[feature-name]-implementation.md

Invoke: python-guidelines skill

Instructions:
1. Read design documents
2. Create branch: feature-[name]
3. Implement story by story per specification
4. Write tests (unit + integration) for each story
5. Run: make lint typecheck test-unit (from root)
6. Get my signoff before next story

Start with Story A-1.
```

### 2. TypeScript Feature (Workroom)

```
Implement [Feature Name] in the workroom.

Context:
- @docs/engineering-standards/development-process/FOR_AI_ASSISTANTS.md
- @AGENTS.md
- @workroom/AGENTS.md
- @docs/features/[category]/[feature-name]-specification.md
- @docs/features/[category]/[feature-name]-implementation.md

Invoke: typescript-guidelines skill

Instructions:
1. Read design documents
2. Create branch: feature-[name]
3. Implement story by story per specification
4. Follow patterns:
   - No `any` types, use discriminated unions
   - Zod for API validation
   - TRPC for server communication
5. Write tests (component + E2E for critical paths)
6. Run: npm run lint typecheck test
7. Get my signoff before next story

Start with Story A-1 from Phase 1.
```

### 3. Full Stack Feature

```
Implement [Feature Name] (Python + TypeScript).

Context:
- @docs/engineering-standards/development-process/FOR_AI_ASSISTANTS.md
- @AGENTS.md, @server/AGENTS.md, @workroom/AGENTS.md
- @docs/features/[category]/[feature-name]-specification.md
- @docs/features/[category]/[feature-name]-implementation.md

Invoke: python-guidelines AND typescript-guidelines skills

Instructions:
1. Backend first (Python):
   - API endpoints, business logic, database
   - Tests (unit + integration)
   - Run: make lint typecheck test-unit
2. Then frontend (TypeScript):
   - React components, TRPC queries
   - Tests (component + E2E for critical paths)
   - Run: npm run lint typecheck test
3. Get signoff after each major component

Start with backend API implementation.
```

### 4. Test Frontend Changes

```
Test the [Feature] UI changes.

Invoke: agent-browser skill

Test at http://localhost:8001:
1. Navigate to feature
2. Test user interactions
3. Test error states
4. Test loading states
5. Verify accessibility

Run in headless mode. Report issues found.
```

### 5. Create Design Documents

```
Create design documents for [Feature Name].

Gate:
- Do NOT proceed unless user requirements are provided.
- If missing, request requirements first and stop.

Input:
- A short problem statement (why + who)
- Requirements list (bullets are fine)
- Constraints / non-goals (if any)
- Relevant existing docs or links (optional)

Templates:
- @docs/engineering-standards/templates/feature-specification-template.md
- @docs/engineering-standards/templates/implementation-guide-template.md

Examples:
- @docs/features/sdm/federated-queries/sdm-federated-queries-specification.md

CRITICAL - Story Requirements:
- Each story MUST have 2-3 paragraph Context section (not one line!)
- Context explains: WHY it matters, current problem, background, user impact
- Scope section lists specific deliverables with details
- Include 5+ testable acceptance criteria per story
- Both humans and AI must understand from Context alone
- @docs/features/sdm/federated-queries/sdm-federated-queries-implementation.md

Requirements:
[List requirements]

Create:
1. Specification with epics, stories, acceptance criteria
2. Architecture with technical decisions, data structures, API design

Output files:
- docs/features/[category]/[feature-name]-specification.md
- docs/features/[category]/[feature-name]-implementation.md
```

### 6. Create Implementation Guide from Specification

```
Create the implementation guide for [Feature Name] based on the specification.

Gate:
- Do NOT proceed unless the feature specification doc is provided/approved.
- If missing, request the specification first and stop.

Input (required):
- @docs/features/[category]/[feature-name]-specification.md

Template:
- @docs/engineering-standards/templates/implementation-guide-template.md

Example:
- @docs/features/sdm/schema-linking/schema-linking-implementation.md

Instructions:

1. ANALYZE THE SPECIFICATION:
   - Extract all stories from each Epic (A-1, A-2, B-1, etc.)
   - Note the phase each story belongs to (Phase 1, 2, etc.)
   - Identify acceptance criteria that imply technical requirements
   - Find performance targets (latency, throughput, etc.)

2. CREATE STORY-TO-IMPLEMENTATION MAPPING:
   - Map each story to the implementation sections it affects
   - Example: "A-1 → §5 Data Structures, §6 Core Algorithm"
   - Group by Epic and Phase for clarity

3. DESIGN THE ARCHITECTURE:
   - Draw ASCII diagrams showing component relationships
   - List all new components and their purposes
   - Show data flow between components
   - Identify integration points with existing systems

4. DOCUMENT DESIGN DECISIONS:
   - For each non-obvious technical choice:
     - State the problem being solved
     - List options considered (with pros/cons table)
     - State chosen option with rationale
   - Include decisions about: storage, algorithms, APIs, error handling

5. DEFINE DATA STRUCTURES:
   - Database schemas (SQL CREATE statements)
   - Pydantic models (Python) or Zod schemas (TypeScript)
   - Card/artifact formats if applicable
   - Include indexes and constraints

6. SPECIFY ALGORITHMS:
   - Pseudocode or actual code for core algorithms
   - Step-by-step breakdown of complex logic
   - Include performance characteristics (Big-O if relevant)

7. DOCUMENT API DESIGN:
   - REST endpoints with request/response examples
   - TRPC procedures if frontend involved
   - Error response contracts

8. CREATE MIGRATION STRATEGY:
   - Phase-by-phase implementation checklist
   - Feature flag strategy
   - Rollback procedure
   - Database migration scripts (up/down)

Key Principles:
- Implementation guide answers HOW, specification answers WHAT
- Include enough detail that an engineer can implement without guessing
- Code examples should be runnable, not pseudocode
- Every story in the spec must appear in the story mapping
- Latency/performance targets from spec become validation criteria

Output file:
- docs/features/[category]/[feature-name]-implementation.md
```

### 7. Create Backend Testing Guide

```
Create the backend testing guide for [Feature Name].

Gate:
- Do NOT proceed unless the feature specification and implementation docs are provided/approved.
- If missing, request them first and stop.

Input (required):
- @docs/features/[category]/[feature-name]-specification.md
- @docs/features/[category]/[feature-name]-implementation.md

Template:
- @docs/engineering-standards/templates/backend-testing-guide-template.md

Invoke:
- python-guidelines skill

Instructions:
1. Map each story to test cases (unit + integration).
2. Include failure-mode tests (invalid input, permission denied, timeouts).
3. Specify fixtures/test data and how to generate them.
4. Define performance assertions (latency targets, budgets).
5. Include mock boundaries (only external services; avoid mocking internal logic).
6. Provide commands to run tests from repo root:
   - make test-unit
   - uv run --project agent_platform_server pytest [path]

Output file:
- docs/features/[category]/[feature-name]-testing-guide.md
```

### 8. Create Frontend Testing Guide

```
Create the frontend testing guide for [Feature Name].

Gate:
- Do NOT proceed unless the feature specification and implementation docs are provided/approved.
- If missing, request them first and stop.

Input (required):
- @docs/features/[category]/[feature-name]-specification.md
- @docs/features/[category]/[feature-name]-implementation.md

Template:
- @docs/engineering-standards/templates/frontend-testing-guide-template.md

Invoke:
- typescript-guidelines skill
- agent-browser skill (for UI verification)

Instructions:
1. Map each story to test cases (component + E2E for critical paths).
2. Include accessibility checks and error/empty/loading states.
3. Define test data setup (fixtures, mocks, MSW if applicable).
4. Specify performance/UX assertions (TTI, render time, large lists).
5. Provide commands to run tests:
   - npm run test
   - npm run lint typecheck
6. Include manual verification checklist for key flows.

Output file:
- docs/features/[category]/[feature-name]-testing-guide.md
```

### 7. Code Review

```
Review and fix this code to comply with standards.

Context: @AGENTS.md, @server/AGENTS.md (Python) or @workroom/AGENTS.md (TypeScript)

Invoke: python-guidelines (Python) OR typescript-guidelines (TypeScript)

[paste code]
```

---

## Component Decision Tree

```
What are you building?

Python (server/core)
  → Invoke: python-guidelines
  → Template: backend-testing-guide-template.md
  → Run: make test-unit (from root)

TypeScript (workroom)
  → Invoke: typescript-guidelines
  → Template: frontend-testing-guide-template.md
  → Run: npm run test (from workroom/)

Full Stack
  → Invoke: Both skills
  → Backend first, then frontend

Design docs
  → Use: feature-specification-template.md
  → Use: implementation-guide-template.md

Testing frontend
  → Invoke: agent-browser

Code review
  → Invoke: Appropriate skill
```

---

## Best Practices

### Always Include

1. `@docs/engineering-standards/development-process/FOR_AI_ASSISTANTS.md` - Workflow
2. `@AGENTS.md` - Root guide
3. Component AGENTS.md - `@server/AGENTS.md` or `@workroom/AGENTS.md`
4. Feature spec + architecture docs

### Always Invoke Skills

- **Python**: `python-guidelines` (comprehensive Python standards)
- **TypeScript**: `typescript-guidelines` (comprehensive TypeScript/React standards)
- **Frontend testing**: `agent-browser` (automated browser testing)

### Key Patterns

- Get signoff after each story (prevent rushing ahead)
- Reference actual examples (`docs/features/`)
- Be explicit about testing requirements
- Specify quality checks (`make lint typecheck` or `npm run lint typecheck`)

---

## Example Prompt (Complete)

```
Implement SDM Hierarchical Data feature.

Workflow: @docs/engineering-standards/development-process/FOR_AI_ASSISTANTS.md
Project: @AGENTS.md
Server: @server/AGENTS.md

Design:
- @docs/features/sdm/hierarchical-data/sdm-hierarchical-data-specification.md
- @docs/features/sdm/hierarchical-data/sdm-hierarchical-data-implementation.md

Invoke python-guidelines skill for code review.

Create branch: sdm-hierarchical-data
Implement story by story per specification.
Write tests (unit + integration) for each story.
Run make lint typecheck test-unit after each story.
Get my signoff before proceeding to next story.

Start with Epic A, Story A-1.
```

---

## Summary

**Minimal prompt structure:**

1. Feature name + context docs
2. Invoke appropriate skill
3. Explicit instructions (branch, story-by-story, tests, quality checks, signoff)
4. Starting point (Epic A, Story A-1)

**Skills are comprehensive** - they contain all engineering standards, so just invoke them rather than listing every pattern.
