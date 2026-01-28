# Testing & Validation Guide: [Feature Name]

**Date:** YYYY-MM-DD  
**Purpose:** Validate [feature] efficacy using [benchmark/test suite]  
**Related:** [Specification](./feature-specification.md) | [Architecture](./architecture-guide.md)

---

## Table of Contents

1. [Overview](#overview)
2. [Story-to-Test Coverage Matrix](#story-to-test-coverage-matrix)
3. [Component Tests](#component-tests)
4. [Performance Validation](#performance-validation)
5. [Enhancement Feature Tests](#enhancement-feature-tests)
6. [Guardrail Tests](#guardrail-tests)
7. [End-to-End Validation](#end-to-end-validation)
8. [Metrics Collection](#metrics-collection)
9. [Success Criteria](#success-criteria)
10. [Troubleshooting](#troubleshooting)
11. [Continuous Monitoring](#continuous-monitoring)

---

## Overview

This guide explains how to validate [feature name] across multiple testing levels.

**Testing Levels:**

- **Component tests:** Validate individual stories in isolation
- **Performance tests:** Verify architecture latency targets
- **Integration tests:** End-to-end validation with [benchmark/test suite]

---

## Story-to-Test Coverage Matrix

This table maps each user story to its test coverage. Use this to ensure all stories are validated.

### Epic A: [Epic Name]

| Story | Description         | Test Type          | Test Location  |
| ----- | ------------------- | ------------------ | -------------- |
| A-1   | [Story description] | Unit               | [Section link] |
| A-2   | [Story description] | Unit + Integration | [Section link] |
| A-3   | [Story description] | Unit               | [Section link] |

### Epic B: [Epic Name]

| Story | Description         | Test Type          | Test Location       |
| ----- | ------------------- | ------------------ | ------------------- |
| B-1   | [Story description] | Integration        | [Section link]      |
| B-2   | [Story description] | Integration        | Deferred to Phase X |
| B-3   | [Story description] | Unit + Performance | [Section link]      |
| B-4   | [Story description] | Unit               | [Section link]      |

### Epic C: [Epic Name]

| Story | Description         | Test Type   | Test Location  |
| ----- | ------------------- | ----------- | -------------- |
| C-1   | [Story description] | Integration | [Section link] |
| C-2   | [Story description] | Integration | [Section link] |

---

## Component Tests

These unit tests validate individual stories in isolation. Run these before integration tests.

```bash
# Run all component tests
uv run --project [project_name] pytest tests/[feature]/ -v

# Run specific epic
uv run --project [project_name] pytest tests/[feature]/test_[component].py -v
```

### A-1: [Component] Tests

**Purpose:** Validate [what this tests].

**Test file:** `tests/[feature]/test_[component].py`

```python
class Test[ComponentName]:
    """Story A-1: [Story Name]"""

    def test_[scenario_1](self, [fixtures]):
        """[Description of what this tests]."""
        # Arrange
        [setup]

        # Act
        result = [function_under_test]([params])

        # Assert
        assert [expected_condition]

    def test_[scenario_2](self, [fixtures]):
        """[Description of what this tests]."""
        [test_implementation]

    def test_[edge_case_1](self):
        """[Edge case description]."""
        [test_implementation]

    def test_[edge_case_2](self):
        """[Edge case description]."""
        [test_implementation]

    def test_serialization_roundtrip(self, [fixtures]):
        """[Data structure] can be serialized and loaded without data loss."""
        [test_implementation]
```

---

### A-2: [Component] Tests

**Purpose:** Validate [what this tests].

**Test file:** `tests/[feature]/test_[component].py`

```python
class Test[ComponentName]:
    """Story A-2: [Story Name]"""

    def test_[scenario_1](self, [fixtures]):
        """[Description]."""
        [test_implementation]

    def test_[scenario_2](self, [fixtures]):
        """[Description]."""
        [test_implementation]
```

---

### B-4: [Component] Tests

**Purpose:** Validate [what this tests].

**Test file:** `tests/[feature]/test_[component].py`

```python
class Test[ComponentName]:
    """Story B-4: [Story Name]"""

    def test_[main_functionality](self, [fixtures]):
        """[Description]."""
        [test_implementation]

    def test_[handles_edge_case](self, [fixtures]):
        """[Edge case description]."""
        [test_implementation]

    def test_[preserves_invariant](self, [fixtures]):
        """[Invariant description]."""
        [test_implementation]
```

---

### E-1: [Operations] Tests

**Purpose:** Validate [operational behavior].

**Test file:** `tests/[feature]/test_[operations].py`

```python
class Test[OperationName]:
    """Story E-1: [Story Name]"""

    async def test_[trigger_scenario](self, [fixtures]):
        """[Trigger] causes [expected behavior]."""
        [test_implementation]

    async def test_[concurrent_scenario](self, [fixtures]):
        """[Concurrent operation] behaves correctly."""
        [test_implementation]

    async def test_[atomic_operation](self, [fixtures]):
        """[Operation] is atomic—no partial state visible."""
        [test_implementation]
```

---

## Performance Validation

These tests verify that the implementation meets architecture latency targets.

```bash
# Run performance tests
uv run --project [project_name] pytest tests/[feature]/test_performance.py -v --benchmark
```

### [Component 1] Performance

**Target:** [Target with units] (Story [X-N])

```python
class Test[Component]Performance:
    """Performance tests for [component]."""

    @pytest.mark.benchmark
    def test_[operation]_[size](self, [fixtures], benchmark):
        """[Operation] completes in < [target] for [size] [entities]."""
        result = benchmark([function], [params])

        assert benchmark.stats["mean"] < [target_seconds]

    @pytest.mark.benchmark
    def test_[operation_2]_[size](self, [fixtures], benchmark):
        """[Operation] completes in < [target]."""
        result = benchmark([function], [params])

        assert benchmark.stats["mean"] < [target_seconds]
```

### [Component 2] Performance

**Target:** [Target] (Story [X-N])

```python
@pytest.mark.benchmark
def test_[operation]_latency(self, [fixtures], benchmark):
    """[Operation] completes in < [target]."""
    result = benchmark([function], [params])

    assert benchmark.stats["mean"] < [target_seconds]
```

### End-to-End Performance

**Target:** [Target] excluding [external dependency] (Specification)

```python
@pytest.mark.benchmark
def test_end_to_end_latency(self, [service], [fixtures], benchmark):
    """End-to-end [operation] completes in < [target] (excluding [external])."""
    # Mock external dependency to isolate latency
    with mock_[external](latency=0):
        result = benchmark([service].[method], [params])

    assert benchmark.stats["mean"] < [target_seconds]
```

---

## Enhancement Feature Tests

These tests validate optional enhancement features. Run when features are enabled.

```bash
# Run with enhancement features enabled
ENABLE_[FEATURE_1]=true ENABLE_[FEATURE_2]=true \
  uv run --project [project_name] pytest tests/[feature]/test_enhancements.py -v
```

### G-1: [Enhancement 1] Tests

```python
class Test[Enhancement1]:
    """Story G-1: [Story Name]"""

    def test_[main_functionality](self, [fixtures]):
        """[Description]."""
        [test_implementation]

    def test_[enhancement_latency](self, [fixtures], benchmark):
        """[Enhancement] adds < [target] latency."""
        result = benchmark([function], [params])

        assert result.metadata["[enhancement]_latency_ms"] < [target]
```

### G-2: [Enhancement 2] Tests

```python
class Test[Enhancement2]:
    """Story G-2: [Story Name]"""

    def test_[functionality](self, [fixtures]):
        """[Description]."""
        [test_implementation]
```

### G-3: [Enhancement 3] Tests

```python
class Test[Enhancement3]:
    """Story G-3: [Story Name]"""

    def test_[functionality](self, [fixtures]):
        """[Description]."""
        [test_implementation]
```

---

## Guardrail Tests

These tests validate safeguards that prevent errors and ensure quality.

```bash
# Run guardrail tests
uv run --project [project_name] pytest tests/[feature]/test_guardrails.py -v
```

### H-1: [Guardrail 1]

```python
class Test[Guardrail1]:
    """Story H-1: [Story Name]"""

    def test_[constraint_enforced](self, [fixtures]):
        """[Constraint] is enforced."""
        result = [function]([params])

        [assertions]

    def test_[invalid_input_rejected](self, [fixtures]):
        """[Invalid input type] is rejected."""
        result = [function]([invalid_params])

        assert [invalid_not_in_result]
```

### H-2: [Guardrail 2]

```python
class Test[Guardrail2]:
    """Story H-2: [Story Name]"""

    async def test_[error_triggers_recovery](self, [fixtures]):
        """[Error type] triggers [recovery mechanism]."""
        result = await [function]([params_causing_error])

        if result.[first_attempt_error]:
            assert result.[recovery_attempted]

    async def test_[recovery_limited](self, [fixtures]):
        """[Recovery] is limited to prevent infinite loops."""
        result = await [function]([params])

        assert result.[attempt_count] <= [max_attempts]
```

### H-3: [Guardrail 3]

```python
class Test[Guardrail3]:
    """Story H-3: [Story Name]"""

    def test_[classification_simple](self, [classifier]):
        """[Simple inputs] are classified correctly."""
        result = [classifier].classify([simple_input])

        assert result.[category] == "[expected]"

    def test_[classification_complex](self, [classifier]):
        """[Complex inputs] are classified correctly."""
        result = [classifier].classify([complex_input])

        assert result.[category] == "[expected]"

    def test_[classifier_latency](self, [classifier], benchmark):
        """Classification completes in < [target]."""
        result = benchmark([classifier].classify, [input])

        assert benchmark.stats["mean"] < [target_seconds]
```

---

## End-to-End Validation

This section covers integration testing using [benchmark/test suite].

### Prerequisites

- ✅ [Feature] implementation complete (Phase X+)
- ✅ [Test infrastructure] set up
- ✅ [Test data] generated
- ✅ Feature flag implemented (`ENABLE_[FEATURE]`)

See [Setup Guide](./setup-guide.md) for setup instructions.

---

### Testing Methodology

#### 1. Baseline Run (Feature Disabled)

Run tests with feature **disabled** to establish baseline metrics.

```bash
# Set feature flag OFF
export ENABLE_[FEATURE]=false

# Run all tests
[test_command] \
  --tests=[test_pattern] \
  --output=results/baseline.json \
  --log-level=INFO
```

**What this captures:**

- Baseline accuracy (% tests passing)
- Baseline latency (per operation)
- Baseline resource usage
- Baseline error rates

---

#### 2. Treatment Run (Feature Enabled)

Run tests with feature **enabled**.

```bash
# Set feature flag ON
export ENABLE_[FEATURE]=true

# Run all tests (same set)
[test_command] \
  --tests=[test_pattern] \
  --output=results/treatment.json \
  --log-level=INFO
```

**What this captures:**

- Treatment accuracy
- Treatment latency
- Treatment resource usage
- [Feature-specific metric] (from logs)

---

#### 3. Comparison

Compare baseline vs treatment results:

```bash
[compare_command] \
  results/baseline.json \
  results/treatment.json \
  --output=results/comparison-report.md
```

---

### Test Corpus Selection

#### Recommended: Use Full Test Set

Test on **all [N] [test cases]** for comprehensive validation:

```bash
[test_command] --tests=[test_pattern] --[option]=all
```

**Why full set?**

- Diverse [variation 1]
- Multiple [variation 2]
- Mixed [variation 3]

#### Alternative: Stratified Sample

For faster iteration during development:

```bash
# Stratified sample
[test_command] --tests=[pattern] --[filter_1]=[value] --limit=40
[test_command] --tests=[pattern] --[filter_2]=[value] --limit=40
[test_command] --tests=[pattern] --[filter_3]=[value] --limit=20
```

---

## Metrics Collection

This section defines the metrics collected during testing.

### 1. [Primary Metric] (Primary)

**Definition:** [What this metric measures]

**Measurement:**

```bash
# Extract from results
jq '[extraction_query]' results/baseline.json
jq '[extraction_query]' results/treatment.json
```

**Target:** [Target] (from specification)

**Example:**

- Baseline: [value]
- Treatment: [value]
- **Improvement: [delta]** ✅

---

### 2. [Secondary Metric]

**Definition:** [What this metric measures]

**Measurement:** Extract from logs or instrumentation.

```python
# In [component] code
logger.info(
    "[event_name]",
    [field_1]=[value],
    [field_2]=[value],
    [feature]_enabled=True
)
```

**Analysis:**

```bash
# Average [metric] per run
jq '[extraction_query]' results/baseline.json
jq '[extraction_query]' results/treatment.json
```

**Target:** [Target] (from specification)

---

### 3. [Tertiary Metric]

**Definition:** [What this metric measures]

**Measurement:** Log [metric] during [operation].

```python
# In [component] code
logger.info(
    "[event_name]",
    [metric_field]=[value],
)
```

**Target:** [Target] (from specification)

---

### 4. [Recall/Precision Metric]

**Definition:**

- **[Recall metric]:** [Definition]
- **[Precision metric]:** [Definition]

**Measurement:** Requires [gold standard] annotations.

```python
# Compare [predicted] vs [gold]
recall = len(predicted & gold) / len(gold)
precision = len(predicted & gold) / len(predicted)
```

**Target:**

- [Recall]: > [target]
- [Precision]: > [target]

---

### 5. [Fallback/Error Rate]

**Definition:** % [operations] that trigger [fallback/error].

**Measurement:** Count [events] from logs.

```bash
# Count [event] occurrences
grep "[event_pattern]" logs/treatment.log | wc -l

# Calculate rate
echo "scale=2; $([count]) * 100 / $([total])" | bc
```

**Target:** < [target]% (from specification)

---

## Success Criteria

All targets from specification must be met:

| Metric                 | Target     | Baseline | Treatment | Status |
| ---------------------- | ---------- | -------- | --------- | ------ |
| **[Primary Metric]**   | [Target]   | [Value]  | [Value]   | ✅     |
| **[Secondary Metric]** | [Target]   | [Value]  | [Value]   | ✅     |
| **[Tertiary Metric]**  | [Target]   | [Value]  | [Value]   | ✅     |
| **[Recall Metric]**    | > [Target] | N/A      | [Value]   | ✅     |
| **[Precision Metric]** | > [Target] | N/A      | [Value]   | ✅     |
| **[Fallback Rate]**    | < [Target] | N/A      | [Value]   | ✅     |

**Pass criteria:** All metrics meet or exceed targets.

---

## Reporting Template

### Executive Summary

```markdown
# [Feature] Validation Report

**Date:** YYYY-MM-DD  
**Test Corpus:** [Description]  
**Environment:** [staging/production]

## Results Summary

✅ **All success criteria met**

- [Primary Metric]: **[value]** (target: [target])
- [Secondary Metric]: **[value]** (target: [target])
- [Tertiary Metric]: **[value]** (target: [target])
- [Fallback Rate]: **[value]** (target: <[target])

## Recommendation

✅ **Approve for production rollout**

[Feature] demonstrates consistent improvements across all metrics with no regressions.
```

### Detailed Metrics

```markdown
## Detailed Metrics

### 1. [Primary Metric]

| [Breakdown]  | Baseline | Treatment | Improvement |
| ------------ | -------- | --------- | ----------- |
| [Category 1] | [Value]  | [Value]   | [Delta]     |
| [Category 2] | [Value]  | [Value]   | [Delta]     |
| [Category 3] | [Value]  | [Value]   | [Delta]     |

**Average:** [baseline] → [treatment] ([delta])

### 2. [Secondary Metric]

| Percentile | Baseline | Treatment | Improvement |
| ---------- | -------- | --------- | ----------- |
| p50        | [Value]  | [Value]   | [Delta]     |
| p90        | [Value]  | [Value]   | [Delta]     |
| p99        | [Value]  | [Value]   | [Delta]     |

### 3. Failure Analysis

| Failure Mode | Count | % of Total |
| ------------ | ----- | ---------- |
| [Mode 1]     | [N]   | [%]        |
| [Mode 2]     | [N]   | [%]        |
| [Mode 3]     | [N]   | [%]        |

**Action items:**

- [Action 1]
- [Action 2]
```

---

## Troubleshooting

### Issue: [Common Issue 1]

**Symptoms:** [How to identify this issue]

**Diagnosis:**

```bash
# Check [diagnostic info]
grep "[pattern]" logs/treatment.log | jq '.[field]' | sort | uniq -c
```

**Common causes:**

- `[cause_1]` → [Solution]
- `[cause_2]` → [Solution]
- `[cause_3]` → [Solution]

---

### Issue: [Common Issue 2]

**Symptoms:** [How to identify this issue]

**Diagnosis:**

```bash
# Find [problematic cases]
jq -s '[query]' \
  results/baseline.json results/treatment.json
```

**Common causes:**

- [Cause 1] → Check [solution]
- [Cause 2] → Review [solution]
- [Cause 3] → Verify [solution]

---

### Issue: [Common Issue 3]

**Symptoms:** [How to identify this issue]

**Diagnosis:**

```bash
# Check if [feature] is running
grep "[event]" logs/treatment.log | wc -l
# Should equal number of [operations]
```

**Common causes:**

- Feature flag not working → Verify env var set
- [Cause 2] → [Solution]
- [Cause 3] → [Solution]

---

## Continuous Monitoring

After production rollout, monitor these metrics continuously:

```python
# Production metrics
metrics.gauge("[feature].[metric_1]", [value])
metrics.gauge("[feature].[metric_2]", [value])
metrics.gauge("[feature].[metric_3]", [value])
metrics.gauge("[feature].[fallback_rate]", [value])
```

**Alert thresholds:**

- [Metric 1] drops > [X]% from baseline → Investigate immediately
- [Fallback rate] > [X]% → Check [component] quality
- [Latency] increases > [X]% → Check for performance regression

---

## Appendix: Helper Scripts

### `scripts/analyze_[feature]_results.py`

Create this helper script to automate metric extraction:

```python
#!/usr/bin/env python3
"""Analyze [feature] validation results."""

import json
import sys
from pathlib import Path

def analyze(baseline_path: Path, treatment_path: Path) -> dict:
    """Compare baseline and treatment results."""

    with open(baseline_path) as f:
        baseline = json.load(f)
    with open(treatment_path) as f:
        treatment = json.load(f)

    # Calculate [primary metric]
    baseline_[metric] = [calculation]
    treatment_[metric] = [calculation]

    # Calculate [secondary metric]
    baseline_[metric_2] = [calculation]
    treatment_[metric_2] = [calculation]

    return {
        "[metric_1]": {
            "baseline": baseline_[metric],
            "treatment": treatment_[metric],
            "improvement": treatment_[metric] - baseline_[metric]
        },
        "[metric_2]": {
            "baseline": baseline_[metric_2],
            "treatment": treatment_[metric_2],
            "improvement_pct": (baseline_[metric_2] - treatment_[metric_2]) / baseline_[metric_2] * 100
        }
    }

if __name__ == "__main__":
    results = analyze(Path(sys.argv[1]), Path(sys.argv[2]))
    print(json.dumps(results, indent=2))
```

---

## References

- [Feature Specification](./feature-specification.md) - Success metrics and requirements
- [Architecture Guide](./architecture-guide.md) - Implementation details
- [Test Infrastructure Guide](./test-infrastructure.md) - Setup instructions
- [External Benchmark](URL) - Background on benchmark design

---

## Revision History

| Version | Date       | Author   | Changes               |
| ------- | ---------- | -------- | --------------------- |
| 1.0     | YYYY-MM-DD | [Author] | Initial testing guide |
| 1.1     | YYYY-MM-DD | [Author] | [Changes made]        |
