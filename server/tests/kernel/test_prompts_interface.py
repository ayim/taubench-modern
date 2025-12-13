from dataclasses import dataclass

import pytest

from agent_platform.core.agent_architectures import StateBase
from agent_platform.core.prompts.content.text import PromptTextContent
from agent_platform.core.prompts.messages import PromptUserMessage
from agent_platform.core.prompts.prompt import Prompt
from server.tests.storage.sample_model_creator import SampleModelCreator

pytest_plugins = ("server.tests.storage_fixtures",)


@dataclass
class _SimpleState(StateBase):
    status: str = "initial"


@pytest.mark.asyncio
async def test_format_prompt_renders_state_and_kwargs(sqlite_storage, tmp_path) -> None:
    """Ensure AgentServerPromptsInterface renders templates with kernel, state, and kwargs."""
    model_creator = SampleModelCreator(sqlite_storage, tmp_path)
    await model_creator.setup()
    kernel = await model_creator.create_agent_server_kernel()

    prompt = Prompt(
        system_instruction=("User {{ kernel.user.cr_user_id }} custom {{ custom_value }} state {{ state.status }}"),
        messages=[
            PromptUserMessage(content=[PromptTextContent(text="Echo {{ custom_value }} for {{ state.status }}")])
        ],
    )

    state = _SimpleState(status="ready")

    result = await kernel.prompts.format_prompt(
        prompt=prompt,
        state=state,
        custom_value="42",
    )

    assert result.system_instruction == "User test_user custom 42 state ready"
    assert isinstance(result.messages[0], PromptUserMessage)
    assert isinstance(result.messages[0].content[0], PromptTextContent)
    assert result.messages[0].content[0].text == "Echo 42 for ready"
