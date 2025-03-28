from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from agent_platform_core.prompts.messages import (
    PromptAgentMessage,
    PromptUserMessage,
)
from agent_platform_core.prompts.special.base import SpecialPromptMessage

if TYPE_CHECKING:
    from agent_platform_core.kernel import Kernel


@dataclass(frozen=True)
class DocumentsParams:
    """Parameters for the documents special message."""

    maximum_number_of_documents: int = field(
        default=5,
        metadata={
            "description": (
                "The maximum number of documents to include in the prompt."
            ),
        },
    )
    """The maximum number of documents to include in the prompt."""

    token_budget_as_percentage: float = field(
        default=0.50,
        metadata={
            "description": (
                "The token budget as a percentage of the total token budget."
            ),
        },
    )
    """The token budget as a percentage of the total token budget."""

    @classmethod
    def model_validate(cls, data: dict) -> "DocumentsParams":
        """Validate and convert a dictionary into a DocumentsParams instance."""
        data = data.copy()
        return cls(**data)


@dataclass(frozen=True)
class DocumentsSpecialMessage(SpecialPromptMessage):
    """Special message for including the documents in a prompt."""

    params: DocumentsParams = field(
        default_factory=DocumentsParams,
    )
    """The parameters for the documents special message."""

    async def hydrate(
        self,
        kernel: "Kernel",
    ) -> list[PromptUserMessage | PromptAgentMessage]:
        """Hydrate the documents special message."""
        # TODO: handle documents
        return []

    @classmethod
    def model_validate(cls, data: dict) -> "DocumentsSpecialMessage":
        """Validate and convert a dictionary into a DocumentsSpecialMessage instance."""
        data = data.copy()
        params = DocumentsParams.model_validate(data.pop("params", {}))
        return cls(params=params, **data)


DocumentsSpecialMessage.register_message_by_role(
    "$documents",
    DocumentsSpecialMessage,
)
