"""Query verification logic for SQL generation.

This module provides functionality to verify that generated SQL queries match
the user's intent by comparing actual query results against LLM-predicted expectations.
"""

from typing import TYPE_CHECKING

from structlog import get_logger

from agent_platform.server.kernel.sql_gen.types import Column, Result, Shape

if TYPE_CHECKING:
    from agent_platform.core.data_frames.data_frames import PlatformDataFrame
    from agent_platform.core.kernel import Kernel

logger = get_logger(__name__)


def extract_actual_shape(data_frame: "PlatformDataFrame") -> Result:
    """Extract the actual shape (columns with types and row count) from a dataframe.

    Args:
        data_frame: The PlatformDataFrame to extract shape from

    Returns:
        A Result with columns and row_count.
    """
    columns = [Column(name=name, type=type_str) for name, type_str in data_frame.columns.items()]
    return Result(columns=columns, row_count=data_frame.num_rows)


async def predict_expected_shape(
    kernel: "Kernel",
    query_intent: str,
    sdm_context: str,
    max_attempts: int = 3,
) -> Shape:
    """Use an LLM to predict the expected shape based on query intent and SDM context.

    Args:
        kernel: The kernel to use for LLM access
        query_intent: The natural language query intent
        sdm_context: The semantic data model context (table schemas, etc.)
        max_attempts: Maximum number of attempts to parse the LLM response

    Returns:
        A Shape with expected_columns and row_cardinality.

    Raises:
        ValueError: If the LLM response cannot be parsed after max_attempts.
    """
    from agent_platform.core.prompts import Prompt, PromptTextContent, PromptUserMessage
    from agent_platform.core.prompts.messages import PromptAgentMessage
    from agent_platform.core.responses.content import ResponseTextContent

    system_instruction = (
        "You are analyzing a SQL query intent to predict what shape "
        "(columns and row count) would best answer the question.\n\n"
        "Given the query intent and available data model, predict:\n"
        "1. What columns should be returned (name, type, and purpose)\n"
        "2. Whether the result should be one row or many rows\n\n"
        "Respond with valid JSON only, no other text:\n"
        "{\n"
        '    "expected_columns": [\n'
        '        {"name": "column_name", "type": "numeric|string|boolean|datetime"}\n'
        "    ],\n"
        '    "row_cardinality": "one_row|many_rows",\n'
        "}\n\n"
        "Guidelines:\n"
        '- Use "one_row" for aggregations (total, average, count, sum, max, min)\n'
        '- Use "many_rows" for listings, details, or multiple records\n'
        "- The ordering of columns is not important\n"
        "- Column types should match the semantic categories: numeric, string, boolean, datetime\n"
        "- Do not include columns in the select that were not explicitly requested by the user's intent\n"
        "- It is critical to only return columns specifically requested by the user's intent\n"
        "- Only include columns that form part of the final answer itself, not columns used for comparison, \n"
        "  filtering, or sorting. The SELECT clause should return the minimum information needed to answer\n"
        "  the question asked.\n"
        "- A DISTINCT clause should only be included if the intent explicitly asks for unique values."
    )

    initial_user_message = (
        f"Query Intent: {query_intent}\n\n"
        f"Available Data Model:\n{sdm_context}\n\n"
        "Predict the expected shape (columns and row cardinality) that would best answer this query."
    )

    messages: list[PromptUserMessage | PromptAgentMessage] = [
        PromptUserMessage(content=[PromptTextContent(text=initial_user_message)])
    ]

    # Get platform and model
    platform, model = await kernel.get_platform_and_model(model_type="llm")

    last_error: Exception | None = None
    for attempt in range(max_attempts):
        prompt = Prompt(
            system_instruction=system_instruction,
            messages=list(messages),
            temperature=0.2,
            max_output_tokens=4096,
        )

        # Generate response
        response = await platform.generate_response(prompt, model)

        logger.info("predict_expected_shape response", response=response, attempt=attempt + 1)

        # Extract text from response
        response_text = ""
        for content in response.content:
            if isinstance(content, ResponseTextContent):
                response_text += content.text

        # Parse JSON response
        try:
            expected_shape = Shape.model_validate_json(response_text)
            logger.info("predict_expected_shape parsed shape", expected_shape=expected_shape)
            return expected_shape
        except Exception as e:
            last_error = e
            logger.warning(
                "Failed to parse expected query shape JSON from LLM",
                response_text=response_text,
                attempt=attempt + 1,
                error=str(e),
            )

            if attempt < max_attempts - 1:
                # Append the failed response and error feedback for retry
                messages.append(PromptAgentMessage(content=[PromptTextContent(text=response_text)]))
                messages.append(
                    PromptUserMessage(
                        content=[
                            PromptTextContent(
                                text=f"Failed to parse your response as valid JSON: {e}\n\n"
                                "Please respond with valid JSON only, no other text."
                            )
                        ]
                    )
                )

    raise ValueError(f"Failed to parse LLM response as Shape after {max_attempts} attempts: {last_error}")


