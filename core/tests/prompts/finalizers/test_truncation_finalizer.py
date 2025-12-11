from unittest.mock import MagicMock

import pytest

from agent_platform.core.prompts.content.tool_result import PromptToolResultContent
from agent_platform.core.prompts.finalizers.truncation_finalizer import TruncationFinalizer
from agent_platform.core.prompts.messages import (
    PromptAgentMessage,
    PromptTextContent,
    PromptToolUseContent,
    PromptUserMessage,
)
from agent_platform.core.prompts.prompt import Prompt

# ---------- Test utilities ----------


class MockPlatform:
    """Simple platform mock with a context window map."""

    def __init__(self) -> None:
        self.client = MagicMock()
        self.client.model_map = MagicMock()
        self.client.model_map.model_context_windows = {
            "o4-mini-low": 16000,
            "gpt-4-1": 128000,
        }


@pytest.fixture
def mock_kernel():
    return MagicMock()


@pytest.fixture
def mock_platform():
    return MockPlatform()


def words(n: int) -> str:
    """Make a space-separated string of n short words."""
    return ("w " * n).strip()


def token_budget(platform: MockPlatform, model: str, pct: float) -> int:
    """Compute the input token budget used by the finalizer."""
    max_tokens = platform.client.model_map.model_context_windows.get(model, 128000)
    return int(max_tokens * pct)


def count_prompt_tokens_for(messages: list, base_prompt: Prompt) -> int:
    """
    Recreate the "hydrated" prompt the finalizer uses (same fields) and count tokens.
    """
    hydrated = Prompt(
        system_instruction=base_prompt.system_instruction,
        messages=list(messages),  # mutated by the finalizer
        tools=base_prompt.tools,
        tool_choice=base_prompt.tool_choice,
        temperature=base_prompt.temperature,
        seed=base_prompt.seed,
        max_output_tokens=base_prompt.max_output_tokens,
        stop_sequences=base_prompt.stop_sequences,
        top_p=base_prompt.top_p,
    )
    # Finalizer calls count_tokens_approx() without passing model, which defaults to o4-mini-low
    return hydrated.count_tokens_approx()


def assert_not_over_budget(
    messages: list,
    base_prompt: Prompt,
    platform: MockPlatform,
    model: str,
    pct: float,
):
    total = count_prompt_tokens_for(messages, base_prompt)
    assert total <= token_budget(platform, model, pct), (
        f"prompt still over budget: {total} > {token_budget(platform, model, pct)}"
    )


TRUNC_MARKER = "[Truncated...]"


# ---------- Tests ----------


@pytest.mark.asyncio
async def test_many_small_messages_progress_and_preserve_newest(mock_kernel, mock_platform):
    """
    A prompt with many small plain-text messages should trigger truncation,
    reduce total tokens, and prefer trimming older content. We *do not*
    require being under a tight budget here because suffix + message scaffolding
    impose a hard floor.
    """
    finalizer = TruncationFinalizer(
        token_budget_percentage=0.40,  # moderately tight but realistic
        text_truncation_token_floor=0,  # allow reduction on small items
        truncation_token_floor=0,
    )

    # Build a moderate number of small user/agent messages; starts with user (required by Prompt)
    small = words(20)
    msgs: list = []
    for _ in range(60):  # 120 small messages total
        msgs.append(PromptUserMessage([PromptTextContent(text=small)]))
        msgs.append(PromptAgentMessage([PromptTextContent(text=small)]))

    # Leave a recognizable last (newest) message to check oldest-first preference
    newest_user = words(20)
    msgs.append(PromptUserMessage([PromptTextContent(text=newest_user)]))

    prompt = Prompt(messages=msgs)

    before_last_text = prompt.messages[-1].content[0].text  # type: ignore
    pre_tokens = count_prompt_tokens_for(prompt.messages, prompt)

    # Run
    result = await finalizer(
        prompt.messages, prompt, mock_kernel, platform=mock_platform, model="o4-mini-low"
    )

    post_tokens = count_prompt_tokens_for(result, prompt)
    assert post_tokens < pre_tokens, f"no progress: {post_tokens} !< {pre_tokens}"

    # Oldest-first: the newest should remain untouched in this scenario.
    assert isinstance(result[-1], PromptUserMessage)
    assert isinstance(result[-1].content[0], PromptTextContent)
    after_last_text = result[-1].content[0].text
    assert after_last_text == before_last_text


