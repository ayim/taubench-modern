from dataclasses import dataclass, field
from typing import Annotated

import pytest

from agent_platform.core.prompts import (
    AnyPromptMessage,
    Prompt,
    PromptAgentMessage,
    PromptUserMessage,
)
from agent_platform.core.prompts.content import (
    PromptTextContent,
)
from agent_platform.core.responses.content import (
    ResponseTextContent,
    ResponseToolUseContent,
)
from agent_platform.core.responses.response import ResponseMessage
from agent_platform.core.tools import ToolDefinition


@dataclass
class _Book:
    title: Annotated[str, "The title of the book"]
    author: Annotated[str, "The author's name"]
    category: Annotated[str | None, "The category of the book"]
    # Showing example of using field(metadata={"description": ...})
    year: int = field(metadata={"description": "Year the book was published"})


async def _add_book(book: Annotated[_Book, "The book to add to the database"]):
    """Store a new book in the database."""
    return {"status": "success", "title": book.title}


async def _confirm_request():
    """Confirm the request, takes no arguments."""
    return {"status": "confirmed"}


def compare_responses(
    given_response: ResponseMessage,
    expected_response: ResponseMessage,
):
    """
    Compare two responses.
    """
    from json import dumps

    # We need to "align" the given response with the expected response
    # by adding wildcards to the given response where necessary
    for idx in range(len(expected_response.content)):
        if isinstance(expected_response.content[idx], ResponseTextContent):
            if idx >= len(given_response.content):
                given_response.content.append(ResponseTextContent(text="*"))
            elif not isinstance(given_response.content[idx], ResponseTextContent):
                given_response.content.insert(idx, ResponseTextContent(text="*"))

    assert given_response.role == expected_response.role
    assert len(given_response.content) == len(expected_response.content)

    for given_content, expected_content in zip(
        given_response.content,
        expected_response.content,
        strict=True,
    ):
        # Tool calls need more care in comparison
        if isinstance(given_content, ResponseToolUseContent):
            assert isinstance(expected_content, ResponseToolUseContent)
            # Do NOT check tool_call_id because it's not always the same
            assert given_content.tool_name == expected_content.tool_name
            # Check tool_input instead of tool_input_raw to avoid minor
            # differences in formatting
            expected_input = expected_content.tool_input
            given_input = given_content.tool_input
            # Ignore the tool_call_id field as it's not deterministic
            expected_input.pop("tool_call_id", None)
            given_input.pop("tool_call_id", None)
            # Now deep compare the rest of the tool_input
            assert dumps(
                given_input,
                sort_keys=True,
            ) == dumps(
                expected_input,
                sort_keys=True,
            )
            continue
        elif isinstance(given_content, ResponseTextContent):
            assert isinstance(expected_content, ResponseTextContent)
            if expected_content.text.strip() == "*":
                continue
            else:
                assert given_content.text.strip() == expected_content.text.strip()

        # Default processing
        assert given_content.model_dump() == expected_content.model_dump()


@pytest.fixture
def basic_prompt_no_tools():
    """
    A basic prompt with no tools. This is the most basic
    "does it work" test.
    """
    messages: list[AnyPromptMessage] = [
        PromptUserMessage(
            content=[
                PromptTextContent(
                    text="""
                This is an end-to-end test, please respond with a
                message containing only the word 'sunflower'
                """,
                ),
            ],
        ),
    ]
    return Prompt(
        messages=messages,
        tools=[],
        temperature=0.0,
        max_output_tokens=512,
    )


@pytest.fixture
def response_to_basic_prompt_no_tools():
    """
    A response to the basic prompt with no tools.
    """
    return ResponseMessage(
        role="agent",
        content=[
            ResponseTextContent(text="sunflower"),
        ],
    )


@pytest.fixture
def basic_prompt_with_system_message():
    """
    A basic prompt with a system instruction. (To test
    whether we effectively translate the system instruction
    across varius model platforms.)
    """
    messages: list[AnyPromptMessage] = [
        PromptUserMessage(
            content=[
                PromptTextContent(
                    """
                This is an end-to-end test, please respond with a
                message containing only the word 'apple'
                """,
                ),
            ],
        ),
    ]
    return Prompt(
        system_instruction=(
            """
            Always provide your response wrapped in <response> tags.
            """
        ),
        messages=messages,
        tools=[],
        temperature=0.0,
        max_output_tokens=512,
    )


@pytest.fixture
def response_to_basic_prompt_with_system_message():
    """
    A response to the basic prompt with a system instruction.
    """
    return ResponseMessage(
        role="agent",
        content=[
            ResponseTextContent(text="<response>apple</response>"),
        ],
    )


