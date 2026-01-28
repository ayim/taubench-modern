# Architecture Guide: [Feature Name]

**Date:** YYYY-MM-DD  
**Audience:** Software engineers, technical leads, DevOps  
**Specification:** See [feature-specification.md](./feature-specification.md) for requirements and user stories

---

## Overview

This document provides implementation guidance for the [Feature Name]. It covers:

- Technical architecture decisions (storage, APIs, external services)
- Detailed algorithms and data structures
- Migration strategy with test data requirements and tuning procedures
- Rollback and operational strategies

**For "what to build"**, see the [specification document](./feature-specification.md).  
**This document focuses on "how to build it".**

---

## Table of Contents

1. [Story-to-Architecture Mapping](#story-to-architecture-mapping)
2. [Performance Targets](#performance-targets)
3. [Implementation Architecture](#implementation-architecture)
4. [Data Structures](#data-structures)
5. [Core Algorithm](#core-algorithm)
6. [Scoring & Configuration](#scoring--configuration)
7. [Migration Strategy](#migration-strategy)
8. [Rollback Strategy](#rollback-strategy)
9. [Appendix](#appendix)

---

## Story-to-Architecture Mapping

This table maps each user story (from the specification) to the relevant architecture sections.

### Epic A: [Epic Name]

| Story | Description         | Architecture Sections |
| ----- | ------------------- | --------------------- |
| A-1   | [Story description] | [Section links]       |
| A-2   | [Story description] | [Section links]       |
| A-3   | [Story description] | [Section links]       |

### Epic B: [Epic Name]

| Story | Description         | Architecture Sections |
| ----- | ------------------- | --------------------- |
| B-1   | [Story description] | [Section links]       |
| B-2   | [Story description] | [Section links]       |
| B-3   | [Story description] | [Section links]       |

### Epic C: [Epic Name]

| Story | Description         | Architecture Sections |
| ----- | ------------------- | --------------------- |
| C-1   | [Story description] | [Section links]       |
| C-2   | [Story description] | [Section links]       |

---

## Performance Targets

Consolidated performance targets from the specification. These define the latency and throughput requirements.

### Offline Operations

| Operation     | Target              | Rationale         |
| ------------- | ------------------- | ----------------- |
| [Operation 1] | [Target with units] | [Why this target] |
| [Operation 2] | [Target with units] | [Why this target] |

### Startup Operations

| Operation     | Target              | Rationale         |
| ------------- | ------------------- | ----------------- |
| [Operation 1] | [Target with units] | [Why this target] |

### Online Operations (Per Request)

| Operation         | Target   | Rationale           |
| ----------------- | -------- | ------------------- |
| **End-to-end**    | [Target] | User-facing latency |
| [Sub-operation 1] | [Target] | [Rationale]         |
| [Sub-operation 2] | [Target] | [Rationale]         |

### Conditional Operations

| Operation     | Target   | When Triggered |
| ------------- | -------- | -------------- |
| [Operation 1] | [Target] | [Condition]    |
| [Operation 2] | [Target] | [Condition]    |

### Timeout Configuration

| Operation     | Timeout   | Action on Timeout |
| ------------- | --------- | ----------------- |
| [Operation 1] | [Timeout] | [Fallback action] |
| [Operation 2] | [Timeout] | [Fallback action] |

---

## Implementation Architecture

### Technology Decisions

#### Decision 1: [Technology Area] (CRITICAL - Required for Phase 1)

**Context:** [Why this decision matters]

**Options Considered:**

| Option   | Pros   | Cons   |
| -------- | ------ | ------ |
| Option A | [Pros] | [Cons] |
| Option B | [Pros] | [Cons] |
| Option C | [Pros] | [Cons] |

**Recommendation:** Option [X]

**Rationale:** [Why this option was chosen]

---

#### Decision 2: [Technology Area] (CRITICAL - Required for Phase 2)

**Context:** [Why this decision matters]

**Options Considered:**

| Option   | Pros   | Cons   |
| -------- | ------ | ------ |
| Option A | [Pros] | [Cons] |
| Option B | [Pros] | [Cons] |

**Recommendation:** Option [X]

**Rationale:** [Why this option was chosen]

---

#### Decision 3: [Technology Area] (MEDIUM - Required for Phase 2)

**Context:** [Why this decision matters]

**Recommendation:** [Chosen approach]

**Rationale:** [Why this approach was chosen]

---

### Decision Summary Table

| Decision     | Phase Required | Criticality  | Recommended Default |
| ------------ | -------------- | ------------ | ------------------- |
| [Decision 1] | Phase 1        | **CRITICAL** | [Default]           |
| [Decision 2] | Phase 2        | **CRITICAL** | [Default]           |
| [Decision 3] | Phase 2        | MEDIUM       | [Default]           |
| [Decision 4] | Phase 3        | LOW          | [Default]           |

**Next Steps:**

1. Implement [Decision 1] for Phase 1
2. [Next step 2]
3. [Next step 3]

---

## Data Structures

### Database Schema

```sql
-- [Table 1]: [Description]
CREATE TABLE [table_name] (
    id SERIAL PRIMARY KEY,
    [column_1] TEXT NOT NULL,
    [column_2] TEXT NOT NULL,
    [column_3] JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE ([column_1], [column_2])
);

-- Indexes
CREATE INDEX idx_[table]_[column] ON [table_name]([column]);
```

### Domain Models

```python
from pydantic import BaseModel, Field
from typing import Literal

class [ModelName](BaseModel):
    """[Description of model purpose]."""
    id: str = Field(..., description="[Description]")
    [field_1]: str = Field(..., description="[Description]")
    [field_2]: Literal["option_a", "option_b"] = Field(default="option_a")
    [field_3]: list[str] = Field(default_factory=list)

    # Optional fields
    [optional_field]: str | None = None


class [ConfigModel](BaseModel):
    """Configuration for [feature]."""
    [param_1]: float = Field(default=0.5, ge=0.0, le=1.0)
    [param_2]: int = Field(default=10, ge=1)
    [param_3]: bool = Field(default=True)
```

### [Data Structure Name] Schema

```python
class [DataStructureName](BaseModel):
    """[Description]."""

    [field_1]: str = Field(..., description="[Description]")
    [field_2]: dict[str, [SubType]] = Field(default_factory=dict)
    [field_3]: list[[SubType]] = Field(default_factory=list)

    def [method_1](self, [param]: str) -> [ReturnType] | None:
        """[Method description]."""
        ...

    def [method_2](self, [param1]: str, [param2]: str) -> bool:
        """[Method description]."""
        ...
```

### Example Data (Serialized)

```json
{
  "[field_1]": "[value]",
  "[field_2]": {
    "[key]": {
      "[nested_field]": "[value]"
    }
  },
  "[field_3]": [
    {
      "[item_field]": "[value]"
    }
  ]
}
```

---

## Core Algorithm

### Overview

```
Step 0: [Preparation step]
Step 1: [First processing step]
Step 2: [Second processing step]
Step 3: [Third processing step]
Step 4: [Post-processing step]
Step 5: [Output generation]
```

### Step 0: [Step Name]

**Input:** [Inputs to this step]  
**Output:** [Outputs from this step]

[Description of what this step does]

```python
def [step_0_function]([params]) -> [ReturnType]:
    """[Function description]."""
    # [Implementation notes]
    ...
```

---

### Step 1: [Step Name]

**Input:** [Inputs]  
**Output:** [Outputs]

[Description]

**Algorithm:**

1. [Sub-step 1]
2. [Sub-step 2]
3. [Sub-step 3]

```python
def [step_1_function]([params]) -> [ReturnType]:
    """[Function description]."""
    ...
```

---

### Step 2: [Step Name]

**Input:** [Inputs]  
**Output:** [Outputs]

[Description]

---

### Step 3: [Step Name]

**Input:** [Inputs]  
**Output:** [Outputs]

[Description]

---

### Step 4: [Step Name]

**Input:** [Inputs]  
**Output:** [Outputs]

[Description]

```python
def [refinement_function]([params]) -> [ReturnType]:
    """[Function description]."""
    ...
```

---

### Step 5: [Step Name]

**Input:** [Inputs]  
**Output:** [Outputs]

[Description]

---

## Scoring & Configuration

### Scoring Formula

```
final_score = [formula]
```

**Components:**

| Component     | Weight   | Description   |
| ------------- | -------- | ------------- |
| [Component 1] | [Weight] | [Description] |
| [Component 2] | [Weight] | [Description] |
| [Component 3] | [Weight] | [Description] |

### Boosts (Additive)

| Condition     | Boost    | Rationale        |
| ------------- | -------- | ---------------- |
| [Condition 1] | +[value] | [Why this boost] |
| [Condition 2] | +[value] | [Why this boost] |

### Default Configuration

```python
DEFAULT_CONFIG = {
    "[param_1]": [value],
    "[param_2]": [value],
    "[param_3]": [value],
    "[threshold_1]": [value],
    "[threshold_2]": [value],
}
```

### Threshold Tuning

| Threshold     | Default | Tune When   | Adjustment      |
| ------------- | ------- | ----------- | --------------- |
| [Threshold 1] | [Value] | [Condition] | [How to adjust] |
| [Threshold 2] | [Value] | [Condition] | [How to adjust] |

---

## Migration Strategy

### Phase Overview

| Phase   | Focus               | Duration   | Dependencies |
| ------- | ------------------- | ---------- | ------------ |
| Phase 1 | Foundation          | [Duration] | None         |
| Phase 2 | Core Implementation | [Duration] | Phase 1      |
| Phase 3 | Integration         | [Duration] | Phase 2      |
| Phase 4 | Validation          | [Duration] | Phase 3      |
| Phase 5 | Optimization        | [Duration] | Phase 4      |

### Phase 1: Foundation

**Goals:**

- [Goal 1]
- [Goal 2]

**Deliverables:**

- [ ] [Deliverable 1]
- [ ] [Deliverable 2]
- [ ] [Deliverable 3]

**Validation:**

- [How to validate this phase]

---

### Phase 2: Core Implementation

**Goals:**

- [Goal 1]
- [Goal 2]

**Deliverables:**

- [ ] [Deliverable 1]
- [ ] [Deliverable 2]

**Validation:**

- [How to validate this phase]

---

### Phase 3: Integration

**Goals:**

- [Goal 1]

**Deliverables:**

- [ ] [Deliverable 1]
- [ ] [Deliverable 2]

**Feature Flag:** `ENABLE_[FEATURE_NAME]` (default: false)

**Validation:**

- [How to validate this phase]

---

### Phase 4: Validation

**Goals:**

- [Goal 1]

**Deliverables:**

- [ ] [Deliverable 1]
- [ ] [Deliverable 2]

**Go/No-Go Criteria:**

- [ ] [Criterion 1]
- [ ] [Criterion 2]

---

### Phase 5: Optimization (Optional)

**Goals:**

- [Goal 1]

**Deliverables:**

- [ ] [Deliverable 1]

---

### Test Data Requirements

| Dataset     | Purpose   | Minimum Size |
| ----------- | --------- | ------------ |
| [Dataset 1] | [Purpose] | [Size]       |
| [Dataset 2] | [Purpose] | [Size]       |

### Tuning Playbook

1. **[Tuning step 1]:** [Instructions]
2. **[Tuning step 2]:** [Instructions]
3. **[Tuning step 3]:** [Instructions]

---

## Rollback Strategy

### Feature Flag Control

```python
# Disable feature immediately
ENABLE_[FEATURE_NAME] = False
```

### Rollback Triggers

| Trigger              | Threshold      | Action              |
| -------------------- | -------------- | ------------------- |
| [Metric 1] drops     | > [X]%         | Disable feature     |
| [Metric 2] increases | > [X]%         | Disable feature     |
| [Error type]         | > [N] per hour | Alert + investigate |

### Rollback Procedure

1. **Immediate:** Set feature flag to `false`
2. **Verify:** Check that [metric] returns to baseline
3. **Investigate:** [Investigation steps]
4. **Fix:** [Fix and redeploy process]

### Transactional Operations

| Operation     | Atomicity | Rollback Method   |
| ------------- | --------- | ----------------- |
| [Operation 1] | [Level]   | [How to rollback] |
| [Operation 2] | [Level]   | [How to rollback] |

### Operations to Log

| Event     | Log Level | Fields          |
| --------- | --------- | --------------- |
| [Event 1] | INFO      | [Fields to log] |
| [Event 2] | WARN      | [Fields to log] |
| [Event 3] | ERROR     | [Fields to log] |

---

## Appendix

### A: [Appendix Topic 1]

[Additional technical details, edge cases, or future considerations]

### B: [Appendix Topic 2]

[Additional technical details]

---

## References

- [Specification](./feature-specification.md) - Requirements and user stories
- [Testing Guide](./testing-guide.md) - Validation approach
- [External Resource](URL) - [Description]

---

## Revision History

| Version | Date       | Author   | Changes              |
| ------- | ---------- | -------- | -------------------- |
| 1.0     | YYYY-MM-DD | [Author] | Initial architecture |
| 1.1     | YYYY-MM-DD | [Author] | [Changes made]       |
