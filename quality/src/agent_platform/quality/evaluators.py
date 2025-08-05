import json
import os
from typing import TYPE_CHECKING

import httpx
import structlog

from agent_platform.quality.models import WorkitemResult

if TYPE_CHECKING:
    from agent_platform.quality.models import Evaluation, Message, TestResult

logger = structlog.get_logger(__name__)

# Constants
CONTENT_PREVIEW_LENGTH = 500


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
        evaluation: "Evaluation",
        agent_messages: list["Message"],
        workitem: WorkitemResult | None,
    ) -> "TestResult":
        """Run a single evaluation against agent messages."""
        from agent_platform.quality.models import TestResult

        logger.debug("Running evaluation", kind=evaluation.kind, num_messages=len(agent_messages))

        try:
            if evaluation.kind == "count-messages-in-last-agent-turn":
                result = await self._evaluate_message_count(evaluation, agent_messages)
            elif evaluation.kind == "llm-eval-of-last-agent-turn":
                result = await self._evaluate_with_llm(evaluation, agent_messages)
            elif evaluation.kind == "tool-call-evaluation":
                result = await self._evaluate_tool_calls(evaluation, agent_messages)
            elif evaluation.kind == "workitem-result-evaluation":
                if workitem is None:
                    raise ValueError("Workitem is missing, cannot be evaluated")
                result = await self._evaluate_workitem_result(evaluation, workitem)
            else:
                return TestResult(
                    evaluation=evaluation,
                    passed=False,
                    actual_value=None,
                    error=f"Unknown evaluation kind: {evaluation.kind}",
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
        self, evaluation: "Evaluation", agent_messages: list["Message"]
    ) -> "TestResult":
        """Evaluate the count of messages in the last agent turn."""
        from agent_platform.quality.models import TestResult

        expected_count = evaluation.expected
        actual_count = len(agent_messages)

        return TestResult(
            evaluation=evaluation, passed=actual_count == expected_count, actual_value=actual_count
        )

    async def _evaluate_with_llm(
        self, evaluation: "Evaluation", agent_messages: list["Message"]
    ) -> "TestResult":
        """Evaluate using LLM via the server's /prompts/generate endpoint."""
        from agent_platform.quality.models import TestResult

        # Prepare the evaluation prompt
        agent_content = "\n\n".join(
            [f"Message {i + 1}: {msg.content}" for i, msg in enumerate(agent_messages)]
        )

        evaluation_prompt = f"""
Please evaluate the following agent response(s) against the given criteria.
Note that our agents have thoughts (visible to the user, but hidden by default; these
can be more verbose in nature) and tool calls (to carry out tasks). In a given agent
message the <test>...</text> is the agent's primary response.

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
                "You are an expert evaluator of AI agent responses. "
                "Provide accurate, objective evaluations."
            ),
            "messages": [
                {"role": "user", "content": [{"kind": "text", "text": evaluation_prompt}]}
            ],
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
                    "model": "gpt-4.1",  # You might want to make this configurable
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

    async def _evaluate_tool_calls(  # noqa: PLR0912 C901
        self, evaluation: "Evaluation", agent_messages: list["Message"]
    ) -> "TestResult":
        """Evaluate tool call usage in agent messages."""
        from agent_platform.quality.models import TestResult, ToolUse

        expected = evaluation.expected

        # Collect all tool calls from agent messages
        all_tool_calls = []
        for message in agent_messages:
            for content in message.content:
                if isinstance(content, ToolUse):
                    all_tool_calls.append(content)

        # Handle the new structured format
        if isinstance(expected, dict) and "calls" in expected:
            expected_calls = expected["calls"]

            # Ensure calls is a list
            if not isinstance(expected_calls, list):
                return TestResult(
                    evaluation=evaluation,
                    passed=False,
                    actual_value=None,
                    error="Expected calls must be a list",
                )

            results = []
            overall_passed = True

            for expected_call in expected_calls:
                # Extract expected call details
                expected_package = expected_call.get("package", "")
                expected_tool = expected_call.get("tool", "")
                is_required = expected_call.get("required", True)
                expected_args = expected_call.get("expected-args", {})

                # Find matching tool calls
                matching_calls = [
                    tool_call
                    for tool_call in all_tool_calls
                    if tool_call.tool_name == expected_tool
                ]

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
                                    if isinstance(expected_value, str) and isinstance(
                                        actual_value, str
                                    ):
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
                                "output": tool_call.output_as_string[:CONTENT_PREVIEW_LENGTH]
                                + "..."
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

        return TestResult(
            evaluation=evaluation,
            passed=False,
            actual_value=None,
            error=(
                "Invalid tool call evaluation format - expected 'calls' "
                "key with list of call specifications"
            ),
        )

    async def _evaluate_workitem_result(
        self, evaluation: "Evaluation", workitem: WorkitemResult
    ) -> "TestResult":
        from agent_platform.quality.models import TestResult

        expected = evaluation.expected

        return TestResult(
            evaluation=evaluation,
            passed=expected == workitem.status,
            actual_value=workitem.status,
            error="Invalid workitem result",
        )
