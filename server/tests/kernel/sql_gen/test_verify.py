"""Tests for SQL generation query verification logic."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from agent_platform.core.data_frames.data_frames import PlatformDataFrame
from agent_platform.core.prompts import Prompt
from agent_platform.core.responses.content import ResponseTextContent
from agent_platform.core.responses.response import ResponseMessage
from agent_platform.server.kernel.sql_gen.types import Column, Result, Shape
from agent_platform.server.kernel.sql_gen.verify import (
    extract_actual_shape,
    generate_feedback,
    predict_expected_shape,
)

# -----------------------------------------------------------------------------
# Test Fixtures
# -----------------------------------------------------------------------------


class FakePlatform:
    """Fake platform that returns a configurable response."""

    def __init__(self, response_text: str | list[str]) -> None:
        """Initialize with a single response or a list of responses for sequential calls."""
        if isinstance(response_text, str):
            self._responses = [response_text]
        else:
            self._responses = response_text
        self._call_count = 0

    async def generate_response(self, prompt: Prompt, model: str) -> ResponseMessage:
        response_text = self._responses[min(self._call_count, len(self._responses) - 1)]
        self._call_count += 1
        return ResponseMessage(
            content=[ResponseTextContent(text=response_text)],
            role="agent",
        )


class FakeKernel:
    """Fake kernel for testing functions that require LLM access."""

    def __init__(self, platform: FakePlatform) -> None:
        self._platform = platform
        self._model = "test-model"

    async def get_platform_and_model(self, **_kwargs) -> tuple[FakePlatform, str]:
        return self._platform, self._model


def make_dataframe(
    columns: dict[str, str],
    num_rows: int,
) -> PlatformDataFrame:
    """Create a PlatformDataFrame for testing."""
    return PlatformDataFrame(
        data_frame_id=str(uuid4()),
        user_id="test-user",
        agent_id="test-agent",
        thread_id="test-thread",
        num_rows=num_rows,
        num_columns=len(columns),
        column_headers=list(columns.keys()),
        columns=columns,
        name="test_dataframe",
        input_id_type="in_memory",
        created_at=datetime.now(UTC),
        computation_input_sources={},
    )


# -----------------------------------------------------------------------------
# Tests for extract_actual_shape
# -----------------------------------------------------------------------------


def test_extract_actual_shape_happy_path():
    """Extract shape from dataframe with multiple columns and rows."""
    columns = {
        "id": "int64",
        "name": "string",
        "price": "float64",
        "is_active": "bool",
    }
    df = make_dataframe(columns=columns, num_rows=42)

    result = extract_actual_shape(df)

    assert isinstance(result, Result)
    assert result.row_count == 42
    assert len(result.columns) == 4
    # Verify column structure
    column_names = {col.name for col in result.columns}
    assert column_names == {"id", "name", "price", "is_active"}
    # Verify types are preserved
    for col in result.columns:
        assert col.type == columns[col.name]


def test_extract_actual_shape_empty_dataframe():
    """Extract shape from empty dataframe returns zero counts."""
    df = make_dataframe(columns={}, num_rows=0)

    result = extract_actual_shape(df)

    assert isinstance(result, Result)
    assert result.row_count == 0
    assert result.columns == []


# -----------------------------------------------------------------------------
# Tests for predict_expected_shape
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_predict_expected_shape_happy_path():
    """Predict expected shape with valid LLM response."""
    llm_response = """{
        "expected_columns": [
            {"name": "total_sales", "type": "numeric"},
            {"name": "region", "type": "string"}
        ],
        "row_cardinality": "many_rows"
    }"""
    kernel = FakeKernel(FakePlatform(llm_response))

    result = await predict_expected_shape(
        kernel=kernel,  # type: ignore[arg-type]
        query_intent="Show total sales by region",
        sdm_context="Tables: sales(id, amount, region_id), regions(id, name)",
    )

    assert isinstance(result, Shape)
    assert result.row_cardinality == "many_rows"
    assert len(result.expected_columns) == 2
    column_names = {col.name for col in result.expected_columns}
    assert column_names == {"total_sales", "region"}


@pytest.mark.asyncio
async def test_predict_expected_shape_malformed_json():
    """Raise ValueError when LLM returns invalid JSON after all retries."""
    llm_response = "This is not valid JSON at all"
    kernel = FakeKernel(FakePlatform(llm_response))

    with pytest.raises(ValueError, match="Failed to parse LLM response as Shape after 3 attempts"):
        await predict_expected_shape(
            kernel=kernel,  # type: ignore[arg-type]
            query_intent="Get total count",
            sdm_context="Tables: items(id, name)",
        )


@pytest.mark.asyncio
async def test_predict_expected_shape_retry_success():
    """Successfully parse shape after retry when first attempt fails."""
    valid_response = """{
        "expected_columns": [{"name": "count", "type": "numeric"}],
        "row_cardinality": "one_row"
    }"""
    # First call returns invalid JSON, second call returns valid JSON
    kernel = FakeKernel(FakePlatform(["invalid json", valid_response]))

    result = await predict_expected_shape(
        kernel=kernel,  # type: ignore[arg-type]
        query_intent="Get total count",
        sdm_context="Tables: items(id, name)",
    )

    assert isinstance(result, Shape)
    assert result.row_cardinality == "one_row"
    assert len(result.expected_columns) == 1


# -----------------------------------------------------------------------------
# Tests for generate_feedback
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_feedback_happy_path():
    """Generate feedback when shapes mismatch."""
    llm_response = """{
        "feedback": [
            "Add column 'category' to match expected output",
            "Remove column 'internal_id' which was not requested"
        ]
    }"""
    kernel = FakeKernel(FakePlatform(llm_response))

    actual_shape = Result(
        columns=[Column(name="internal_id", type="int64")],
        row_count=10,
    )
    expected_shape = Shape(
        expected_columns=[Column(name="category", type="string")],
        row_cardinality="many_rows",
    )

    result = await generate_feedback(
        kernel=kernel,  # type: ignore[arg-type]
        query_intent="List product categories",
        actual_shape=actual_shape,
        expected_shape=expected_shape,
    )

    assert len(result) == 2
    assert "category" in result[0]
    assert "internal_id" in result[1]


@pytest.mark.asyncio
async def test_generate_feedback_malformed_json():
    """Raise ValueError when LLM returns invalid JSON after all retries."""
    llm_response = "{ invalid json here }"
    kernel = FakeKernel(FakePlatform(llm_response))

    with pytest.raises(ValueError, match="Failed to parse LLM response as Feedback after 3 attempts"):
        await generate_feedback(
            kernel=kernel,  # type: ignore[arg-type]
            query_intent="Get sales total",
            actual_shape=Result(columns=[], row_count=0),
            expected_shape=Shape(expected_columns=[], row_cardinality="one_row"),
        )


@pytest.mark.asyncio
async def test_generate_feedback_retry_success():
    """Successfully parse feedback after retry when first attempt fails."""
    valid_response = '{"feedback": ["Add missing column"]}'
    # First call returns invalid JSON, second call returns valid JSON
    kernel = FakeKernel(FakePlatform(["not json", valid_response]))

    result = await generate_feedback(
        kernel=kernel,  # type: ignore[arg-type]
        query_intent="Get sales total",
        actual_shape=Result(columns=[], row_count=0),
        expected_shape=Shape(expected_columns=[], row_cardinality="one_row"),
    )

    assert result == ["Add missing column"]
