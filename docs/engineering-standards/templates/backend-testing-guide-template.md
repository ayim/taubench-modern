# Backend Testing Guide: [Feature Name]

> **For AI Assistants:** Invoke `python-guidelines` skill. Map each story to tests: unit (mocked), integration (real DB), performance (if targets exist). Run from root: `make test-unit`

**Related:** [Specification](./feature-specification.md) | [Implementation](./implementation-guide.md)

---

## Story-to-Test Mapping

| Story | Test Type          | Test File                              |
| ----- | ------------------ | -------------------------------------- |
| A-1   | Unit               | `test_[module].py::test_story_a1`      |
| A-2   | Unit + Integration | `test_[module].py::test_story_a2_*`    |
| B-1   | Integration        | `test_[integration].py::test_story_b1` |

---

## Unit Tests

### Test [Story A-1]

```python
async def test_story_a1_basic():
    """Test [what this story does]."""
    # Arrange
    input_data = {...}

    # Act
    result = await function(input_data)

    # Assert
    assert result.field == expected_value
```

### Test [Story A-2]

```python
async def test_story_a2_edge_case():
    """Test edge case: [describe scenario]."""
    # Test implementation
```

---

## Integration Tests

### Test [Story B-1]

```python
async def test_story_b1_with_db(test_db):
    """Test [story] with real database."""
    # Arrange: Insert test data
    await test_db.execute("INSERT INTO ...")

    # Act: Execute feature
    result = await feature_function()

    # Assert: Verify database state
    rows = await test_db.fetch("SELECT * FROM ...")
    assert len(rows) == expected_count
```

---

## Performance Tests

```python
async def test_performance_target():
    """Verify < [X]ms latency target."""
    start = time.perf_counter()

    result = await function(large_input)

    elapsed_ms = (time.perf_counter() - start) * 1000
    assert elapsed_ms < target_ms
```

---

## Test Data

```python
# Minimal test data (< 100 rows)
TEST_DATA = {
    "users": [...],
    "items": [...],
}
```

---

## Running Tests

```bash
# From repo root
make test-unit
make test-integration

# Specific test
uv run --project agent_platform_server pytest path/to/test.py::test_name -v
```
