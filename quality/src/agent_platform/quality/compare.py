"""Compare quality test results between runs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from agent_platform.quality.export_results import ExportResults


@dataclass
class TestKey:
    """Unique identifier for a test result."""

    name: str
    platform: str
    agent_name: str
    trial_id: int

    def __hash__(self):
        return hash((self.name, self.platform, self.agent_name, self.trial_id))

    def __eq__(self, other):
        if not isinstance(other, TestKey):
            return False
        return (
            self.name == other.name
            and self.platform == other.platform
            and self.agent_name == other.agent_name
            and self.trial_id == other.trial_id
        )

    def __str__(self):
        return f"{self.name} ({self.platform}, {self.agent_name}, trial={self.trial_id})"


@dataclass
class TestComparison:
    """Comparison of a single test between two runs."""

    key: TestKey
    old_status: Literal["passed", "failed", "error"] | None
    new_status: Literal["passed", "failed", "error"] | None

    @property
    def status_changed(self) -> bool:
        """Check if status changed between runs."""
        return self.old_status != self.new_status

    @property
    def improved(self) -> bool:
        """Check if test improved (failed -> passed)."""
        return self.old_status in ("failed", "error") and self.new_status == "passed"

    @property
    def regressed(self) -> bool:
        """Check if test regressed (passed -> failed)."""
        return self.old_status == "passed" and self.new_status in ("failed", "error")


class ResultsComparator:
    """Compare two quality test results."""

    def __init__(self, old_results: ExportResults, new_results: ExportResults):
        self.old_results = old_results
        self.new_results = new_results

        # Build test dictionaries keyed by TestKey
        self.old_tests = {
            TestKey(
                name=test.name,
                platform=test.platform,
                agent_name=test.agent_name,
                trial_id=test.trial_id,
            ): test
            for test in old_results.tests
        }

        self.new_tests = {
            TestKey(
                name=test.name,
                platform=test.platform,
                agent_name=test.agent_name,
                trial_id=test.trial_id,
            ): test
            for test in new_results.tests
        }

    def get_summary_line(self, results: ExportResults) -> str:
        """Generate a single-line summary for a test run."""
        summary = results.summary
        return (
            f"Run {results.run_metadata.run_id}: "
            f"{summary.total_tests} tests, "
            f"{summary.passed} passed, "
            f"{summary.failed} failed, "
            f"{summary.error} errors "
            f"({summary.duration_seconds:.1f}s)"
        )

    def compare(self) -> list[TestComparison]:
        """Compare all tests between old and new runs."""
        # Get all unique test keys from both runs
        all_keys = set(self.old_tests.keys()) | set(self.new_tests.keys())

        comparisons = []
        for key in sorted(all_keys, key=lambda k: (k.agent_name, k.platform, k.name, k.trial_id)):
            old_test = self.old_tests.get(key)
            new_test = self.new_tests.get(key)

            comparison = TestComparison(
                key=key,
                old_status=old_test.status if old_test else None,
                new_status=new_test.status if new_test else None,
            )
            comparisons.append(comparison)

        return comparisons

    def get_only_in_old(self) -> list[TestKey]:
        """Get tests that only exist in old results."""
        return sorted(
            [key for key in self.old_tests if key not in self.new_tests],
            key=lambda k: (k.agent_name, k.platform, k.name, k.trial_id),
        )

    def get_only_in_new(self) -> list[TestKey]:
        """Get tests that only exist in new results."""
        return sorted(
            [key for key in self.new_tests if key not in self.old_tests],
            key=lambda k: (k.agent_name, k.platform, k.name, k.trial_id),
        )


def load_results(path: Path) -> ExportResults:
    """Load ExportResults from a JSON file."""
    with open(path) as f:
        data = json.load(f)
    return ExportResults.model_validate(data)


def format_comparison_line(comparison: TestComparison) -> str:
    """Format a comparison as a single line."""
    if comparison.old_status is None:
        return f"  ✨ NEW: {comparison.key} -> {comparison.new_status}"
    elif comparison.new_status is None:
        return f"  🗑️  REMOVED: {comparison.key} (was {comparison.old_status})"
    elif comparison.improved:
        return f"  ✅ IMPROVED: {comparison.key}: {comparison.old_status} -> {comparison.new_status}"
    elif comparison.regressed:
        return f"  ❌ REGRESSED: {comparison.key}: {comparison.old_status} -> {comparison.new_status}"
    else:
        return f"  🔄 CHANGED: {comparison.key}: {comparison.old_status} -> {comparison.new_status}"