@pytest.mark.asyncio
async def test_many_small_tool_calls_progress_and_preserve_newest(mock_kernel, mock_platform):
    """
    Many small tool results aggregate to overflow—finalizer should reduce total tokens.
    We include tool-use overhead implicitly via count_tokens_approx.
    """
    finalizer = TruncationFinalizer(
        token_budget_percentage=0.50,
        truncation_token_floor=0,
        text_truncation_token_floor=0,
    )

    small_tool_text = words(60)

    # Start with a tiny seed user message
    msgs: list = [PromptUserMessage([PromptTextContent(text="seed")])]
    for i in range(30):
        # Tool use (not truncatable) + tool result (truncatable text)
        msgs.append(
            PromptAgentMessage(
                [
                    PromptToolUseContent(  # tool-use is part of the prompt and not removed
                        tool_call_id=f"call_{i}",
                        tool_name="small_tool",
                        tool_input_raw="",
                    )
                ]
            )
        )
        msgs.append(
            PromptUserMessage(
                [
                    PromptToolResultContent(
                        tool_call_id=f"call_{i}",
                        tool_name="small_tool",
                        content=[PromptTextContent(text=small_tool_text)],
                    )
                ]
            )
        )

    prompt = Prompt(messages=msgs)

    # Snapshot of newest tool result text to check protection of the newest item.
    assert isinstance(prompt.messages[-1], PromptUserMessage)
    assert isinstance(prompt.messages[-1].content[0], PromptToolResultContent)
    assert isinstance(prompt.messages[-1].content[0].content[0], PromptTextContent)
    last_tool_before = prompt.messages[-1].content[0].content[0].text

    pre_tokens = count_prompt_tokens_for(prompt.messages, prompt)
    result = await finalizer(
        prompt.messages, prompt, mock_kernel, platform=mock_platform, model="o4-mini-low"
    )
    post_tokens = count_prompt_tokens_for(result, prompt)
    assert post_tokens < pre_tokens, f"no progress: {post_tokens} !< {pre_tokens}"

    # Newest (last) tool result should remain intact thanks to oldest-first.
    assert isinstance(result[-1], PromptUserMessage)
    assert isinstance(result[-1].content[0], PromptToolResultContent)
    assert isinstance(result[-1].content[0].content[0], PromptTextContent)
    last_tool_after = result[-1].content[0].content[0].text
    assert last_tool_after == last_tool_before


@pytest.mark.asyncio
async def test_large_tool_result_absorbs_most_truncation(mock_kernel, mock_platform):
    """
    One very large, older tool result + many small later ones.
    The large older one should absorb most of the truncation and show the marker.
    We assert strong progress instead of under-budget (tight budgets are often impossible).
    """
    finalizer = TruncationFinalizer(
        token_budget_percentage=0.40,
        truncation_token_floor=1000,  # keep some of the large result
        text_truncation_token_floor=256,
    )

    big = words(30000)  # very large
    small = words(20)

    msgs: list = [
        PromptUserMessage([PromptTextContent(text="seed")]),
        # Big tool call
        PromptAgentMessage(
            [
                PromptToolUseContent(
                    tool_call_id="call_big",
                    tool_name="big_tool",
                    tool_input_raw="",
                )
            ]
        ),
        # Older big tool result
        PromptUserMessage(
            [
                PromptToolResultContent(
                    tool_call_id="call_big",
                    tool_name="big_tool",
                    content=[PromptTextContent(text=big)],
                )
            ]
        ),
    ]
    # Later, many small tool results
    for i in range(40):
        msgs.append(
            PromptAgentMessage(
                [
                    PromptToolUseContent(
                        tool_call_id=f"call_small_{i}",
                        tool_name="small_tool",
                        tool_input_raw="",
                    )
                ]
            )
        )
        msgs.append(
            PromptUserMessage(
                [
                    PromptToolResultContent(
                        tool_call_id=f"call_small_{i}",
                        tool_name="small_tool",
                        content=[PromptTextContent(text=small)],
                    )
                ]
            )
        )

    prompt = Prompt(messages=msgs)

    pre_tokens = count_prompt_tokens_for(prompt.messages, prompt)
    result = await finalizer(
        prompt.messages, prompt, mock_kernel, platform=mock_platform, model="o4-mini-low"
    )
    post_tokens = count_prompt_tokens_for(result, prompt)

    # Strong progress: reduce by at least ~60%
    assert post_tokens <= int(pre_tokens * 0.4), (
        f"insufficient reduction: {post_tokens} vs {pre_tokens}"
    )

    # The big, older tool result should show the truncation marker
    assert isinstance(result[2], PromptUserMessage)
    assert isinstance(result[2].content[0], PromptToolResultContent)
    assert isinstance(result[2].content[0].content[0], PromptTextContent)
    truncated_text = result[2].content[0].content[0].text
    assert TRUNC_MARKER in truncated_text


