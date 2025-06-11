import json
import logging

from agent_platform.core.agent_architectures import StateBase
from agent_platform.core.kernel import PromptsInterface
from agent_platform.core.prompts.prompt import Prompt
from agent_platform.server.kernel.kernel_mixin import UsesKernelMixin

logger = logging.getLogger(__name__)


class AgentServerPromptsInterface(PromptsInterface, UsesKernelMixin):
    """Handles prompt building/management via importlib.resources."""

    async def format_prompt(
        self,
        prompt: Prompt,
        *,
        state: StateBase | None = None,
    ) -> Prompt:
        """
        Format a prompt using the kernel and state.

        Arguments:
            prompt: The prompt to format.
            state: The agent architecture's state to use in formatting. (Optional.)

        Returns:
            A fully formatted Prompt.
        """
        # Create input metadata for tracing
        input_metadata = {
            "user_id": self.kernel.user.cr_user_id
            if self.kernel.user.cr_user_id
            else self.kernel.user.sub,
            "agent_architecture": self.kernel.agent.agent_architecture.name,
            "agent_architecture_version": self.kernel.agent.agent_architecture.version,
        }

        with self.kernel.ctx.start_span(
            "format_prompt",
            attributes={
                "langsmith.span.kind": "prompt",
            },
        ) as span:
            # Set input info for the span
            span.set_attribute("input.value", json.dumps(input_metadata))

            # Track prompt before formatting for debugging
            span.add_event("formatting prompt")

            # Format the prompt with kernel and state
            final_prompt = prompt.format_with_values(
                kernel=self.kernel,
                state=state,
            )

            # Set output attributes for OpenTelemetry span
            try:
                # Build output JSON (without tools for now, they'll be added later)
                output_json = {
                    "formatted_prompt": final_prompt.to_pretty_yaml(),
                }

                # Set output value
                span.set_attribute("output.value", json.dumps(output_json))
                span.add_event("formatted prompt")

            except Exception as e:
                logger.error(f"Error setting span attributes: {e}")
                span.record_exception(e)

        return final_prompt

    def record_tools_in_trace(self, prompt: Prompt, span_name: str = "prompt_tools") -> None:
        """Record tools from a prompt in a trace.

        This method should be called just before submission to a provider,
        after tools have been attached to the prompt.

        Args:
            prompt: The prompt containing tools
            span_name: Optional name for the span
        """
        # Skip if no tools
        if not prompt.tools:
            return

        # Use this to record tools right before submitting to provider
        with self.kernel.ctx.start_span(
            span_name,
            attributes={
                "langsmith.span.kind": "prompt.tools",
            },
        ) as span:
            # Extract tool names
            tool_names = [tool.name for tool in prompt.tools]

            # Log tools being recorded
            logger.info(f"Recording {len(tool_names)} tools in trace: {', '.join(tool_names)}")
            span.set_attribute("tools", ", ".join(tool_names))

            tools_detail = []
            for tool in prompt.tools:
                tool_info = {
                    "name": tool.name,
                    "description": tool.description,
                }
                # Add schema if available
                if tool.input_schema:
                    try:
                        # Try to convert schema to string if it's a dict
                        if isinstance(tool.input_schema, dict):
                            tool_info["parameters"] = json.dumps(tool.input_schema)
                        else:
                            tool_info["parameters"] = str(tool.input_schema)
                    except Exception as e:
                        logger.warning(f"Failed to serialize tool schema: {e}")

                tools_detail.append(tool_info)

            # Format in LangSmith compatible format - tools is a top-level key
            output_json = {
                "prompt_info": {
                    "tools_count": len(tool_names),
                    "tool_names": tool_names,
                },
                "tools": tools_detail,
            }
            span.set_attribute("output.value", json.dumps(output_json))
