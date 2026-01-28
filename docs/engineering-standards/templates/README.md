# Feature Documentation Templates

This directory contains reusable templates for documenting features in a consistent, comprehensive way.

## Templates

| Template                                                                 | Purpose                    | When to Use                  |
| ------------------------------------------------------------------------ | -------------------------- | ---------------------------- |
| [feature-specification-template.md](./feature-specification-template.md) | Define **what** to build   | Starting a new feature       |
| [architecture-guide-template.md](./architecture-guide-template.md)       | Define **how** to build it | After specification approved |
| [testing-guide-template.md](./testing-guide-template.md)                 | Define **how to validate** | Before implementation begins |

## Document Relationships

```
┌─────────────────────────┐
│  Feature Specification  │  ← "What to build" (Product/PM)
│  - Problem statement    │
│  - Requirements         │
│  - Epics & Stories      │
│  - Success metrics      │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Architecture Guide     │  ← "How to build it" (Engineering)
│  - Story-to-section map │
│  - Performance targets  │
│  - Data structures      │
│  - Algorithms           │
│  - Migration plan       │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Testing Guide          │  ← "How to validate" (QA/Engineering)
│  - Story-to-test map    │
│  - Component tests      │
│  - Performance tests    │
│  - E2E validation       │
│  - Success criteria     │
└─────────────────────────┘
```

## Quick Start

### 1. Copy the templates

```bash
# Create feature documentation directory
mkdir -p docs/features/[feature-name]

# Copy templates
cp docs/templates/feature-specification-template.md docs/features/[feature-name]/specification.md
cp docs/templates/architecture-guide-template.md docs/features/[feature-name]/architecture.md
cp docs/templates/testing-guide-template.md docs/features/[feature-name]/testing.md
```

### 2. Update cross-references

In each document, update the links to point to sibling documents:

```markdown
# In specification.md

**Architecture:** See [architecture.md](./architecture.md)

# In architecture.md

**Specification:** See [specification.md](./specification.md)

# In testing.md

**Related:** [Specification](./specification.md) | [Architecture](./architecture.md)
```

### 3. Fill in the templates

Work through each template section:

**Specification (start here):**

1. Executive Summary
2. Problem Statement
3. Solution Overview
4. Requirements
5. Epics & User Stories
6. Success Metrics

**Architecture (after spec approved):**

1. Story-to-Architecture Mapping
2. Performance Targets
3. Technology Decisions
4. Data Structures
5. Core Algorithm
6. Migration Strategy

**Testing (before implementation):**

1. Story-to-Test Coverage Matrix
2. Component Tests
3. Performance Validation
4. E2E Validation
5. Success Criteria

## Template Features

### Story Structure (Specification)

Each user story follows a consistent pattern:

```markdown
**Story A-1: [Story Name]**

> As a [persona], I want to [action] so that [benefit].

**Context:**
[Why this story matters - 2-3 sentences]

**Scope:**
_What this story produces:_

- [Deliverable 1]
- [Deliverable 2]

_What this enables:_

- [Capability 1]

**Acceptance Criteria:**

- [ ] [Testable criterion 1]
- [ ] [Testable criterion 2]
- [ ] [Testable criterion 3]

**Performance Target:** [Target] (if applicable)

**Edge Cases:**

- [Edge case 1]: [Handling]

**Dependencies:**

- [Dependency]
```

### Traceability

All three documents maintain traceability through mapping tables:

| Document      | Maps                            |
| ------------- | ------------------------------- |
| Specification | Epics → Stories                 |
| Architecture  | Stories → Architecture Sections |
| Testing       | Stories → Test Cases            |

This ensures every requirement can be traced from spec → implementation → validation.

### Performance Targets

Performance targets flow from specification through architecture to testing:

1. **Specification:** Defines target (e.g., "< 500ms latency")
2. **Architecture:** Provides implementation guidance to meet target
3. **Testing:** Provides benchmark tests to verify target

## Best Practices

### Writing Good Stories

- **Context** should explain WHY (not just WHAT)
- **Scope** should be concrete and measurable
- **Acceptance Criteria** should be 4-6 testable items
- **Edge Cases** should document non-obvious scenarios

### Keeping Documents in Sync

When updating one document, check if related documents need updates:

| Change                    | Update Specification | Update Architecture | Update Testing |
| ------------------------- | -------------------- | ------------------- | -------------- |
| New requirement           | ✅                   | ✅                  | ✅             |
| Algorithm change          | —                    | ✅                  | ✅             |
| Performance target change | ✅                   | ✅                  | ✅             |
| New edge case             | ✅                   | —                   | ✅             |

### Review Checklist

Before finalizing documentation:

- [ ] All stories have Context, Scope, and Acceptance Criteria
- [ ] Architecture maps every story to a section
- [ ] Testing guide covers every story
- [ ] Performance targets are consistent across all documents
- [ ] Cross-references between documents are correct
- [ ] No placeholder text remains (search for `[` brackets)

## Examples

These templates were derived from:

- [schema-linking-specification.md](../../schema-linking-specification.md)
- [schema-linking-architecture.md](../../schema-linking-architecture.md)
- [schema-linking-testing-guide.md](../../schema-linking-testing-guide.md)

Use these as reference implementations when filling out the templates.
