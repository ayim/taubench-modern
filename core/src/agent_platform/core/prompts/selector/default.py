import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from agent_platform.core.configurations import Configuration
from agent_platform.core.configurations.base import FieldMetadata
from agent_platform.core.prompts.prompt import Prompt
from agent_platform.core.prompts.selector.base import (
    PromptSelectionRequest,
    PromptSelector,
)

if TYPE_CHECKING:
    from importlib.abc import Traversable

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class DefaultPromptConfig(Configuration):
    """Configuration for default prompt."""

    default_prompt: str = field(
        default="conversation-default.yml",
        metadata=FieldMetadata(
            description="The default prompt to use if no other prompt is selected.",
            env_vars=["SEMA4AI_AGENT_SERVER_DEFAULT_PROMPT"],
        ),
    )


class DefaultPromptSelector(PromptSelector):
    """A default prompt selector that selects a prompt for a given platform
    based on the selected model family or model name. If neither are provided,
    the configured default prompt will be selected and if that fails, the first
    prompt in the prompts dictionary will be selected.
    """

    def select_prompt(
        self,
        request: PromptSelectionRequest | None = None,
        **kwargs,
    ) -> "tuple[str, Traversable]":
        """Select a prompt for a given platform based on the selected model family.

        Selections is based on the model family being included in the prompt name,
        e.g., "default-prompt.gpt.yml" will be selected for a request with a model
        family of "gpt". Alternatively, if model_name is provided in the request,
        the prompt will be selected based on the model name similarly as to how
        model family is checked for.

        If the provided request does not include a model family, the default
        prompt for the platform will be selected.
        """
        if request is None:
            # Create default request
            request = PromptSelectionRequest()

        selected_prompt = None

        # Handle direct prompt name selection
        if request.direct_prompt_name:
            selected_prompt = (
                request.direct_prompt_name,
                self.prompts[request.direct_prompt_name],
            )

        # Handle selection based on model family or model name
        if request.model_family is not None or request.model_name is not None:
            model_identifier = request.model_family or request.model_name
            # Check for model family or model name between dots
            if model_identifier is not None:
                pattern = re.compile(rf"\.{re.escape(model_identifier)}\.")

                for prompt_name, prompt_content in self.prompts.items():
                    if pattern.search(prompt_name):
                        selected_prompt = prompt_name, prompt_content

        if selected_prompt is None:
            try:
                selected_prompt = (
                    DefaultPromptConfig.default_prompt,
                    self.prompts[DefaultPromptConfig.default_prompt],
                )
            except KeyError:
                logger.warning(
                    "Default prompt not found",
                    default_prompt=DefaultPromptConfig.default_prompt,
                    available_prompts=list(self.prompts.keys()),
                )

        if selected_prompt is None:
            selected_prompt = next(iter(self.prompts.items()))

        return selected_prompt


def select_prompt(
    prompt_paths: list[str | Path] | None = None,
    package: str | None = None,
    direct_prompt_name: str | None = None,
    provider: str | None = None,
    model_family: str | None = None,
    model_name: str | None = None,
    **kwargs,
) -> Prompt:
    """Select a prompt using the default prompt selector.

    Arguments:
        prompt_paths: The paths to the prompts to load.
        package: The package to load the prompts from.
        direct_prompt_name: The name of the prompt to select.
        provider: A model provider to filter by.
        model_family: A model family to filter by.
        model_name: A model name to filter by.
        **kwargs: Additional keyword arguments to pass to the prompt selector.

    Returns:
        An unformatted Prompt object.
    """
    prompt_selector = DefaultPromptSelector(
        prompt_paths=prompt_paths,
        package=package,
    )

    selecion_request = PromptSelectionRequest(
        direct_prompt_name=direct_prompt_name,
        provider=provider,
        model_family=model_family,
        model_name=model_name,
    )

    _, prompt_path = prompt_selector.select_prompt(
        request=selecion_request,
        **kwargs,
    )

    return Prompt.load_yaml(prompt_path)