@pytest.fixture
def basic_prompt_with_three_messages():
    """
    A basic prompt with three messages. (To ensure
    that the system can handle user -> agent -> user
    interactions.)
    """
    messages: list[AnyPromptMessage] = [
        PromptUserMessage(
            content=[
                PromptTextContent(
                    """
                You are acting as an agent named 'Test Agent'. You
                are to assist the user with their request.
                """,
                ),
            ],
        ),
        PromptAgentMessage(
            content=[
                PromptTextContent(
                    """
                Understood, I will assist the user with their request.
                """,
                ),
            ],
        ),
        PromptUserMessage(
            content=[
                PromptTextContent(
                    """
                Reply with the answer only, nothing else. What is the
                capital of the state of Wisconsin, USA?

                The answer must be one word. Starting with a capital
                letter, and ending with a period. Emit nothing else
                aside from the capital of Wisconsin with a period
                at the end and starting with a capital letter.

                NOTE: We are not looking for ALL CAPS. Just regular
                capitalization with a period at the end.
                """,
                ),
            ],
        ),
    ]
    return Prompt(
        messages=messages,
        tools=[],
        temperature=0.0,
        max_output_tokens=512,
    )


@pytest.fixture
def response_to_basic_prompt_with_three_messages():
    """
    A response to the basic prompt with three messages.
    """
    return ResponseMessage(
        role="agent",
        content=[
            ResponseTextContent(text="Madison."),
        ],
    )


@pytest.fixture
def basic_prompt_with_one_tool():
    """
    A basic prompt with one tool.
    """
    messages: list[AnyPromptMessage] = [
        PromptUserMessage(
            content=[
                PromptTextContent(
                    """
                This is an end-to-end test, please call the tool
                called add_book with the following book:

                Title: "Foundation"
                Author: "Isaac Asimov"
                Year: 1951

                Emit nothing else but the tool call with the
                book information _exactly_ as shown above. Completely
                omit any optional fields.
                """,
                ),
            ],
        ),
    ]

    return Prompt(
        system_instruction=(
            """
            You are an expert librarian. You are given a book
            and you need to add it to the database. If any
            information is missing/optional, you should leave
            it out instead of trying to guess it!! Do NOT even
            include an empty string/null for optional fields, completely
            omit them.
            """
        ),
        messages=messages,
        tools=[ToolDefinition.from_callable(_add_book)],
        temperature=0.0,
        max_output_tokens=512,
    )


@pytest.fixture
def response_to_basic_prompt_with_one_tool():
    """
    A response to the basic prompt with one tool.
    """
    from json import dumps

    expected_tool_input = {
        "book": {
            "title": "Foundation",
            "author": "Isaac Asimov",
            "year": 1951,
        },
    }

    return ResponseMessage(
        role="agent",
        content=[
            # Claude LOVES to start with some text before
            # emitting the tool call, despite instructions...
            # So we'll allow arbitrary text content prior to the
            # tool call.
            ResponseTextContent(text="*"),
            ResponseToolUseContent(
                tool_call_id="DO-NOT-COMPARE",
                tool_name="_add_book",
                tool_input_raw=dumps(expected_tool_input),
            ),
        ],
    )


@pytest.fixture
def basic_prompt_tool_no_args():
    """
    A basic prompt with a tool that takes no arguments.
    """
    messages: list[AnyPromptMessage] = [
        PromptUserMessage(
            content=[
                PromptTextContent(
                    """
                You are a helpful assistant. You are acting
                as an agent named 'Test Agent'. You will do
                your best to assist the user with their request.
                """,
                ),
            ],
        ),
        PromptAgentMessage(
            content=[
                PromptTextContent(
                    """
                Understood, I will assist the user with their request.
                """,
                ),
            ],
        ),
        PromptUserMessage(
            content=[
                PromptTextContent(
                    """
                Please confirm the request using the provided
                tool.
                """,
                ),
            ],
        ),
    ]
    return Prompt(
        messages=messages,
        tools=[
            ToolDefinition.from_callable(_add_book),  # distrctor tool
            ToolDefinition.from_callable(_confirm_request),
        ],
        temperature=0.0,
        max_output_tokens=512,
    )


@pytest.fixture
def response_to_basic_prompt_tool_no_args():
    """
    A response to the basic prompt with a tool that takes no arguments.
    """
    return ResponseMessage(
        role="agent",
        content=[
            # Claude LOVES to start with some text before
            # emitting the tool call, despite instructions...
            # So we'll allow arbitrary text content prior to the
            # tool call.
            ResponseTextContent(text="*"),
            ResponseToolUseContent(
                tool_call_id="DO-NOT-COMPARE",
                tool_name="_confirm_request",
                tool_input_raw="{}",
            ),
        ],
    )