@pytest.mark.asyncio
async def test_long_user_message_truncated_under_budget(mock_kernel, mock_platform):
    """
    Simple scenario where getting under budget is feasible, but the very first user
    instructions must remain untouched.
    """
    finalizer = TruncationFinalizer(
        token_budget_percentage=0.30,
        text_truncation_token_floor=256,
        truncation_token_floor=1000,
    )

    instructions = "Keep these instructions intact."
    long_user = words(4000)  # large top-level text
    prompt = Prompt(
        messages=[
            PromptUserMessage([PromptTextContent(text=instructions)]),
            PromptUserMessage([PromptTextContent(text=long_user)]),
            PromptAgentMessage([PromptTextContent(text="ack")]),
        ]
    )

    result = await finalizer(
        prompt.messages, prompt, mock_kernel, platform=mock_platform, model="o4-mini-low"
    )

    assert_not_over_budget(
        result,
        prompt,
        mock_platform,
        "o4-mini-low",
        finalizer.token_budget_percentage,
    )

    # First user turn is preserved verbatim, but the second user message should be truncated.
    assert result[0].content[0].text == instructions  # type: ignore
    assert isinstance(result[1], PromptUserMessage)
    assert isinstance(result[1].content[0], PromptTextContent)
    assert TRUNC_MARKER in result[1].content[0].text


@pytest.mark.asyncio
async def test_long_agent_message_truncated_under_budget(mock_kernel, mock_platform):
    """
    Another simple scenario where under-budget is feasible.
    """
    finalizer = TruncationFinalizer(
        token_budget_percentage=0.30,
        text_truncation_token_floor=256,
        truncation_token_floor=1000,
    )

    long_agent = words(4000)
    prompt = Prompt(
        messages=[
            PromptUserMessage([PromptTextContent(text="seed")]),
            PromptAgentMessage([PromptTextContent(text=long_agent)]),
        ]
    )

    result = await finalizer(
        prompt.messages, prompt, mock_kernel, platform=mock_platform, model="o4-mini-low"
    )

    assert_not_over_budget(
        result,
        prompt,
        mock_platform,
        "o4-mini-low",
        finalizer.token_budget_percentage,
    )

    assert isinstance(result[1], PromptAgentMessage)
    assert isinstance(result[1].content[0], PromptTextContent)
    assert TRUNC_MARKER in result[1].content[0].text  # agent content truncated


@pytest.mark.asyncio
async def test_oldest_first_preference_for_plain_text(mock_kernel, mock_platform):
    """
    Two truncatable plain-text messages (after the preserved user instructions):
    an older huge one and a newer small one (< text floor). Budget should trim the
    older agent message and leave the newer user message untouched.
    """
    finalizer = TruncationFinalizer(
        token_budget_percentage=0.30,
        text_truncation_token_floor=512,
        truncation_token_floor=1000,
    )

    preserved_instructions = "Always follow these instructions."
    older_huge = words(18000)  # huge
    newer_small = words(50)  # << text floor

    prompt = Prompt(
        messages=[
            PromptUserMessage([PromptTextContent(text=preserved_instructions)]),
            PromptAgentMessage([PromptTextContent(text=older_huge)]),
            PromptUserMessage([PromptTextContent(text=newer_small)]),
        ]
    )

    assert isinstance(prompt.messages[2], PromptUserMessage)
    assert isinstance(prompt.messages[2].content[0], PromptTextContent)
    newer_before = prompt.messages[2].content[0].text

    result = await finalizer(
        prompt.messages, prompt, mock_kernel, platform=mock_platform, model="o4-mini-low"
    )

    assert_not_over_budget(
        result,
        prompt,
        mock_platform,
        "o4-mini-low",
        finalizer.token_budget_percentage,
    )

    # First user message is preserved.
    assert result[0].content[0].text == preserved_instructions  # type: ignore

    # Older huge agent text should be truncated
    assert isinstance(result[1], PromptAgentMessage)
    assert isinstance(result[1].content[0], PromptTextContent)
    assert TRUNC_MARKER in result[1].content[0].text

    # Newer small user message should remain untouched (below floor)
    assert isinstance(result[2], PromptUserMessage)
    assert isinstance(result[2].content[0], PromptTextContent)
    assert result[2].content[0].text == newer_before


