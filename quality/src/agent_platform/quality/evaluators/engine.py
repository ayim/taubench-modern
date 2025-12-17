from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any

import httpx
import structlog

from agent_platform.quality.models import WorkitemResult

if TYPE_CHECKING:
    from agent_platform.core.files.files import UploadedFile
    from agent_platform.core.thread.content.sql_generation import SQLGenerationContent
    from agent_platform.quality.models import (
        CountMessagesEvaluation,
        DataFrameGoldenComparisonEvaluation,
        Evaluation,
        LLMEvalEvaluation,
        Message,
        SQLGenerationResultEvaluation,
        SQLGoldenComparisonEvaluation,
        TestResult,
        ToolCallEvaluation,
        WorkitemResultEvaluation,
    )

logger = structlog.get_logger(__name__)

# Constants
CONTENT_PREVIEW_LENGTH = 500
SQL_GENERATION_OUTPUT_FILENAME = "output.json"


class EvaluatorEngine:
    """Engine for running evaluations on test results."""

    def __init__(self, server_url: str = "http://localhost:8000"):
        self.server_url = server_url
        self.client = httpx.AsyncClient(timeout=30.0)

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()

    async def evaluate(
        self,
        evaluation: Evaluation,
        agent_messages: list[Message],
        workitem: WorkitemResult | None,
        thread_files: list[UploadedFile],
        thread_id: str | None = None,
        test_directory: Any | None = None,
    ) -> TestResult:
        """Run a single evaluation against agent messages.

        Args:
            evaluation: The evaluation specification to run.
            agent_messages: Messages from the agent.
            workitem: Optional workitem result for workitem evaluations.
            thread_files: Optional list of UploadedFile objects from the thread.
            thread_id: Optional thread ID for evaluations that need it.
            test_directory: Optional test directory Path for filesystem-based evaluations.
        """
        from agent_platform.quality.models import (
            CountMessagesEvaluation,
            DataFrameGoldenComparisonEvaluation,
            LLMEvalEvaluation,
            SQLGenerationResultEvaluation,
            SQLGoldenComparisonEvaluation,
            TestResult,
            ToolCallEvaluation,
            WorkitemResultEvaluation,
        )

        logger.debug("Running evaluation", kind=evaluation.kind, num_messages=len(agent_messages))

        try:
            # Use isinstance to narrow the type for each evaluation kind
            if isinstance(evaluation, CountMessagesEvaluation):
                result = await self._evaluate_message_count(evaluation, agent_messages)
            elif isinstance(evaluation, LLMEvalEvaluation):
                result = await self._evaluate_with_llm(evaluation, agent_messages)
            elif isinstance(evaluation, ToolCallEvaluation):
                result = await self._evaluate_tool_calls(evaluation, agent_messages)
            elif isinstance(evaluation, SQLGenerationResultEvaluation):
                result = await self._evaluate_sql_generation_result(evaluation, thread_files)
            elif isinstance(evaluation, SQLGoldenComparisonEvaluation):
                result = await self._evaluate_sql_golden_comparison(evaluation, thread_files)
            elif isinstance(evaluation, DataFrameGoldenComparisonEvaluation):
                result = await self._evaluate_dataframe_golden_comparison(evaluation, thread_id, test_directory)
            elif isinstance(evaluation, WorkitemResultEvaluation):
                if workitem is None:
                    raise ValueError("Workitem is missing, cannot be evaluated")
                result = await self._evaluate_workitem_result(evaluation, workitem)
            else:
                return TestResult(
                    evaluation=evaluation,
                    passed=False,
                    actual_value=None,
                    error=f"Unknown evaluation type: {type(evaluation)}",
                )

            logger.info(
                "Evaluation completed",
                kind=evaluation.kind,
                passed=result.passed,
                actual=result.actual_value,
            )
            return result

        except Exception as e:
            logger.error("Evaluation failed", kind=evaluation.kind, error=str(e))
            return TestResult(evaluation=evaluation, passed=False, actual_value=None, error=str(e))

    async def _evaluate_message_count(
        self, evaluation: CountMessagesEvaluation, agent_messages: list[Message]
    ) -> TestResult:
        """Evaluate the count of messages in the last agent turn."""
        from agent_platform.quality.models import TestResult

        expected_count = evaluation.expected
        actual_count = len(agent_messages)

        return TestResult(evaluation=evaluation, passed=actual_count == expected_count, actual_value=actual_count)

    async def _evaluate_with_llm(self, evaluation: LLMEvalEvaluation, agent_messages: list[Message]) -> TestResult:
        """Evaluate using LLM via the server's /prompts/generate endpoint."""
        from agent_platform.quality.models import TestResult

        # Prepare the evaluation prompt
        agent_content = "\n\n".join([f"Message {i + 1}: {msg.content}" for i, msg in enumerate(agent_messages)])

        evaluation_prompt = f"""
Please evaluate the following agent response(s) against the given criteria.
Note that our agents have thoughts (visible to the user, but hidden by default; these
can be more verbose in nature) and tool calls (to carry out tasks). In a given agent
message the <text>...</text> is the agent's primary response.

CRITERIA:
{evaluation.expected}

AGENT RESPONSE(S):
{agent_content}

Please respond with a JSON object containing (in this order):
- "explanation": a brief explanation of your thoughts/evaluation
- "score": a number from 0-10 indicating quality (10 = perfect match)
- "passed": true/false indicating if the response meets the criteria (score >= 6)

Only respond with the JSON object, no other text.
"""

        # Build the prompt for the server API
        prompt_data = {
            "system_instruction": (
                "You are an expert evaluator of AI agent responses. Provide accurate, objective evaluations."
            ),
            "messages": [{"role": "user", "content": [{"kind": "text", "text": evaluation_prompt}]}],
            "temperature": 0.1,
            "max_output_tokens": 500,
        }

        # Platform config for OpenAI (you might want to make this configurable)
        platform_config = {
            "kind": "openai",
            "openai_api_key": os.environ["OPENAI_API_KEY"],
        }

        try:
            # Call the server's prompt endpoint
            response = await self.client.post(
                f"{self.server_url}/api/v2/prompts/generate",
                json={
                    "prompt": prompt_data,
                    "platform_config_raw": platform_config,
                    "model": "gpt-5-low",  # You might want to make this configurable
                },
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()

            llm_response = response.json()

            # Extract the content from the LLM response
            content_text = ""
            for content in llm_response.get("content", []):
                if content.get("kind") == "text":
                    content_text += content.get("text", "")

            # Try to parse the JSON response from the LLM
            try:
                eval_result = json.loads(content_text.strip())
                passed = eval_result.get("passed", False)
                explanation = eval_result.get("explanation", "No explanation provided")
                score = eval_result.get("score", 0)

                return TestResult(
                    evaluation=evaluation,
                    passed=passed,
                    actual_value={
                        "passed": passed,
                        "explanation": explanation,
                        "score": score,
                        "llm_response": content_text,
                    },
                )
            except json.JSONDecodeError:
                # Fallback: look for true/false keywords in the response
                content_lower = content_text.lower()
                passed = "true" in content_lower and "false" not in content_lower

                return TestResult(
                    evaluation=evaluation,
                    passed=passed,
                    actual_value={
                        "passed": passed,
                        "explanation": "Parsed from text response",
                        "llm_response": content_text,
                    },
                )

        except Exception as e:
            logger.error("LLM evaluation failed", error=str(e))
            return TestResult(
                evaluation=evaluation,
                passed=False,
                actual_value=None,
                error=f"LLM evaluation failed: {e!s}",
            )

    async def _evaluate_tool_calls(self, evaluation: ToolCallEvaluation, agent_messages: list[Message]) -> TestResult:
        """Evaluate tool call usage in agent messages."""
        from agent_platform.quality.models import TestResult, ToolUse

        expected = evaluation.expected

        # Collect all tool calls from agent messages
        all_tool_calls = []
        for message in agent_messages:
            for content in message.content:
                if isinstance(content, ToolUse):
                    all_tool_calls.append(content)

        # Get expected calls from the typed model
        expected_calls = expected.calls

        results = []
        overall_passed = True

        for expected_call in expected_calls:
            # Extract expected call details
            expected_package = expected_call.get("package", "")
            expected_tool = expected_call.get("tool", "")
            is_required = expected_call.get("required", True)
            expected_args = expected_call.get("expected-args", {})

            # Find matching tool calls
            matching_calls = [tool_call for tool_call in all_tool_calls if tool_call.tool_name == expected_tool]

            call_found = len(matching_calls) > 0
            args_match = True

            # If tool call found, check arguments
            if call_found and expected_args:
                args_match = False
                for tool_call in matching_calls:
                    try:
                        tool_input = json.loads(tool_call.input_as_string)
                        call_args_match = True

                        for key, expected_value in expected_args.items():
                            if key not in tool_input:
                                call_args_match = False
                                break

                            # Check value if specified
                            if expected_value is not None:
                                actual_value = tool_input[key]
                                if isinstance(expected_value, str) and isinstance(actual_value, str):
                                    # Case-insensitive string comparison
                                    if expected_value.lower() != actual_value.lower():
                                        call_args_match = False
                                        break
                                elif expected_value != actual_value:
                                    call_args_match = False
                                    break

                        if call_args_match:
                            args_match = True
                            break

                    except json.JSONDecodeError:
                        # Skip tool calls with malformed JSON
                        continue

            # Determine if this expected call passed
            call_passed = call_found and args_match

            # If this is a required call and it didn't pass, overall evaluation fails
            if is_required and not call_passed:
                overall_passed = False

            results.append(
                {
                    "expected_package": expected_package,
                    "expected_tool": expected_tool,
                    "required": is_required,
                    "call_found": call_found,
                    "args_match": args_match,
                    "passed": call_passed,
                    "expected_args": expected_args,
                    "matching_calls": [
                        {
                            "tool_name": tool_call.tool_name,
                            "input": tool_call.input_as_string,
                            "output": tool_call.output_as_string[:CONTENT_PREVIEW_LENGTH] + "..."
                            if len(tool_call.output_as_string) > CONTENT_PREVIEW_LENGTH
                            else tool_call.output_as_string,
                        }
                        for tool_call in matching_calls
                    ],
                }
            )

        return TestResult(
            evaluation=evaluation,
            passed=overall_passed,
            actual_value={
                "call_results": results,
                "all_tool_calls": [
                    {
                        "tool_name": tool_call.tool_name,
                        "input": tool_call.input_as_string,
                        "output": tool_call.output_as_string[:CONTENT_PREVIEW_LENGTH] + "..."
                        if len(tool_call.output_as_string) > CONTENT_PREVIEW_LENGTH
                        else tool_call.output_as_string,
                    }
                    for tool_call in all_tool_calls
                ],
            },
        )

    async def _evaluate_workitem_result(
        self, evaluation: WorkitemResultEvaluation, workitem: WorkitemResult
    ) -> TestResult:
        from agent_platform.quality.models import TestResult

        expected = evaluation.expected
        passed = expected == workitem.status
        error = f"Invalid workitem result: {workitem.status}" if not passed else None

        return TestResult(
            evaluation=evaluation,
            passed=passed,
            actual_value=workitem.status,
            error=error,
        )

    async def _find_sql_generation_output(self, thread_files: list[UploadedFile]) -> SQLGenerationContent | None:
        """Find and parse the SQL generation output.json from thread files.

        The SQL subagent uploads a file named 'output.json' containing a
        SQLGenerationContent model when it finalizes. This method searches
        for that file in the thread files and fetches/parses its content.

        Args:
            thread_files: List of UploadedFile objects from the thread.

        Returns:
            Parsed SQLGenerationContent object, or None if not found.
        """
        if not thread_files:
            return None

        # Search for output.json file in thread files
        for file in thread_files:
            # Look for file with the expected filename
            if file.file_ref != SQL_GENERATION_OUTPUT_FILENAME:
                continue

            if file.thread_id is None:
                logger.warning(
                    "File has no thread ID",
                    file_ref=file.file_ref,
                )
                continue

            # Found the output.json file - fetch its content
            try:
                return await self._fetch_and_parse_json_file(file.thread_id, file.file_ref)
            except Exception as e:
                logger.warning(
                    "Failed to fetch SQL generation output",
                    file_id=file.file_id,
                    error=str(e),
                )
                return None

        return None

    async def _fetch_and_parse_json_file(self, thread_id: str, file_ref: str) -> SQLGenerationContent | None:
        """Fetch a JSON file by file_id and parse it.

        Args:
            thread_id: The thread ID to fetch the file from.
            file_ref: The file reference to fetch.

        Returns:
            Parsed SQLGenerationContent object, or None on failure.
        """
        from agent_platform.core.thread.content.sql_generation import SQLGenerationContent

        # Fetch file content from agent server
        download_url = f"{self.server_url}/api/v2/threads/{thread_id}/files/download/?file_ref={file_ref}"
        response = await self.client.get(download_url)
        response.raise_for_status()

        return SQLGenerationContent.model_validate(response.json())

    async def _evaluate_sql_generation_result(
        self, evaluation: SQLGenerationResultEvaluation, thread_files: list[UploadedFile]
    ) -> TestResult:
        """Evaluate SQL generation subagent results.

        The SQL subagent finalizes by uploading an output.json file to the thread
        containing a SQLGenerationContent model. This evaluator fetches that file
        and validates its contents against the expected criteria.
        """
        from agent_platform.core.thread.content.sql_generation import SQLGenerationStatus
        from agent_platform.quality.models import TestResult

        expected = evaluation.expected

        # Find SQL generation output.json in thread files
        sql_gen_content = await self._find_sql_generation_output(thread_files)

        if sql_gen_content is None:
            return TestResult(
                evaluation=evaluation,
                passed=False,
                actual_value=None,
                error=f"No {SQL_GENERATION_OUTPUT_FILENAME} found in thread attachments",
            )

        # Perform checks based on expected criteria
        checks: list[bool] = []
        failures: list[str] = []

        # Check status
        if expected.status is not None:
            expected_status = SQLGenerationStatus(expected.status)
            actual_status = sql_gen_content.status
            if actual_status == expected_status:
                checks.append(True)
            else:
                checks.append(False)
                failures.append(f"Status mismatch: expected={expected_status}, actual={actual_status}")

        # Check for logical SQL presence
        if expected.has_sql is not None:
            sql = sql_gen_content.sql_query
            has_sql = sql is not None and sql != ""
            if has_sql == expected.has_sql:
                checks.append(True)
            else:
                checks.append(False)
                failures.append(f"Logical SQL presence mismatch: expected={expected.has_sql}, actual={has_sql}")

        # Check for patterns in SQL
        if expected.sql_contains is not None:
            sql = (sql_gen_content.sql_query or "").lower()
            for pattern in expected.sql_contains:
                if pattern.lower() in sql:
                    checks.append(True)
                else:
                    checks.append(False)
                    failures.append(f"SQL missing expected pattern: '{pattern}'")

        # Check for absence of patterns in logical SQL
        if expected.sql_not_contains is not None:
            sql = (sql_gen_content.sql_query or "").lower()
            for pattern in expected.sql_not_contains:
                if pattern.lower() not in sql:
                    checks.append(True)
                else:
                    checks.append(False)
                    failures.append(f"SQL contains unexpected pattern: '{pattern}'")

        # Check for assumptions
        if expected.has_assumptions is not None:
            assumptions = sql_gen_content.assumptions_used
            has_assumptions = assumptions is not None and assumptions != ""
            if has_assumptions == expected.has_assumptions:
                checks.append(True)
            else:
                checks.append(False)
                failures.append(
                    f"Assumptions presence mismatch: expected={expected.has_assumptions}, actual={has_assumptions}"
                )

        passed = all(checks) if checks else False

        return TestResult(
            evaluation=evaluation,
            passed=passed,
            actual_value={
                "status": sql_gen_content.status,
                "sql": sql_gen_content.sql_query,
                "assumptions": sql_gen_content.assumptions_used,
                "message_to_parent": sql_gen_content.message_to_parent,
                "error_message": sql_gen_content.error_message,
            },
            error="; ".join(failures) if failures else None,
        )

    async def _evaluate_sql_golden_comparison(
        self, evaluation: SQLGoldenComparisonEvaluation, thread_files: list[UploadedFile]
    ) -> TestResult:
        """Compare generated SQL against golden (expected) SQL using an LLM."""
        from agent_platform.quality.models import TestResult

        expected = evaluation.expected
        golden_sql = expected.golden_sql

        # Find SQL generation output.json in thread files
        sql_gen_content = await self._find_sql_generation_output(thread_files)

        if sql_gen_content is None:
            return TestResult(
                evaluation=evaluation,
                passed=False,
                actual_value=None,
                error=f"No {SQL_GENERATION_OUTPUT_FILENAME} found in thread attachments",
            )

        if not sql_gen_content.sql_query:
            return TestResult(
                evaluation=evaluation,
                passed=False,
                actual_value={"actual_sql": None, "golden_sql": golden_sql},
                error="No SQL query found in output.json",
            )

        passed, explanation = await self._compare_sql_semantically(sql_gen_content.sql_query, golden_sql)

        return TestResult(
            evaluation=evaluation,
            passed=passed,
            actual_value={
                "actual_sql": sql_gen_content.sql_query,
                "golden_sql": golden_sql,
                "explanation": explanation,
            },
            error=None if passed else explanation,
        )

    async def _compare_sql_semantically(self, actual_sql: str, golden_sql: str) -> tuple[bool, str]:
        """Use LLM to compare two SQL queries for semantic equivalence.

        Args:
            actual_sql: The generated SQL query.
            golden_sql: The expected golden SQL query.

        Returns:
            Tuple of (passed, explanation).
        """
        comparison_prompt = f"""
Compare these two SQL queries for semantic equivalence.
Two queries are semantically equivalent if they would produce the same result set
(ignoring column order and aliases).

ACTUAL SQL:
```sql
{actual_sql}
```

GOLDEN SQL:
```sql
{golden_sql}
```

Consider:
- Do they query the same tables?
- Do they apply the same filters/conditions?
- Do they return the same columns (ignoring aliases)?
- Do they have the same grouping, ordering, and limits?

IMPORTANT: The ACTUAL SQL may include defensive additions that don't change the
logical result. These should be considered EQUIVALENT:
- Adding `WHERE column IS NOT NULL` before aggregations (SUM/AVG/COUNT ignore NULLs anyway)
- Adding explicit NULL checks that match implicit SQL behavior
- Using COALESCE or IFNULL with default values that match NULL handling
- More explicit column qualifications (table.column vs just column)
- Defensive type casts that don't change the result

The ACTUAL query is considered equivalent if it produces the same meaningful result
as the GOLDEN query, even if it's more defensive or explicit.

Respond with a JSON object:
{{
    "equivalent": true/false,
    "explanation": "Brief explanation of why they are or aren't equivalent"
}}
"""

        prompt_data = {
            "system_instruction": (
                "You are an expert SQL analyst. Compare SQL queries for semantic equivalence. "
                "Be precise and thorough in your analysis."
            ),
            "messages": [{"role": "user", "content": [{"kind": "text", "text": comparison_prompt}]}],
            "temperature": 0.1,
            "max_output_tokens": 500,
        }

        platform_config = {
            "kind": "openai",
            "openai_api_key": os.environ.get("OPENAI_API_KEY", ""),
        }

        try:
            response = await self.client.post(
                f"{self.server_url}/api/v2/prompts/generate",
                json={
                    "prompt": prompt_data,
                    "platform_config_raw": platform_config,
                    "model": "gpt-5-low",
                },
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()

            llm_response = response.json()
            content_text = ""
            for content in llm_response.get("content", []):
                if content.get("kind") == "text":
                    content_text += content.get("text", "")

            result = json.loads(content_text.strip())
            passed = result.get("equivalent", False)
            explanation = result.get("explanation", "No explanation provided")
            return passed, explanation

        except Exception as e:
            logger.error("Semantic SQL comparison failed", error=str(e))
            return False, f"Semantic comparison failed: {e!s}"

    async def _evaluate_dataframe_golden_comparison(
        self,
        evaluation: DataFrameGoldenComparisonEvaluation,
        thread_id: str | None,
        test_directory: Any | None,
    ) -> TestResult:
        """Compare agent-produced dataframes against a golden dataset.

        Delegates to DataFrameGoldenComparisonEvaluator for implementation.
        """
        from agent_platform.quality.evaluators.dataframe import DataFrameGoldenComparisonEvaluator

        evaluator = DataFrameGoldenComparisonEvaluator(
            evaluation=evaluation,
            client=self.client,
            server_url=self.server_url,
        )
        return await evaluator.evaluate(thread_id=thread_id, test_directory=test_directory)
