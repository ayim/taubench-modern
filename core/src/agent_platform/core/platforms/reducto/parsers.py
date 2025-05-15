from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from reducto.types import ExtractResponse, ParseResponse

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
        self, response: "ParseResponse | ExtractResponse"
    ) -> ResponseMessage:
        """Parses a Reducto response to an agent-server model response."""
        from reducto.types import ExtractResponse, ParseResponse

        if isinstance(response, ParseResponse):
            # TODO: do we download and process the URL result?
            if response.result.type == "url":
                return ResponseMessage(
                    role="agent",
                    content=[
                        ResponseTextContent(
                            text=response.to_json(),
                        ),
                    ],
                )

            block_metadata = []
            chunk_metadata = []
            text_content = []
            for chunk in response.result.chunks:
                chunk_metadata = {}
                if chunk.enrichment_success and chunk.enriched:
                    chunk_metadata["reducto_chunk_enrichment_success"] = True
                    chunk_metadata["reducto_chunk_enriched"] = chunk.enriched
                else:
                    chunk_metadata["reducto_chunk_enrichment_success"] = False

                chunk_metadata["chunk_embed_text"] = chunk.embed

                for block in chunk.blocks:
                    block_metadata.append(
                        {
                            "reducto_block_confidence": block.confidence,
                            "reducto_block_type": block.type,
                            "reducto_block_bbox": block.bbox.to_dict(),
                            "reducto_block_image_url": block.image_url,
                        }
                    )
                    if block.content:
                        text_content.append(ResponseTextContent(text=block.content))

            return ResponseMessage(
                role="agent",
                content=text_content,
                metadata={
                    "reducto_blocks": block_metadata,
                    "reducto_chunks": chunk_metadata,
                    "reducto_duration": response.duration,
                    "reducto_job_id": response.job_id,
                    "reducto_pdf_url": response.pdf_url,
                    "reducto_usage": response.usage.to_dict(),
                },
            )

        elif isinstance(response, ExtractResponse):
            # TODO: look more at extract... focused on Parse for now
            return ResponseMessage(
                role="agent",
                content=[
                    ResponseTextContent(
                        text=response.to_json(),
                    ),
                ],
            )
        else:
            raise ValueError(f"Unsupported response type: {type(response)}")
