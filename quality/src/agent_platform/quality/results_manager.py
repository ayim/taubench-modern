from __future__ import annotations

import dataclasses
import json
import threading
from datetime import datetime
from pathlib import Path

import structlog
import yaml

from agent_platform.quality.models import AgentPackage, Platform, TestCase, ThreadResult

logger = structlog.get_logger(__name__)


class QualityResultsManager:
    """Manages incremental writing of quality test results to JSON files in datadir."""

    def __init__(
        self,
        datadir: Path,
        all_agents: list[AgentPackage] | None = None,
        export_results_path: Path | None = None,
        command_args: str | None = None,
    ):
        self.datadir = datadir
        self.results_dir = datadir / "quality_results"
        self.runs_dir = self.results_dir / "runs"

        # Export configuration
        # - None: don't export
        # - Path: export to this specific path
        self.export_results_path = export_results_path
        self.command_args = command_args or "quality-test run"

        # Current run metadata
        self.current_run_id = datetime.now().strftime("run_%Y-%m-%d_%H-%M-%S")
        self.current_run_dir = self.runs_dir / self.current_run_id

        # Thread safety locks
        self._status_lock = threading.Lock()
        self._file_locks = {}  # Per-file locks for thread safety

        # Initialize directory structure
        self._init_directories()

        # Initialize status tracking
        self.current_status = {
            "run_id": self.current_run_id,
            "current_run_dir": str(self.current_run_dir),
            "started_at": datetime.now().isoformat(),
            "status": "initializing",
            "agents": {},
            "overall_stats": {
                "total_agents": 0,
                "completed_agents": 0,
                "total_tests": 0,
                "completed_tests": 0,
                "passed_tests": 0,
                "failed_tests": 0,
            },
        }

        # Collected test results for export
        self._export_test_results: list[dict] = []

        # Write initial status
        self._write_status()

        # Write all available agents to agents.json for UI
        if all_agents:
            self._write_all_agents(all_agents)

    def _init_directories(self):
        """Initialize the directory structure."""
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.current_run_dir.mkdir(parents=True, exist_ok=True)

    def _build_test_id(
        self,
        test_case_name: str,
        platform_name: str,
        model_id: str | None = None,
        index: int | None = None,
    ) -> str:
        """Build a test ID from test case, platform, optional model, and optional index.

        Args:
            test_case_name: Name of the test case
            platform_name: Name of the platform
            model_id: Optional model ID (will be sanitized for filename safety)
            index: Optional trial index to append

        Returns:
            Test ID string with components joined by underscores
        """
        parts = [test_case_name, platform_name]
        if model_id:
            # Sanitize model_id for filename safety (replace / with __)
            safe_model_id = model_id.replace("/", "__")
            parts.append(safe_model_id)
        if index is not None:
            parts.append(str(index))
        return "_".join(parts)

    def _write_status(self):
        """Write current status to status.json."""
        status_file = self.results_dir / "status.json"

        # Get or create lock for this file
        if "status.json" not in self._file_locks:
            self._file_locks["status.json"] = threading.Lock()

        with self._file_locks["status.json"]:
            try:
                self.results_dir.mkdir(parents=True, exist_ok=True)
                with open(status_file, "w") as f:
                    json.dump(self.current_status, f, indent=2, default=self._json_default)
            except Exception as e:
                logger.error(f"Failed to write status file: {e}")

    def _write_summary(self):
        """Write overall summary to summary.json."""
        summary_file = self.results_dir / "summary.json"

        # Get or create lock for this file
        if "summary.json" not in self._file_locks:
            self._file_locks["summary.json"] = threading.Lock()

        with self._file_locks["summary.json"]:
            summary_data = {
                "last_run_id": self.current_run_id,
                "last_updated": datetime.now().isoformat(),
                "stats": self.current_status["overall_stats"],
                "agents": {
                    agent_name: {
                        "total_tests": agent_data.get("total_tests", 0),
                        "completed_tests": agent_data.get("completed_tests", 0),
                        "passed_tests": agent_data.get("passed_tests", 0),
                        "failed_tests": agent_data.get("failed_tests", 0),
                        "status": agent_data.get("status", "unknown"),
                    }
                    for agent_name, agent_data in self.current_status["agents"].items()
                },
            }

            try:
                self.results_dir.mkdir(parents=True, exist_ok=True)
                with open(summary_file, "w") as f:
                    json.dump(summary_data, f, indent=2, default=self._json_default)
            except Exception as e:
                logger.error(f"Failed to write summary file: {e}")

    def start_agent_testing(
        self,
        agent_package: AgentPackage,
        test_cases: list[TestCase],
        platform_filter: str | None = None,
    ):
        """Initialize tracking for an agent's test run."""
        logger.info(f"Starting agent testing: {agent_package.name}")

        def filtered_platforms(test_case: TestCase) -> list[Platform]:
            if platform_filter is None:
                return list(test_case.target_platforms)
            return [p for p in test_case.target_platforms if p.name == platform_filter]

        # Calculate total tests for this agent (respecting platform filter and models)
        # For each test case: sum(for each platform: num_models * trials)
        total_tests = 0
        for tc in test_cases:
            for platform in filtered_platforms(tc):
                # Count models for this platform
                target_models_for_platform = tc.target_models.get(platform.name, [])
                num_models = len(target_models_for_platform) if target_models_for_platform else 1
                total_tests += num_models * tc.trials

        # Initialize agent status
        self.current_status["agents"][agent_package.name] = {
            "status": "running",
            "started_at": datetime.now().isoformat(),
            "total_tests": total_tests,
            "completed_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "current_test": None,
            "error": None,
        }

        # Update overall stats
        self.current_status["overall_stats"]["total_agents"] += 1
        self.current_status["overall_stats"]["total_tests"] += total_tests
        self.current_status["status"] = "running"

        # Write agent metadata to current run directory
        metadata = {
            "name": agent_package.name,
            "zip_path": str(agent_package.zip_path),
            "test_cases": [
                {
                    "name": tc.name,
                    "description": tc.description,
                    "file_path": str(tc.file_path),
                    "target_platforms": [p.name for p in filtered_platforms(tc)],
                    "evaluations": [
                        {"kind": e.kind, "expected": str(e.expected), "description": e.description}
                        for e in tc.evaluations
                    ],
                }
                for tc in test_cases
            ],
            "total_tests": total_tests,
            "started_at": datetime.now().isoformat(),
        }

        metadata_file = self.current_run_dir / f"{agent_package.name}_metadata.json"
        try:
            self.current_run_dir.mkdir(parents=True, exist_ok=True)
            with open(metadata_file, "w") as f:
                json.dump(metadata, f, indent=2, default=self._json_default)
        except Exception as e:
            logger.error(f"Failed to write agent metadata: {e}")

        self._write_status()
        self._write_summary()

    def start_test(self, agent_name: str, test_case: TestCase, platform: Platform, model_id: str | None = None):
        """Mark the start of a specific test."""
        # Build test_id that includes model if present
        test_id = self._build_test_id(test_case.name, platform.name, model_id)

        logger.info(f"Starting test: {agent_name}/{test_id}")

        if agent_name in self.current_status["agents"]:
            current_test_info = {
                "test_name": test_case.name,
                "platform": platform.name,
                "started_at": datetime.now().isoformat(),
                "status": "running",
            }
            if model_id:
                current_test_info["model_id"] = model_id

            self.current_status["agents"][agent_name]["current_test"] = current_test_info

            self._write_status()

    def complete_test(self, agent_name: str, result: ThreadResult, index: int):
        """Record completion of a specific test."""
        # Build test_id that includes model if present and index
        test_id = self._build_test_id(
            result.test_case.name,
            result.platform.name,
            result.model_id,
            index,
        )

        logger.info(f"Completing test: {agent_name}/{test_id} - Success: {result.success}")

        # Thread-safe test completion - use status lock for shared state updates
        with self._status_lock:
            try:
                # Get the start time from the current test (if available)
                started_at = None
                if (
                    agent_name in self.current_status["agents"]
                    and self.current_status["agents"][agent_name]["current_test"]
                ):
                    current_test = self.current_status["agents"][agent_name]["current_test"]
                    if (
                        current_test["test_name"] == result.test_case.name
                        and current_test["platform"] == result.platform.name
                    ):
                        started_at = current_test["started_at"]

                # Convert ThreadResult to JSON-serializable format
                result_data = {
                    "agent_name": agent_name,
                    "agent_id": result.agent_id,
                    "thread_id": result.thread_id,
                    "trial_id": index,
                    "test_name": result.test_case.name,
                    "platform": result.platform.name,
                    "model_id": result.model_id,
                    "success": result.success,
                    "started_at": started_at,
                    "completed_at": datetime.now().isoformat(),
                    "error": result.error,
                    "test_case": {
                        "name": result.test_case.name,
                        "trials": result.test_case.trials,
                        "metrics": [{"name": m.name, "k": m.k} for m in result.test_case.metrics],
                        "description": result.test_case.description,
                        "file_path": str(result.test_case.file_path),
                        "evaluations": [
                            {
                                "kind": e.kind,
                                "expected": str(e.expected),
                                "description": e.description,
                            }
                            for e in result.test_case.evaluations
                        ],
                        "thread": self._serialize_thread(getattr(result.test_case, "thread", None)),
                        "workitem": self._serialize_workitem(getattr(result.test_case, "workitem", None)),
                    },
                    "agent_messages": [
                        {
                            "role": msg.role,
                            "content": [self._serialize_content(content) for content in msg.content],
                        }
                        for msg in result.agent_messages
                    ],
                    "evaluation_results": [
                        {
                            "kind": eval_result.evaluation.kind,
                            "expected": str(eval_result.evaluation.expected),
                            "passed": eval_result.passed,
                            "actual_value": json.dumps(eval_result.actual_value),
                            "error": eval_result.error,
                            "reference_sql": result.test_case.reference_sql,
                        }
                        for eval_result in result.evaluation_results
                    ],
                }

                # Write test result to current run directory (individual files are safe)
                run_test_file = self.current_run_dir / f"{agent_name}_{test_id}.json"
                # Ensure the run directory exists
                self.current_run_dir.mkdir(parents=True, exist_ok=True)
                with open(run_test_file, "w") as f:
                    json.dump(result_data, f, indent=2, default=self._json_default)

                if result.thread_files is not None:
                    thread_files_file = self.current_run_dir / f"{agent_name}_{test_id}.files.yml"
                    # Convert UploadedFile dataclasses to dicts for serialization
                    thread_files_data = [dataclasses.asdict(f) for f in result.thread_files]
                    with open(thread_files_file, "w") as file:
                        yaml.dump(thread_files_data, file, default_flow_style=False, sort_keys=False)

                # Collect test result for export
                self._export_test_results.append(result_data)

            except Exception as e:
                logger.error(f"Failed to write test result for {test_id}: {e}")
                # Even if writing fails, continue with status updates

            # Update agent status (shared state - must be protected)
            if agent_name in self.current_status["agents"]:
                agent_status = self.current_status["agents"][agent_name]
                agent_status["completed_tests"] += 1
                agent_status["current_test"] = None

                if result.success:
                    agent_status["passed_tests"] += 1
                    self.current_status["overall_stats"]["passed_tests"] += 1
                else:
                    agent_status["failed_tests"] += 1
                    self.current_status["overall_stats"]["failed_tests"] += 1

                self.current_status["overall_stats"]["completed_tests"] += 1

            # Write shared files (these use their own locks)
            self._write_status()
            self._write_summary()

    def _json_default(self, obj):
        """Custom JSON serializer for objects that aren't natively serializable."""
        from agent_platform.quality.models import Platform, Text, Thought, ToolUse

        if isinstance(obj, Text | Thought | ToolUse):
            return self._serialize_content(obj)
        elif isinstance(obj, Platform):
            return {"name": obj.name}
        elif hasattr(obj, "__dict__"):
            return str(obj)
        else:
            return str(obj)

    def _serialize_message(self, message):
        return {
            "role": message.role,
            "content": [self._serialize_content(content) for content in message.content],
        }

    def _serialize_thread(self, thread):
        if thread is None:
            return None

        return {
            "name": thread.name,
            "description": thread.description,
            "messages": [self._serialize_message(message) for message in thread.messages],
        }

    def _serialize_workitem(self, workitem):
        if workitem is None:
            return None

        return {
            "messages": [self._serialize_message(message) for message in workitem.messages],
            "payload": workitem.payload,
            "is_preview_only": workitem.is_preview_only,
        }

    def complete_agent_testing(self, agent_name: str, error: str | None = None):
        """Mark completion of all tests for an agent."""
        logger.info(f"Completing agent testing: {agent_name}")

        if agent_name in self.current_status["agents"]:
            agent_status = self.current_status["agents"][agent_name]
            agent_status["status"] = "failed" if error else "completed"
            agent_status["completed_at"] = datetime.now().isoformat()
            agent_status["current_test"] = None

            if error:
                agent_status["error"] = error

            self.current_status["overall_stats"]["completed_agents"] += 1

        self._write_status()
        self._write_summary()

    def complete_run(self, error: str | None = None):
        """Mark completion of the entire test run."""
        logger.info("Completing test run")

        self.current_status["status"] = "failed" if error else "completed"
        self.current_status["completed_at"] = datetime.now().isoformat()

        if error:
            self.current_status["error"] = error

        self._write_status()
        self._write_summary()

        # Write final run summary
        run_summary = {
            "run_id": self.current_run_id,
            "started_at": self.current_status["started_at"],
            "completed_at": datetime.now().isoformat(),
            "status": self.current_status["status"],
            "stats": self.current_status["overall_stats"],
            "agents": self.current_status["agents"],
            "error": error,
        }

        run_summary_file = self.current_run_dir / "summary.json"
        # Ensure the run directory exists
        self.current_run_dir.mkdir(parents=True, exist_ok=True)
        try:
            with open(run_summary_file, "w") as f:
                json.dump(run_summary, f, indent=2, default=self._json_default)
        except Exception as e:
            logger.error(f"Failed to write run summary: {e}")

        # Export results
        self._export_results()

    def get_results_dir(self) -> Path:
        """Get the results directory path."""
        return self.results_dir

    def get_current_run_dir(self) -> Path:
        """Get the current run directory path."""
        return self.current_run_dir

    def _serialize_content(self, content):
        """Serialize message content for JSON storage."""
        from agent_platform.quality.models import FileAttachment, Text, Thought, ToolUse

        if isinstance(content, Text):
            return {"type": "text", "data": {"text": content.content}}
        elif isinstance(content, Thought):
            return {"type": "thought", "data": {"thought": content.content}}
        elif isinstance(content, ToolUse):
            return {
                "type": "tool_use",
                "data": {
                    "tool_name": content.tool_name,
                    "started_at": content.started_at,
                    "ended_at": content.ended_at,
                    "output_as_string": content.output_as_string,
                    "input_as_string": content.input_as_string,
                    "error": content.error,
                },
            }
        elif isinstance(content, FileAttachment):
            return {
                "type": "attachment",
                "data": {
                    "file_name": content.file_name,
                    "description": content.description,
                    "mime_type": content.mime_type,
                },
            }
        else:
            match content:
                case {"type": "text", "text": text}:
                    return {"type": "text", "data": {"text": text}}
                case {"type": "tool_use", **data}:
                    return {"type": "tool_use", "data": data}
                case _:
                    return {"type": "unknown", "data": str(content)}

    def _write_all_agents(self, all_agents: list[AgentPackage]):
        """Write all discovered agents to agents.json for UI consumption."""
        agents_data = {
            "discovered_at": datetime.now().isoformat(),
            "run_id": self.current_run_id,
            "agents": [
                {
                    "name": agent.name,
                    "zip_path": str(agent.zip_path),
                    "path": str(agent.path),
                    "status": "pending",  # Default status before testing starts
                }
                for agent in all_agents
            ],
        }

        agents_file = self.results_dir / "agents.json"
        try:
            self.results_dir.mkdir(parents=True, exist_ok=True)
            with open(agents_file, "w") as f:
                json.dump(agents_data, f, indent=2, default=self._json_default)
            logger.info(f"Written {len(all_agents)} discovered agents to agents.json")
        except Exception as e:
            logger.error(f"Failed to write agents file: {e}")

    def _export_results(self):
        """Export results in stable JSON format for tracking over time."""
        from agent_platform.quality.export_results import (
            ExportResults,
            RunMetadata,
            TestResult,
            TestSummary,
            calculate_duration_seconds,
            export_to_json_file,
        )

        if self.export_results_path is None:
            return

        from agent_platform.quality.git_info import get_git_commit_sha

        try:
            logger.info("Exporting results to stable JSON format")

            # Use the provided output path (already resolved at CLI level)
            output_path = self.export_results_path

            # Get git commit SHA
            git_commit = get_git_commit_sha()

            # Calculate total duration
            started_at = self.current_status.get("started_at", datetime.now().isoformat())
            completed_at = self.current_status.get("completed_at", datetime.now().isoformat())
            duration_seconds = calculate_duration_seconds(started_at, completed_at) or 0.0

            # Build run metadata
            run_metadata = RunMetadata(
                run_id=self.current_run_id,
                command=self.command_args,
                started_at=started_at,
                completed_at=completed_at,
                git_commit=git_commit,
            )

            # Build summary
            stats = self.current_status["overall_stats"]
            # Calculate error count (tests that didn't pass or fail normally)
            error_count = stats["total_tests"] - stats["passed_tests"] - stats["failed_tests"]
            summary = TestSummary(
                total_tests=stats["total_tests"],
                passed=stats["passed_tests"],
                failed=stats["failed_tests"],
                error=max(0, error_count),  # Ensure non-negative
                duration_seconds=duration_seconds,
            )

            # Build test results
            test_results = []
            for test_data in self._export_test_results:
                # Determine status
                if test_data.get("success"):
                    status = "passed"
                elif test_data.get("error"):
                    status = "error"
                else:
                    status = "failed"

                # Calculate test duration
                test_duration = calculate_duration_seconds(
                    test_data.get("started_at", datetime.now().isoformat()),
                    test_data.get("completed_at", datetime.now().isoformat()),
                )

                test_result = TestResult(
                    name=test_data["test_name"],
                    platform=test_data["platform"],
                    agent_name=test_data["agent_name"],
                    status=status,
                    model_id=test_data.get("model_id"),
                    trial_id=test_data["trial_id"],
                    started_at=test_data.get("started_at"),
                    completed_at=test_data["completed_at"],
                    duration_seconds=test_duration,
                    error=test_data.get("error"),
                )
                test_results.append(test_result)

            # Create export data
            export_data = ExportResults(
                run_metadata=run_metadata,
                summary=summary,
                tests=test_results,
            )

            # Write to file
            export_to_json_file(export_data, output_path)

            logger.info(
                "Successfully exported results",
                output_path=str(output_path),
                total_tests=len(test_results),
            )

        except Exception as e:
            logger.error(f"Failed to export results: {e}", exc_info=True)
