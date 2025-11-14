#!/usr/bin/env python3
"""
Work Items Transaction Log Analyzer

This script analyzes work items transaction logs to verify exactly-once processing
and identify any issues with work item execution.

Usage:
    python analyze_work_items_transactions.py work_items_transaction.log
    python analyze_work_items_transactions.py logs/work_items_transaction.log*

The script will:
1. Parse JSON transaction log entries
2. Group events by work_item_id
3. Verify the expected event sequence
4. Flag any anomalies (duplicates, missing events, etc.)
5. Generate a summary report

Expected event sequence:
    work_item_started → agent_completed → judge_started/judge_skipped →
    judge_completed (if started) → work_item_finished
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class WorkItemEvent:
    """Represents a single transaction log event."""

    event_type: str
    timestamp: str
    work_item_id: str
    raw_data: dict[str, Any]

    @property
    def timestamp_dt(self) -> datetime:
        """Parse timestamp to datetime object."""
        return datetime.fromisoformat(self.timestamp.replace("Z", "+00:00"))


@dataclass
class WorkItemExecution:
    """Tracks all events for a single work item execution."""

    work_item_id: str
    events: list[WorkItemEvent] = field(default_factory=list)

    def add_event(self, event: WorkItemEvent) -> None:
        """Add an event to this execution."""
        self.events.append(event)

    @property
    def sorted_events(self) -> list[WorkItemEvent]:
        """Return events sorted by timestamp."""
        return sorted(self.events, key=lambda e: e.timestamp_dt)

    @property
    def event_types(self) -> list[str]:
        """Return list of event types in order."""
        return [e.event_type for e in self.sorted_events]

    @property
    def is_complete(self) -> bool:
        """Check if execution has a work_item_finished event."""
        return "work_item_finished" in self.event_types

    @property
    def final_status(self) -> str | None:
        """Get the final status from work_item_finished event."""
        for event in self.sorted_events:
            if event.event_type == "work_item_finished":
                return event.raw_data.get("final_status")
        return None

    @property
    def duration_seconds(self) -> float | None:
        """Calculate duration from start to finish."""
        if len(self.events) < 2:
            return None
        sorted_events = self.sorted_events
        start = sorted_events[0].timestamp_dt
        end = sorted_events[-1].timestamp_dt
        return (end - start).total_seconds()

    def validate(self) -> list[str]:
        """Validate the event sequence and return any issues found."""
        issues = []
        event_types = self.event_types

        # Check for expected start
        if not event_types or event_types[0] != "work_item_started":
            issues.append("Missing or out-of-order 'work_item_started' event")

        # Check for duplicates
        event_counts: dict[str, int] = {}
        for event_type in event_types:
            event_counts[event_type] = event_counts.get(event_type, 0) + 1

        for event_type, count in event_counts.items():
            if count > 1:
                issues.append(f"Duplicate event: {event_type} (x{count})")

        # Check for incomplete execution
        if not self.is_complete:
            issues.append("Missing 'work_item_finished' event - execution incomplete")

        # Check for expected sequence
        if "agent_completed" in event_types:
            agent_idx = event_types.index("agent_completed")
            if agent_idx == 0:
                issues.append("'agent_completed' before 'work_item_started'")

        # Check judge logic
        has_judge_started = "judge_started" in event_types
        has_judge_skipped = "judge_skipped" in event_types
        has_judge_completed = "judge_completed" in event_types

        if has_judge_started and has_judge_skipped:
            issues.append("Both 'judge_started' and 'judge_skipped' present")

        if has_judge_started and not has_judge_completed:
            issues.append("'judge_started' without 'judge_completed'")

        if has_judge_completed and not has_judge_started:
            issues.append("'judge_completed' without 'judge_started'")

        if not has_judge_started and not has_judge_skipped and self.is_complete:
            issues.append("No judge event (neither started nor skipped)")

        return issues


class TransactionLogAnalyzer:
    """Analyzes work items transaction logs."""

    def __init__(self):
        self.executions: dict[str, WorkItemExecution] = defaultdict(
            lambda: WorkItemExecution(work_item_id="")
        )
        self.parse_errors: list[tuple[str, str]] = []

    def parse_log_file(self, file_path: Path) -> None:
        """Parse a single log file."""
        print(f"Parsing: {file_path}")

        try:
            with open(file_path) as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        data = json.loads(line)
                        event = WorkItemEvent(
                            event_type=data.get("event_type", data.get("event", "unknown")),
                            timestamp=data.get("timestamp", ""),
                            work_item_id=data.get("work_item_id", "unknown"),
                            raw_data=data,
                        )

                        if event.work_item_id == "unknown":
                            self.parse_errors.append(
                                (str(file_path), f"Line {line_num}: Missing work_item_id")
                            )
                            continue

                        if event.work_item_id not in self.executions:
                            self.executions[event.work_item_id] = WorkItemExecution(
                                work_item_id=event.work_item_id
                            )

                        self.executions[event.work_item_id].add_event(event)

                    except json.JSONDecodeError as e:
                        self.parse_errors.append(
                            (str(file_path), f"Line {line_num}: Invalid JSON - {e}")
                        )

        except FileNotFoundError:
            print(f"Error: File not found: {file_path}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error reading file {file_path}: {e}", file=sys.stderr)
            sys.exit(1)

    def analyze(self) -> dict[str, Any]:
        """Analyze all executions and return summary."""
        total_executions = len(self.executions)
        complete_executions = sum(1 for e in self.executions.values() if e.is_complete)
        incomplete_executions = total_executions - complete_executions

        executions_with_issues = []
        clean_executions = []

        for work_item_id, execution in self.executions.items():
            issues = execution.validate()
            if issues:
                executions_with_issues.append((work_item_id, execution, issues))
            else:
                clean_executions.append((work_item_id, execution))

        # Calculate durations for completed executions
        durations = []
        for _, execution in clean_executions:
            if execution.duration_seconds is not None:
                durations.append(execution.duration_seconds)

        avg_duration = sum(durations) / len(durations) if durations else 0
        min_duration = min(durations) if durations else 0
        max_duration = max(durations) if durations else 0

        # Track final statuses
        status_counts: dict[str, int] = defaultdict(int)
        for execution in self.executions.values():
            if execution.final_status:
                status_counts[execution.final_status] += 1
            elif execution.is_complete:
                status_counts["UNKNOWN"] += 1

        return {
            "total_executions": total_executions,
            "complete_executions": complete_executions,
            "incomplete_executions": incomplete_executions,
            "clean_executions": len(clean_executions),
            "executions_with_issues": len(executions_with_issues),
            "issues_list": executions_with_issues,
            "parse_errors": self.parse_errors,
            "avg_duration": avg_duration,
            "min_duration": min_duration,
            "max_duration": max_duration,
            "status_counts": status_counts,
        }

    def print_report(self, summary: dict[str, Any], verbose: bool = False) -> None:
        """Print analysis report."""
        print("\n" + "=" * 80)
        print("WORK ITEMS TRANSACTION LOG ANALYSIS")
        print("=" * 80)

        print(f"\nTotal work items: {summary['total_executions']}")
        print(f"Complete executions: {summary['complete_executions']}")
        print(f"Incomplete executions: {summary['incomplete_executions']}")
        print(f"Clean executions: {summary['clean_executions']}")
        print(f"Executions with issues: {summary['executions_with_issues']}")

        # Final status breakdown
        if summary["status_counts"]:
            print("\nFinal Status Breakdown:")
            for status, count in sorted(summary["status_counts"].items()):
                print(f"  {status}: {count}")

        if summary["avg_duration"] > 0:
            print("\nExecution times (clean executions only):")
            print(f"  Average: {summary['avg_duration']:.2f}s")
            print(f"  Min: {summary['min_duration']:.2f}s")
            print(f"  Max: {summary['max_duration']:.2f}s")

        # Parse errors
        if summary["parse_errors"]:
            print(f"\n⚠️  Parse Errors: {len(summary['parse_errors'])}")
            for file_path, error in summary["parse_errors"]:
                print(f"  - {file_path}: {error}")

        # Issues
        if summary["issues_list"]:
            print(f"\n⚠️  Executions with Issues: {len(summary['issues_list'])}")
            for work_item_id, execution, issues in summary["issues_list"]:
                print(f"\n  Work Item: {work_item_id}")
                if execution.final_status:
                    print(f"  Final Status: {execution.final_status}")
                print(f"  Event sequence: {' → '.join(execution.event_types)}")
                for issue in issues:
                    print(f"    ❌ {issue}")

                if verbose:
                    print("  Events:")
                    for event in execution.sorted_events:
                        print(f"    - {event.timestamp} {event.event_type}")

        # Exactly-once verification
        print("\n" + "=" * 80)
        print("EXACTLY-ONCE PROCESSING VERIFICATION")
        print("=" * 80)

        if summary["executions_with_issues"] == 0 and len(summary["parse_errors"]) == 0:
            print("✅ All work items processed exactly once with no issues!")
        else:
            print("❌ Issues detected that may indicate problems with exactly-once processing")
            print(f"   - {summary['executions_with_issues']} work items with event issues")
            print(f"   - {len(summary['parse_errors'])} parse errors")

        # Detailed breakdown if verbose
        if verbose and summary["clean_executions"] > 0:
            print("\n" + "=" * 80)
            print("CLEAN EXECUTIONS (sample)")
            print("=" * 80)
            # Show first 5 clean executions
            count = 0
            for work_item_id, execution in self.executions.items():
                if count >= 5:
                    break
                if not execution.validate():
                    print(f"\n  Work Item: {work_item_id}")
                    if execution.final_status:
                        print(f"  Final Status: {execution.final_status}")
                    if execution.duration_seconds:
                        print(f"  Duration: {execution.duration_seconds:.2f}s")
                    print(f"  Events: {' → '.join(execution.event_types)}")
                    count += 1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze work items transaction logs for exactly-once processing verification",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "log_files",
        nargs="+",
        type=Path,
        help="One or more transaction log files to analyze",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed information for all executions",
    )

    args = parser.parse_args()

    analyzer = TransactionLogAnalyzer()

    # Parse all log files
    for log_file in args.log_files:
        analyzer.parse_log_file(log_file)

    # Analyze and print report
    summary = analyzer.analyze()
    analyzer.print_report(summary, verbose=args.verbose)

    # Exit with error code if issues found
    if summary["executions_with_issues"] > 0 or len(summary["parse_errors"]) > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