@pytest.mark.asyncio
async def test_oldest_first_preference_for_tool_results(mock_kernel, mock_platform):
    """
    Two tool results: older huge & newer small (below tool floor).
    Budget requires reducing only the older one; newer should be untouched.
    """
    finalizer = TruncationFinalizer(
        token_budget_percentage=0.80,
        truncation_token_floor=1000,
        text_truncation_token_floor=512,
    )

    older_huge_tool = words(18000)
    newer_small_tool = words(100)

    prompt = Prompt(
        messages=[
            PromptUserMessage([PromptTextContent(text="seed")]),
            PromptAgentMessage(
                [
                    PromptToolUseContent(
                        tool_call_id="older",
                        tool_name="older_tool",
                        tool_input_raw="",
                    )
                ]
            ),
            PromptUserMessage(
                [
                    PromptToolResultContent(
                        tool_call_id="older",
                        tool_name="older_tool",
                        content=[PromptTextContent(text=older_huge_tool)],
                    )
                ]
            ),
            PromptAgentMessage(
                [
                    PromptToolUseContent(
                        tool_call_id="newer",
                        tool_name="newer_tool",
                        tool_input_raw="",
                    )
                ]
            ),
            PromptUserMessage(
                [
                    PromptToolResultContent(
                        tool_call_id="newer",
                        tool_name="newer_tool",
                        content=[PromptTextContent(text=newer_small_tool)],
                    )
                ]
            ),
        ]
    )

    assert isinstance(prompt.messages[4], PromptUserMessage)
    assert isinstance(prompt.messages[4].content[0], PromptToolResultContent)
    assert isinstance(prompt.messages[4].content[0].content[0], PromptTextContent)
    newer_before = prompt.messages[4].content[0].content[0].text  # newest tool result text

    result = await finalizer(
        prompt.messages, prompt, mock_kernel, platform=mock_platform, model="o4-mini-low"
    )

    assert_not_over_budget(
        result,
        prompt,
        mock_platform,
        "o4-mini-low",
        finalizer.token_budget_percentage,
    )

    # Older tool result truncated (lives at index 2)
    assert isinstance(result[2], PromptUserMessage)
    assert isinstance(result[2].content[0], PromptToolResultContent)
    assert isinstance(result[2].content[0].content[0], PromptTextContent)
    assert TRUNC_MARKER in result[2].content[0].content[0].text

    # Newer small one remains untouched (below floor) at index 4
    assert isinstance(result[4], PromptUserMessage)
    assert isinstance(result[4].content[0], PromptToolResultContent)
    assert isinstance(result[4].content[0].content[0], PromptTextContent)
    assert result[4].content[0].content[0].text == newer_before


@pytest.mark.asyncio
async def test_mixed_plain_text_vs_tool_prefers_tool_first(mock_kernel, mock_platform):
    """
    Older plain text (huge) followed by a newer tool result (large). Even though the plain
    text is older, the finalizer should prefer trimming the tool result first. The older
    agent text should remain untouched if truncating the tool is sufficient.
    """
    finalizer = TruncationFinalizer(
        token_budget_percentage=0.80,
        text_truncation_token_floor=512,
        truncation_token_floor=1000,
    )

    preserved_instructions = "Preserve these instructions."
    older_huge_text = words(8000)
    newer_tool_text = words(5000)

    prompt = Prompt(
        messages=[
            PromptUserMessage([PromptTextContent(text=preserved_instructions)]),
            PromptAgentMessage([PromptTextContent(text=older_huge_text)]),
            PromptAgentMessage(
                [
                    PromptToolUseContent(
                        tool_call_id="tool",
                        tool_name="data_tool",
                        tool_input_raw="",
                    )
                ]
            ),
            PromptUserMessage(
                [
                    PromptToolResultContent(
                        tool_call_id="tool",
                        tool_name="data_tool",
                        content=[PromptTextContent(text=newer_tool_text)],
                    )
                ]
            ),
        ]
    )

    assert isinstance(prompt.messages[3], PromptUserMessage)
    assert isinstance(prompt.messages[3].content[0], PromptToolResultContent)
    assert isinstance(prompt.messages[3].content[0].content[0], PromptTextContent)
    newer_tool_before = prompt.messages[3].content[0].content[0].text

    assert isinstance(prompt.messages[1], PromptAgentMessage)
    assert isinstance(prompt.messages[1].content[0], PromptTextContent)
    older_plain_before = prompt.messages[1].content[0].text

    result = await finalizer(
        prompt.messages, prompt, mock_kernel, platform=mock_platform, model="o4-mini-low"
    )

    assert_not_over_budget(
        result,
        prompt,
        mock_platform,
        "o4-mini-low",
        finalizer.token_budget_percentage,
    )

    # Instructions remain intact and the older agent text is untouched.
    assert result[0].content[0].text == preserved_instructions  # type: ignore
    assert isinstance(result[1], PromptAgentMessage)
    assert isinstance(result[1].content[0], PromptTextContent)
    assert result[1].content[0].text == older_plain_before

    # Tool result is prioritized for truncation
    assert isinstance(result[3], PromptUserMessage)
    assert isinstance(result[3].content[0], PromptToolResultContent)
    assert isinstance(result[3].content[0].content[0], PromptTextContent)
    assert result[3].content[0].content[0].text != newer_tool_before
    assert TRUNC_MARKER in result[3].content[0].content[0].text


