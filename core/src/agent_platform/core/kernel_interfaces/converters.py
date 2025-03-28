from abc import ABC, abstractmethod

from agent_platform.core.prompts import PromptMessage
from agent_platform.core.thread import ThreadMessage


class ConvertersInterface(ABC):
    """Methods for converting between thread, prompt, and response objects.

    There's a relationship bewteen these three bits of state that's very
    imporant: a cycle from thread state -> what goes into a Prompt ->
    what comes out of a prompt (response) -> back into thread state.
    """

    @abstractmethod
    async def thread_messages_to_prompt_messages(
        self,
        messages: list[ThreadMessage],
    ) -> list[PromptMessage]:
        """Convert a list of thread messages to a list of prompt messages.

        Why is this a big deal? There may be things in the thread state
        that deserve special consideration during prompting. Say we have
        a Vega chart in the thread state. Do we want to include that in the
        prompt? Do we include it as text? Or do we include it as an image?

        These choices are _important_ for what our agents can and can't do.
        If we include the Vega chart as text, it'd probably be easy for the
        agent to add tooltips (structured transform of the chart spec JSON).
        But, in this case, it'd be hard for the agent to do something like
        "fix the spacing in this chart".

        If we include the Vega chart as an image, it'd be easy for the agent
        to do something like "fix the spacing in this chart". But, it'd be
        hard for the agent to add tooltips.

        It will be the responsibility of the ConvertersInterface to handle
        these translations (and do so in a configurable way).

        Arguments:
            messages: The list of thread messages to convert.
        """
        pass
