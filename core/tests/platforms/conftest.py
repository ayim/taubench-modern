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
from agent_platform.core.prompts.content.image import PromptImageContent
from agent_platform.core.responses.content import (
    ResponseReasoningContent,
    ResponseTextContent,
    ResponseToolUseContent,
)
from agent_platform.core.responses.response import ResponseMessage
from agent_platform.core.tools import ToolDefinition


@dataclass
class _Book:
    title: Annotated[str, "The title of the book"]
    author: Annotated[str, "The author's name"]
    # Showing example of using field(metadata={"description": ...})
    year: int = field(metadata={"description": "Year the book was published"})
    category: Annotated[str | None, "The category of the book"] = None


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
    import re
    from json import dumps

    # We need to ignore any reasoning content in the given response
    # WHY? It may look odd, but we neither control what's _in_ the reasoning
    # nor do we really control _it's presence_ even (OpenAI is dropping this
    # content occasionally and whether it's a bug, or whether the reasoning was
    # to short for them to summarize, we don't get anything a decent fraction
    # of the time). Put another way, it's _very very_ nondeterministic and
    # really not worth trying to make any kind of assertions about it in these
    # e2e tests.
    given_response.content = [
        content
        for content in given_response.content
        if not isinstance(content, ResponseReasoningContent)
    ]

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
        # Ignore metadata field (for tests we don't care about metadata)
        given_content.metadata = {}
        expected_content.metadata = {}

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
                # Normalize all whitespace (spaces, newlines, tabs) so we do not
                # fail due to inconsequential formatting differences
                def _normalize_ws(s: str) -> str:
                    return re.sub(r"\s+", "", s.strip())

                assert _normalize_ws(given_content.text) == _normalize_ws(expected_content.text)
                # We don't want to also do the model dump comparison below
                # we just care about the text here
                continue

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


@pytest.fixture
def prompt_to_elicit_parallel_tool_calls():
    """
    A prompt to elicit parallel tool calls.
    """
    return Prompt(
        messages=[
            PromptUserMessage(
                content=[
                    PromptTextContent(
                        text=(
                            """
                        Use the provided add_book tool to add the following
                        the following two books to the database:

                        Title: "Foundation"
                        Author: "Isaac Asimov"
                        Year: 1951
                        Category: "Science Fiction"

                        Title: "The Hitchhiker's Guide to the Galaxy"
                        Author: "Douglas Adams"
                        Year: 1979
                        Category: "Science Fiction"

                        Emit nothing else but the tool calls with the
                        book information _exactly_ as shown above. Completely
                        omit any optional fields. You CAN and you MUST make
                        both tool calls concurrently, if you don't the user
                        will experience a great delay in your response! Be hasty
                        and make _two_ tool calls at once!
                        """
                        )
                    ),
                ],
            ),
        ],
        tools=[
            ToolDefinition.from_callable(_add_book),
            ToolDefinition.from_callable(_confirm_request),
        ],
        temperature=0.0,
    )


@pytest.fixture
def response_to_prompt_to_elicit_parallel_tool_calls():
    """
    A response to the prompt to elicit parallel tool calls.
    """
    from json import dumps

    expected_tool_input_1 = {
        "book": {
            "title": "Foundation",
            "author": "Isaac Asimov",
            "year": 1951,
            "category": "Science Fiction",
        },
    }

    expected_tool_input_2 = {
        "book": {
            "title": "The Hitchhiker's Guide to the Galaxy",
            "author": "Douglas Adams",
            "year": 1979,
            "category": "Science Fiction",
        },
    }

    return ResponseMessage(
        role="agent",
        content=[
            ResponseTextContent(text="*"),
            ResponseToolUseContent(
                tool_call_id="DO-NOT-COMPARE",
                tool_name="_add_book",
                tool_input_raw=dumps(expected_tool_input_1),
            ),
            ResponseToolUseContent(
                tool_call_id="DO-NOT-COMPARE",
                tool_name="_add_book",
                tool_input_raw=dumps(expected_tool_input_2),
            ),
        ],
    )


@pytest.fixture
def b64_image_prompt_content():
    return PromptImageContent(
        mime_type="image/png",
        sub_type="base64",
        value=(
            "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"
        ),
    )