def test_collect_truncatable_content_includes_plain_text_and_tool(mock_platform):
    """
    Directly unit-test _collect_truncatable_content to ensure it classifies and carries metadata.
    Also verifies the floor includes the suffix token cost.
    """
    finalizer = TruncationFinalizer(
        token_budget_percentage=0.80,
        text_truncation_token_floor=512,
        truncation_token_floor=1000,
    )

    prompt = Prompt(
        messages=[
            PromptUserMessage([PromptTextContent(text="Preserve me")]),
            PromptAgentMessage([PromptTextContent(text=words(1000))]),  # plain text
            PromptAgentMessage(
                [
                    PromptToolUseContent(
                        tool_call_id="t1",
                        tool_name="tool1",
                        tool_input_raw="",
                    )
                ]
            ),
            PromptUserMessage(
                [
                    PromptToolResultContent(
                        tool_call_id="t1",
                        tool_name="tool1",
                        content=[PromptTextContent(text=words(1200))],
                    )
                ]
            ),
        ]
    )

    items = finalizer._collect_truncatable_content(prompt.messages)

    # Should have both a 'text' item and a 'tool' item
    kinds = {it["item_type"] for it in items}
    assert "text" in kinds
    assert "tool" in kinds

    # Expected extra metadata
    for it in items:
        assert "message_index" in it
        assert "floor" in it
        assert it["tokens"] > 0
        assert len(it["text_contents"]) >= 1
        assert isinstance(it["text_contents"][0], PromptTextContent)

    # The floor should be at least the suffix token cost (times content chunks)
    suffix_tokens = PromptTextContent(text=TRUNC_MARKER).count_tokens_approx()
    for it in items:
        assert it["floor"] >= suffix_tokens * len(it["text_contents"])


@pytest.mark.asyncio
async def test_respects_tool_floor_even_if_budget_demands_more(mock_kernel, mock_platform):
    """
    If budget asks for more than reducible (above the floor), the item must not go below its floor.
    We don't assert staying under budget in this test—only that floors are respected.
    """
    finalizer = TruncationFinalizer(
        token_budget_percentage=0.10,  # very tight
        truncation_token_floor=1000,  # enforce a high floor for tools
        text_truncation_token_floor=512,
    )

    # Build a tool result just slightly over the floor in token terms.
    just_over_floor = words(900)  # ~1200 tokens

    prompt = Prompt(
        messages=[
            PromptUserMessage([PromptTextContent(text="seed")]),
            PromptAgentMessage(
                [
                    PromptToolUseContent(
                        tool_call_id="near_floor",
                        tool_name="near_floor_tool",
                        tool_input_raw="",
                    )
                ]
            ),
            PromptUserMessage(
                [
                    PromptToolResultContent(
                        tool_call_id="near_floor",
                        tool_name="near_floor_tool",
                        content=[PromptTextContent(text=just_over_floor)],
                    )
                ]
            ),
        ]
    )

    result = await finalizer(
        prompt.messages, prompt, mock_kernel, platform=mock_platform, model="o4-mini-low"
    )

    # Confirm the tool result wasn't pushed *below* floor.
    assert isinstance(result[2], PromptUserMessage)
    assert isinstance(result[2].content[0], PromptToolResultContent)
    assert isinstance(result[2].content[0].content[0], PromptTextContent)
    tool_text = result[2].content[0].content[0].text
    measured_tokens = PromptTextContent(text=tool_text).count_tokens_approx()
    assert measured_tokens >= finalizer.truncation_token_floor