async def generate_feedback(
    kernel: "Kernel",
    query_intent: str,
    actual_shape: Result,
    expected_shape: Shape,
    max_attempts: int = 3,
) -> list[str]:
    """Use an LLM to compare actual vs expected shape and generate actionable feedback.

    Args:
        kernel: The kernel to use for LLM access
        query_intent: The natural language query intent
        actual_shape: The actual shape from the dataframe
        expected_shape: The expected shape from LLM prediction
        max_attempts: Maximum number of attempts to parse the LLM response

    Returns:
        A list of feedback strings. Empty list if shapes match.

    Raises:
        ValueError: If the LLM response cannot be parsed after max_attempts.
    """
    from agent_platform.core.prompts import Prompt, PromptTextContent, PromptUserMessage
    from agent_platform.core.prompts.messages import PromptAgentMessage
    from agent_platform.core.responses.content import ResponseTextContent
    from agent_platform.server.kernel.sql_gen.types import Feedback

    system_instruction = (
        "You are comparing the actual SQL query results against what was expected "
        "based on the user's intent.\n\n"
        "Your job is to generate actionable feedback for improving the SQL query. "
        "Compare the actual and expected shapes and identify any issues.\n\n"
        "Respond with valid JSON only, no other text:\n"
        "{\n"
        '    "feedback": [\n'
        '        "Specific actionable feedback item 1",\n'
        '        "Specific actionable feedback item 2"\n'
        "    ]\n"
        "}\n\n"
        "Guidelines:\n"
        "- Return an empty feedback array [] if the shapes match well enough\n"
        '- Be specific about what needs to change (e.g., "add column X", '
        '"remove column Y", "aggregate to one row")\n'
        "- The ordering of columns is not important\n"
        "- The names of columns are not important, never recommend changing column names\n"
        "- Focus on semantic mismatches (not just exact type matching)\n"
        "- You should suggest removal of any columns in the select which were not identified by the expected shape\n"
        "- Columns that are necessary to filter should not be returned unless the user explicitly asked for them\n"
        "- Each feedback item should be actionable for an AI agent to fix the SQL query\n"
        "- Numeric precision is an important factor when comparing numeric columns\n\n"
    )

    actual_json = actual_shape.model_dump_json(indent=2)
    expected_json = expected_shape.model_dump_json(indent=2)

    initial_user_message = (
        f"Query Intent: {query_intent}\n\n"
        f"Actual Query Results:\n```json\n{actual_json}\n```\n\n"
        f"Expected Shape:\n```json\n{expected_json}\n```\n\n"
        "Compare these shapes and generate actionable feedback for improving the SQL query "
        "to better match the intent. If they match well enough, return an empty feedback array."
    )

    messages: list[PromptUserMessage | PromptAgentMessage] = [
        PromptUserMessage(content=[PromptTextContent(text=initial_user_message)])
    ]

    # Get platform and model
    platform, model = await kernel.get_platform_and_model(model_type="llm")

    last_error: Exception | None = None
    for attempt in range(max_attempts):
        prompt = Prompt(
            system_instruction=system_instruction,
            messages=list(messages),
            temperature=0.3,
            max_output_tokens=4096,
        )

        # Generate response
        response = await platform.generate_response(prompt, model)

        # Extract text from response
        response_text = ""
        for content in response.content:
            if isinstance(content, ResponseTextContent):
                response_text += content.text

        # Parse JSON response
        try:
            feedback_result = Feedback.model_validate_json(response_text)
            return feedback_result.feedback
        except Exception as e:
            last_error = e
            logger.warning(
                "Failed to parse SQL generation feedback JSON from LLM",
                response_text=response_text,
                attempt=attempt + 1,
                error=str(e),
            )

            if attempt < max_attempts - 1:
                # Append the failed response and error feedback for retry
                messages.append(PromptAgentMessage(content=[PromptTextContent(text=response_text)]))
                messages.append(
                    PromptUserMessage(
                        content=[
                            PromptTextContent(
                                text=f"Failed to parse your response as valid JSON: {e}\n\n"
                                "Please respond with valid JSON only, no other text."
                            )
                        ]
                    )
                )

    raise ValueError(f"Failed to parse LLM response as Feedback after {max_attempts} attempts: {last_error}")
