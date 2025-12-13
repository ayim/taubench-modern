from collections.abc import Sequence

from agent_platform.architectures.experimental.consistency.state import ConsistencyArchState
from agent_platform.core import Kernel
from agent_platform.core.prompts.prompt import Prompt
from agent_platform.core.prompts.selector.default import select_prompt
from agent_platform.core.tools.tool_definition import ToolDefinition


async def build_prompt(
    kernel: Kernel,
    state: ConsistencyArchState,
    *,
    prompt_path: str,
    tools: Sequence[ToolDefinition] = (),
    minimize_reasoning: bool = False,
    tool_choice: str | None = None,
) -> Prompt:
    """Constructs a complete `Prompt` object from a template and configuration.

    This factory function handles the full lifecycle of prompt creation:
    1. Selects a prompt template from a relative file path.
    2. Renders the template using the provided state object.
    3. Optionally attaches tools, requests minimized reasoning, and sets a
       specific tool_choice for the model.

    Args:
        kernel: The active Kernel instance, used for its prompt formatting service.
        state: The `ConsistencyArchState` object, providing the context for
               Jinja2 template rendering.
        prompt_path: The relative path to the prompt template directory within the
                     current package (e.g., "prompts/plan-creation").
        tools: A sequence of `ToolDefinition` objects to be made available to the
               model for this specific prompt.
        minimize_reasoning: If True, configures the prompt to request less
                            verbose reasoning from the model.
        tool_choice: If set, instructs the model to use a specific tool by name.
                     (e.g., "any", "auto", or a specific tool name).

    Returns:
        A fully configured `Prompt` instance ready to be sent to a model.
    """
    # 1. Load the prompt template from the specified path within this package.
    template = select_prompt(prompt_paths=[prompt_path], package=__package__)

    # 2. Render the template with the state, creating the base prompt.
    prompt = await kernel.prompts.format_prompt(template, state=state)

    # 3. Apply optional configurations
    if minimize_reasoning:
        prompt = prompt.with_minimized_reasoning()
    if tools:
        prompt = prompt.with_tools(*tools)
    if tool_choice:
        prompt.tool_choice = tool_choice

    return prompt
