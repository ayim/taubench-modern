import json
from pathlib import Path

import pytest
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExportResult
from opentelemetry.trace import SpanContext, TraceFlags
from opentelemetry.trace.status import Status, StatusCode

from agent_platform.server.telemetry.dir_span_exporter import DirSpanExporter


def _create_span_context(trace_id: int, span_id: int = 1) -> SpanContext:
    """Create a SpanContext with the given trace_id and span_id."""
    return SpanContext(
        trace_id=trace_id,
        span_id=span_id,
        is_remote=False,
        trace_flags=TraceFlags(0x01),
    )


def _create_readable_span(
    name: str,
    trace_id: int,
    attributes: dict | None = None,
    start_time: int | None = None,
    end_time: int | None = None,
    status: Status | None = None,
) -> ReadableSpan:
    """Create a ReadableSpan with the given parameters."""
    if start_time is None:
        start_time = 1_000_000_000_000_000_000
    if end_time is None:
        end_time = start_time + 1_000_000_000  # 1 second later
    if status is None:
        status = Status(StatusCode.OK)
    if attributes is None:
        attributes = {}

    context = _create_span_context(trace_id)
    return ReadableSpan(
        name=name,
        context=context,
        attributes=attributes,
        start_time=start_time,
        end_time=end_time,
        status=status,
    )


@pytest.mark.asyncio
async def test_format_prompt_with_input_output_values(
    exporter: DirSpanExporter, output_dir: Path, file_regression
) -> None:
    """Test that format_prompt spans with input.value and output.value are formatted correctly."""
    # Create a span with format_prompt name and input.value/output.value attributes
    input_value = json.dumps(
        {
            "prompt": "Test prompt\nanother value\nand another value",
            "model": "gpt-4",
            "simple_string": "just a string",
            "big_string": "a" * 300,
        }
    )
    output_value = json.dumps({"response": "Test response\nanother value\nand another value", "tokens": 100})

    span = _create_readable_span(
        name="format_prompt",
        trace_id=12345,
        attributes={
            "agent_name": "test_agent",
            "thread_name": "test_thread",
            "input.value": input_value,
            "output.value": output_value,
        },
    )

    result = exporter.export([span])
    assert result == SpanExportResult.SUCCESS

    # Find the exported file
    exported_files = list(output_dir.glob("**/*.txt"))
    assert len(exported_files) == 1

    # Read and verify the content
    content = exported_files[0].read_text(encoding="utf-8")
    file_regression.check(content)


@pytest.mark.asyncio
async def test_other_attributes_formatted_with_pretty_print(
    output_dir: Path, exporter: DirSpanExporter, file_regression
) -> None:
    """Test that other attributes are formatted with pretty print."""
    # Create a span with various attributes
    span = _create_readable_span(
        name="test_operation",
        trace_id=67890,
        attributes={
            "agent_name": "test_agent",
            "thread_name": "test_thread",
            "custom_attr": json.dumps({"key": "value", "nested": {"a": 1, "b": 2}}),
            "simple_string": "just a string",
            "number": 42,
        },
    )

    result = exporter.export([span])
    assert result == SpanExportResult.SUCCESS

    # Find the exported file
    exported_files = list(output_dir.glob("**/*.txt"))
    assert len(exported_files) == 1, f"Expected 1 exported file, got {len(exported_files)}: {exported_files}"

    # Read and verify the content
    content = exported_files[0].read_text(encoding="utf-8")
    file_regression.check(content)


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    return tmp_path / "output"


@pytest.fixture
def exporter(output_dir: Path):
    exporter = DirSpanExporter(output_dir)
    exporter.max_entries_in_disk = 5  # Set a small limit for testing
    yield exporter
    exporter.shutdown()


@pytest.mark.asyncio
async def test_old_entries_removed_when_max_entries_reached(output_dir: Path, exporter: DirSpanExporter) -> None:
    """Test that old entries are removed from disk when max_entries_in_disk is reached."""
    from sema4ai.common.wait_for import wait_for_non_error_condition

    # Create initial directories to reach the limit
    # Each unique agent_name-thread_name combination creates a new directory
    for i in range(5):
        span = _create_readable_span(
            name=f"test_span_{i}",
            trace_id=1000 + i,
            attributes={
                "agent_name": f"agent_{i}",
                "thread_name": f"thread_{i}",
            },
        )
        exporter.export([span])

    def check_5_dirs():
        directories_before = [d for d in output_dir.iterdir() if d.is_dir()]
        assert len(directories_before) == 5, (
            f"Expected 5 directories, got {len(directories_before)}: {directories_before}"
        )

    wait_for_non_error_condition(check_5_dirs)

    # Now add more spans that will trigger cleanup
    for i in range(5, 8):  # Add 3 more, should trigger cleanup
        span = _create_readable_span(
            name=f"test_span_{i}",
            trace_id=1000 + i,
            attributes={
                "agent_name": f"agent_{i}",
                "thread_name": f"thread_{i}",
            },
        )
        exporter.export([span])

    def check_dirs_after():
        # Count directories - should be at most max_entries_in_disk
        directories_after = [d for d in output_dir.iterdir() if d.is_dir()]
        dirs_after_str = "\n".join(str(d) for d in directories_after)

        i_dirs_found = set()
        for directory in directories_after:
            # Should start with a number followed by underscore
            parts = directory.name.split("_", 1)
            i_dir_found = int(parts[0])
            i_dirs_found.add(i_dir_found)

        expected = set(range(4, 9))
        assert i_dirs_found == expected, f"Expected directories {expected}, got {i_dirs_found}\n{dirs_after_str}"

    wait_for_non_error_condition(check_dirs_after)
