import json
import logging
from typing import Any
from uuid import uuid4

from agent_platform.architectures.experimental.violet.docintel.types import (
    DocCard,
)
from agent_platform.architectures.experimental.violet.prompts import build_prompt
from agent_platform.architectures.experimental.violet.state import VioletState
from agent_platform.core.kernel import Kernel
from agent_platform.core.kernel_interfaces.thread_state import ThreadMessageWithThreadState
from agent_platform.core.thread.content import ThreadToolUsageContent

logger = logging.getLogger(__name__)


class SchemaGenerator:
    """
    Handles the LLM interaction for inferring a JSON schema from document samples.
    """

    def __init__(self, kernel: Kernel, state: VioletState):
        self.kernel = kernel
        self.state = state

    async def infer_and_apply(
        self,
        card: DocCard,
        message: ThreadMessageWithThreadState,
        instructions: str = "",
    ) -> dict[str, Any]:
        """
        Main entrypoint:
        1. Emits a 'running' tool usage event (so UI shows activity).
        2. Calls the LLM to infer the schema.
        3. Updates the Card state.
        4. Emits a 'finished' tool usage event.
        """
        # Safety check: if we already have a schema and no new instructions, skip.
        if isinstance(card.json_schema, dict) and not instructions:
            return {
                "schema": card.json_schema,
                "source": "cached",
                "message": "Schema already inferred.",
            }

        try:
            # Prepare Payload & Run Inference
            logger.info(
                f"doc_int.infer_schema.start file_ref={card.file_ref} revision={card.revision}",
            )

            schema_result = await self._run_llm_inference(card, message, instructions)

            # Apply State
            if schema_result:
                card.json_schema = schema_result
                card.revision += 1
                self.state.doc_int.revision += 1

                # Success output
                result_payload = {"schema": schema_result}
                return result_payload
            else:
                raise ValueError("Model returned empty or invalid JSON")

        except Exception as exc:
            logger.exception(f"Schema inference failed file_ref={card.file_ref} error={exc!s}")
            error_payload = {"error_code": "inference_failed", "message": str(exc)}

            # Failure output
            return error_payload

    async def _run_llm_inference(
        self, card: DocCard, message: ThreadMessageWithThreadState, instructions: str
    ) -> dict[str, Any] | None:
        """
        Builds the prompt, streams the response, and parses the JSON.
        """
        # Summarize pages to avoid blowing up context window
        pages_payload = []
        for page in card.sampled_pages:
            parsed_summary = (
                self._summarize_parse_response(page.parse_data) if page.parse_data else None
            )
            pages_payload.append(
                {
                    "page": page.page,
                    "status": page.status,
                    "summary": page.summary,
                    "parse_sample": parsed_summary,
                }
            )

        payload = {
            "file_ref": card.file_ref,
            "comments": [c.comment for c in card.comments],
            "pages": pages_payload,
            "instructions": instructions.strip(),
        }

        # Inject payload into state for Jinja rendering
        self.state.doc_int.prompt_payload = json.dumps(payload, indent=2)

        try:
            prompt = await build_prompt(
                kernel=self.kernel,
                state=self.state,
                prompt_path="prompts/docint",
            )
        finally:
            # Always clear the payload so it doesn't leak into other prompts
            self.state.doc_int.prompt_payload = ""

        platform, model = await self.kernel.get_platform_and_model(model_type="llm")

        # Stream response
        full_response = None
        async with platform.stream_response(prompt, model) as stream:
            # Pipe reasoning to the UI immediately
            if message:
                await stream.pipe_to(message.sinks.reasoning)
            full_response = stream.reassembled_response

        if not full_response:
            return None

        # Parse JSON
        text_parts = [c.text for c in full_response.content if c.kind == "text"]
        raw_text = text_parts[0] if text_parts else ""
        cleaned_json = self._strip_code_fences(raw_text)

        # Mark any reasoning generated in this process as "ignored" so we don't
        # slice it back into the context during our tool loop
        reasoning_ids = [
            c.response_id for c in full_response.content if c.kind == "reasoning" and c.response_id
        ]
        if reasoning_ids:
            self.state.ignored_reasoning_ids.extend(reasoning_ids)

        try:
            return json.loads(cleaned_json)
        except Exception:
            logger.warning(f"Failed to parse schema JSON raw_text={raw_text}")
            return None

    async def emit_tool_start(
        self, message: ThreadMessageWithThreadState, file_ref: str, instructions: str
    ) -> ThreadToolUsageContent:
        """Creates the 'running' tool usage bubble in the chat."""
        # Ensure a thought is in place so streamed reasoning appears before the tool bubble.
        message.new_thought("")
        tool_call_id = f"auto_infer_schema_{uuid4()}"
        usage = ThreadToolUsageContent(
            name="infer_schema",
            tool_call_id=tool_call_id,
            arguments_raw=json.dumps({"file_ref": file_ref, "instructions": instructions}),
            sub_type="aa-internal",
            status="running",
            metadata={"auto_invoked": True},
        )
        message.message.content.append(usage)
        await message.stream_delta()
        return usage

    async def emit_tool_finish(
        self,
        message: ThreadMessageWithThreadState,
        usage: ThreadToolUsageContent,
        file_ref: str,
        result: dict[str, Any],
        is_error: bool = False,
    ) -> None:
        """Updates the tool usage bubble to 'finished' or 'failed'."""
        from datetime import UTC, datetime

        usage.complete = True
        usage.ended_at = datetime.now(UTC)
        if is_error:
            usage.status = "failed"
            usage.error = result.get("message") or "Unknown error"
        else:
            usage.status = "finished"
            usage.result = json.dumps(
                {"file_ref": file_ref, "schema": result.get("schema")},
                ensure_ascii=False,
            )
        await message.stream_delta()

    def _strip_code_fences(self, text: str) -> str:
        """Remove Markdown code fences."""
        if "```" not in text:
            return text
        parts = text.split("```")
        if len(parts) < 2:  # noqa: PLR2004
            return text
        candidate = parts[1]
        if candidate.strip().startswith("json"):
            candidate = candidate.split("\n", 1)[1] if "\n" in candidate else candidate
        return candidate.strip()

    def _summarize_parse_response(self, parse_response: Any) -> dict[str, Any]:
        """
        Trims a Reducto ParseResponse to a compact sample for the LLM context window.
        Keeps the structure but limits the number of blocks/chunks.
        """
        try:
            if hasattr(parse_response, "model_dump"):
                data = parse_response.model_dump()
            else:
                data = dict(parse_response)
        except Exception:
            return {}

        result = data.get("result") if isinstance(data, dict) else {}
        chunks = result.get("chunks") if isinstance(result, dict) else None
        if not isinstance(chunks, list):
            return data

        trimmed_chunks = []
        for chunk in chunks[:6]:  # Limit chunks
            if not isinstance(chunk, dict):
                continue
            trimmed_chunk = {
                "type": chunk.get("type"),
                "content": chunk.get("content"),
            }
            blocks = chunk.get("blocks")
            if isinstance(blocks, list):
                trimmed_blocks = []
                for block in blocks[:8]:  # Limit blocks per chunk
                    if not isinstance(block, dict):
                        continue
                    trimmed_blocks.append(
                        {
                            "type": block.get("type"),
                            "content": block.get("content"),
                            # Keep page number for citation logic
                            "page": (
                                block.get("bbox", {}).get("page")
                                if isinstance(block.get("bbox"), dict)
                                else None
                            ),
                        }
                    )
                if trimmed_blocks:
                    trimmed_chunk["blocks"] = trimmed_blocks
            trimmed_chunks.append(trimmed_chunk)

        data["result"] = {"chunks": trimmed_chunks}
        return data
