from __future__ import annotations

import re
from collections.abc import Callable

from agent_platform.core.responses.streaming import TextResponseStreamSink

from .manager import InlineWidgetManager


def chart_detection_sink(  # noqa: C901
    *,
    manager: InlineWidgetManager,
    spawn_chart: Callable[[str, str], None],
    spawn_buttons: Callable[[str, str], None] | None = None,
) -> TextResponseStreamSink:
    """
    Returns a stream sink that detects `<chart description="..."/>` tags in raw text.

    We tolerate chunked streams by keeping a running buffer and deduplicate on the
    start index of each matched tag.
    """

    buffer: str = ""
    processed_starts: set[int] = set()
    # <chart .../> or <buttons .../>
    tag_regex = re.compile(r"<chart\b[^>]*?/?>|<buttons\b[^>]*?/?>", flags=re.IGNORECASE)

    def _parse_description(tag: str) -> str | None:
        desc_match = re.search(
            r'description\s*=\s*"([^"]+)"|description\s*=\s*\'([^\']+)\'',
            tag,
            flags=re.IGNORECASE,
        )
        if not desc_match:
            return None
        # group 1 (double quotes) or group 2 (single quotes)
        return desc_match.group(1) or desc_match.group(2)

    def _parse_id(tag: str) -> str | None:
        id_match = re.search(
            r'id\s*=\s*"([^"]+)"|id\s*=\s*\'([^\']+)\'',
            tag,
            flags=re.IGNORECASE,
        )
        if not id_match:
            return None
        return id_match.group(1) or id_match.group(2)

    async def _scan() -> None:
        nonlocal buffer
        for match in tag_regex.finditer(buffer):
            if match.start() in processed_starts:
                continue
            processed_starts.add(match.start())
            description = _parse_description(match.group(0))
            widget_id = _parse_id(match.group(0))
            if not description or not widget_id:
                continue
            is_buttons = match.group(0).lower().startswith("<buttons")
            if is_buttons and spawn_buttons:
                widget = await manager.ensure_widget("buttons", description, widget_id=widget_id)
                spawn_buttons(widget.widget_id, widget.description)
            elif not is_buttons:
                widget = await manager.ensure_widget("chart", description, widget_id=widget_id)
                spawn_chart(widget.widget_id, widget.description)

        # Keep a manageable tail in case of very large buffers; this preserves any
        # partial tag across chunk boundaries.
        buffer = buffer[-2048:]

    async def _on_text(text: str) -> None:
        nonlocal buffer
        buffer += text
        await _scan()

    # Treat start/partial/complete the same for detection purposes.
    return TextResponseStreamSink(
        on_text_start=_on_text,
        on_text_partial=_on_text,
        on_text_complete=_on_text,
    )
