from typing import TYPE_CHECKING

from reducto.types.shared.parse_response import ResultFullResult

if TYPE_CHECKING:
    from reducto.types import ParseResponse
    from sema4ai_docint.models.extraction import ExtractionResult

from agent_platform.core.kernel_interfaces.kernel_mixin import UsesKernelMixin
from agent_platform.core.platforms.base import PlatformParsers
from agent_platform.core.responses import ResponseMessage, ResponseTextContent


class ReductoParsers(PlatformParsers, UsesKernelMixin):
    """Converts Reducto responses to agent-server response types."""

    def classify_response(self, response: "ResponseMessage") -> ResponseMessage:
        # The LLM should have already classified the response.
        # Do we need to validate that the LLM did what we asked
        # it to do? (e.g. return a single word)
        return response

    def parse_response(
        self, response: "ParseResponse | ExtractionResult", full_output: bool = False
    ) -> ResponseMessage:
        """Parses a Reducto/sema4ai-docint response to an agent-server model response."""
        from reducto.types import ParseResponse
        from sema4ai_docint.models.extraction import ExtractionResult

        if isinstance(response, ParseResponse):
            if not isinstance(response.result, ResultFullResult):
                raise ValueError(f"Expected ResultFullResult, got {type(response.result)}")

            text_content = []
            for chunk in response.result.chunks:
                text_content.append(ResponseTextContent(text=chunk.content))

            return ResponseMessage(
                role="agent",
                content=text_content,
                metadata={
                    "reducto_job_id": response.job_id,
                    "reducto_pdf_url": response.pdf_url,
                },
            )

        elif isinstance(response, ExtractionResult):
            import json

            return ResponseMessage(
                role="agent",
                content=[
                    ResponseTextContent(
                        text=json.dumps(response.results, indent=2),
                    ),
                    ResponseTextContent(
                        text=json.dumps(response.citations, indent=2),
                    ),
                ],
            )
        else:
            raise ValueError(f"Unsupported response type: {type(response)}")
