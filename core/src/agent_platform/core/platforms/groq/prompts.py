"""Prompt helpers for the Groq platform."""

import logging
from dataclasses import dataclass
from typing import Any

from agent_platform.core.platforms.openai.prompts import OpenAIPrompt

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GroqPrompt(OpenAIPrompt):
    """Prompt for Groq's OpenAI-compatible Responses API."""

    def as_platform_request(self, model: str, stream: bool = False) -> dict[str, Any]:
        """Convert the prompt to a Groq Responses API request."""
        logger.debug("Using Groq model: %s", model)
        request = super().as_platform_request(model, stream=stream)

        # Groq's Responses API is largely compatible with OpenAI's, but it does
        # not yet support the `include` or `store` parameters. Remove them if
        # present to avoid HTTP 400 responses.
        request.pop("include", None)
        request.pop("store", None)
        if request.get("reasoning") is None:
            request.pop("reasoning", None)

        original_input = request.get("input")
        sanitized_input = self._sanitize_input_items(original_input)
        if sanitized_input is not None:
            if original_input and not sanitized_input:
                raise ValueError(
                    "Groq request sanitization removed all input content. "
                    "Review prompt construction."
                )
            request["input"] = sanitized_input
            if logger.isEnabledFor(logging.DEBUG):
                preview: list[dict[str, Any]] = []
                for item in sanitized_input:
                    if not isinstance(item, dict):
                        preview.append({"unexpected_item": type(item).__name__})
                        continue
                    entry: dict[str, Any] = {}
                    if "type" in item:
                        entry["type"] = item["type"]
                    if "role" in item:
                        entry["role"] = item["role"]
                    content = item.get("content")
                    if isinstance(content, list):
                        entry["content_types"] = [
                            c.get("type") if isinstance(c, dict) else type(c).__name__
                            for c in content
                        ]
                    preview.append(entry)
                logger.debug("Groq sanitized input preview: %s", preview)

        # OpenAIPrompt strips namespace prefixes (e.g. 'meta-llama/') when building the
        # internal request. Groq requires the fully-qualified identifier, so we restore it.
        request["model"] = model
        return request

    @staticmethod
    def _sanitize_input_items(input_items: Any) -> list[dict[str, Any]] | None:
        """Remove unsupported content/tool fields before sending to Groq."""
        if not isinstance(input_items, list):
            return None

        allowed_content_keys = {
            "input_text": {"type", "text"},
            "output_text": {"type", "text"},
            "input_image": {"type", "image_url", "image_base64", "detail"},
        }
        allowed_tool_item_fields = {
            "function_call": {"type", "id", "call_id", "name", "arguments"},
            "function_call_output": {"type", "id", "call_id", "output"},
        }

        sanitized_items: list[dict[str, Any]] = []
        for item in input_items:
            item_dict = GroqPrompt._model_dump_generic(item)
            tool_payload = GroqPrompt._sanitize_tool_item(item_dict, allowed_tool_item_fields)
            if tool_payload is not None:
                sanitized_items.append(tool_payload)
                continue

            message_payload = GroqPrompt._sanitize_message_item(item_dict, allowed_content_keys)
            if message_payload is not None:
                sanitized_items.append(message_payload)

        return sanitized_items

    @staticmethod
    def _sanitize_tool_item(
        item_dict: dict[str, Any],
        allowed_tool_item_fields: dict[str, set[str]],
    ) -> dict[str, Any] | None:
        item_type = item_dict.get("type")
        if not isinstance(item_type, str):
            return None

        allowed_keys = allowed_tool_item_fields.get(item_type)
        if not allowed_keys:
            return None

        payload = {key: item_dict[key] for key in allowed_keys if item_dict.get(key) is not None}
        return payload or None

    @staticmethod
    def _sanitize_message_item(
        item_dict: dict[str, Any],
        allowed_content_keys: dict[str, set[str]],
    ) -> dict[str, Any] | None:
        role = item_dict.get("role")
        if not role:
            return None

        sanitized_item: dict[str, Any] = {"role": role}
        content_list = item_dict.get("content")
        if isinstance(content_list, list):
            sanitized_content: list[dict[str, Any]] = []
            for part in content_list:
                part_dict = GroqPrompt._model_dump_generic(part)
                part_dict.pop("annotations", None)
                content_type = part_dict.get("type")
                allowed_keys = (
                    allowed_content_keys.get(content_type)
                    if isinstance(content_type, str)
                    else None
                )
                if not allowed_keys:
                    continue
                if content_type in {"input_text", "output_text"}:
                    text_value = part_dict.get("text")
                    if not text_value:
                        continue
                    sanitized_content.append({"type": "input_text", "text": text_value})
                    continue
                cleaned = {
                    key: part_dict[key] for key in allowed_keys if part_dict.get(key) is not None
                }
                if cleaned:
                    sanitized_content.append(cleaned)
            if sanitized_content:
                sanitized_item["content"] = sanitized_content

        return sanitized_item if sanitized_item.get("content") else None

    @staticmethod
    def _model_dump_generic(obj: Any) -> dict[str, Any]:
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if isinstance(obj, dict):
            return obj
        return dict(obj)
