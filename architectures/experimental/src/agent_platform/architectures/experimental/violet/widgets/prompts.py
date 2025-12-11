from __future__ import annotations

from agent_platform.architectures.experimental.violet.state import VioletState
from agent_platform.core import Kernel
from agent_platform.core.prompts.prompt import Prompt
from agent_platform.core.prompts.selector.default import select_prompt


async def build_chart_prompt(
    *,
    kernel: Kernel,
    state: VioletState,
    description: str,
    error_hint: str | None = None,
    partial_agent_reply: str | None = None,
) -> Prompt:
    """
    Build the chart-generation prompt for a detected `<chart .../>` placeholder.
    """
    template = select_prompt(
        prompt_paths=["prompts/widgets/charts"],
        package="agent_platform.architectures.experimental.violet",
    )
    prompt = await kernel.prompts.format_prompt(
        template,
        state=state,
        description=description,
        error_hint=error_hint or "",
        partial_agent_reply=partial_agent_reply or "",
        recent_user_message=(kernel.thread.latest_user_message_as_text or ""),
        data_frames_overview=getattr(kernel.data_frames, "data_frames_system_prompt", ""),
    )
    return prompt


async def build_buttons_prompt(
    *,
    kernel: Kernel,
    state: VioletState,
    description: str,
    error_hint: str | None = None,
    partial_agent_reply: str | None = None,
) -> Prompt:
    template = select_prompt(
        prompt_paths=["prompts/widgets/buttons"],
        package="agent_platform.architectures.experimental.violet",
    )
    prompt = await kernel.prompts.format_prompt(
        template,
        state=state,
        description=description,
        error_hint=error_hint or "",
        partial_agent_reply=partial_agent_reply or "",
        recent_user_message=(kernel.thread.latest_user_message_as_text or ""),
    )
    return prompt.with_minimized_reasoning()
