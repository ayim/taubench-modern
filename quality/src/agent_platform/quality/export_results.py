"""Export results module for stable JSON output format.

This module provides functionality to export quality test results in a stable,
single-file JSON format suitable for tracking test results over time.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class RunMetadata(BaseModel):
    """Metadata about a quality test run."""

    run_id: str = Field(description="Unique identifier for this test run")
    command: str = Field(description="The command that was executed")
    started_at: str = Field(description="ISO timestamp when the run started")
    completed_at: str = Field(description="ISO timestamp when the run completed")
    git_commit: str | None = Field(default=None, description="Git commit SHA of the monorepo at run time")


class TestSummary(BaseModel):
    """Summary statistics for a test run."""

    total_tests: int = Field(description="Total number of tests executed")
    passed: int = Field(description="Number of tests that passed")
    failed: int = Field(description="Number of tests that failed")
    error: int = Field(description="Number of tests that had errors")
    duration_seconds: float = Field(description="Total duration of the run in seconds")


class TestResult(BaseModel):
    """Result of a single test execution."""

    name: str = Field(description="Name of the test")
    platform: str = Field(description="Platform the test was run on")
    agent_name: str = Field(description="Name of the agent being tested")
    status: Literal["passed", "failed", "error"] = Field(description="Status of the test")
    model_id: str | None = Field(default=None, description="Model ID used for the test")
    trial_id: int = Field(description="Trial number (0-indexed)")
    started_at: str | None = Field(default=None, description="ISO timestamp when test started")
    completed_at: str = Field(description="ISO timestamp when test completed")
    duration_seconds: float | None = Field(default=None, description="Duration of the test in seconds")
    error: str | None = Field(default=None, description="Error message if test failed")


class ExportResults(BaseModel):
    """Complete export format for quality test results."""

    version: str = Field(default="1.0", description="Schema version")
    run_metadata: RunMetadata
    summary: TestSummary
    tests: list[TestResult]


def export_to_json_file(export_data: ExportResults, output_path: Path) -> None:
    """Export results to a JSON file.

    Args:
        export_data: The export data to write
        output_path: Path where the JSON file should be written
    """
    # Ensure parent directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write JSON file with proper formatting
    with open(output_path, "w") as f:
        f.write(export_data.model_dump_json(indent=2, exclude_none=False))


def calculate_duration_seconds(started_at: str | None, completed_at: str) -> float | None:
    """Calculate duration in seconds between two ISO timestamps.

    Args:
        started_at: ISO timestamp string for start time
        completed_at: ISO timestamp string for end time

    Returns:
        Duration in seconds, or None if started_at is None
    """
    if started_at is None:
        return None

    try:
        start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        end = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
        return (end - start).total_seconds()
    except (ValueError, AttributeError):
        return None
