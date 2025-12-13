from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from agent_platform.core.kernel_interfaces.thread_state import ThreadMessageWithThreadState
from agent_platform.core.thread.content import ThreadQuickActionsContent, ThreadVegaChartContent

WidgetStatus = Literal["detected", "generating", "done", "error"]
WidgetKind = Literal["chart", "buttons"]
InlineWidgetContent = ThreadVegaChartContent | ThreadQuickActionsContent


@dataclass(slots=True)
class InlineWidget:
    widget_id: str
    kind: WidgetKind
    description: str
    status: WidgetStatus = "detected"
    thinking: str = ""
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="milliseconds"))
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="milliseconds"))

    def to_metadata(self) -> dict[str, Any]:
        return {
            "id": self.widget_id,
            "kind": self.kind,
            "description": self.description,
            "status": self.status,
            "thinking": self.thinking,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def touch(self) -> None:
        self.updated_at = datetime.now(UTC).isoformat(timespec="milliseconds")


class InlineWidgetManager:
    """
    Tracks inline widget requests for the current in-flight agent message.
    """

    def __init__(self, message: ThreadMessageWithThreadState) -> None:
        self.message = message
        self._widgets: dict[str, InlineWidget] = {}
        self._descriptions_seen: set[tuple[WidgetKind, str]] = set()
        self._widget_content: dict[str, InlineWidgetContent] = {}

    async def ensure_widget(
        self,
        kind: WidgetKind,
        description: str,
        widget_id: str | None = None,
    ) -> InlineWidget:
        """
        Ensure a widget entry exists for the given kind+description.
        Returns the existing widget or creates a new one.
        """
        if widget_id and widget_id in self._widgets:
            return self._widgets[widget_id]

        key = (kind, description.strip())
        for widget in self._widgets.values():
            if (widget.kind, widget.description.strip()) == key:
                return widget

        widget = InlineWidget(
            widget_id=widget_id or str(uuid4()),
            kind=kind,
            description=description.strip(),
        )
        self._widgets[widget.widget_id] = widget
        self._descriptions_seen.add(key)
        # Create placeholder thread content so UI can render a loading block
        placeholder: InlineWidgetContent
        if kind == "chart":
            placeholder = ThreadVegaChartContent(
                chart_spec_raw="{}",
                sub_type="vega-lite",
            )
        else:
            from agent_platform.core.thread.content import (
                ThreadQuickActionContent,
                ThreadQuickActionsContent,
            )

            placeholder = ThreadQuickActionsContent(
                actions=[ThreadQuickActionContent(label="Loading...", value="")],
                completed=False,
            )

        placeholder.widget_id = widget.widget_id
        placeholder.description = widget.description
        placeholder.status = "generating"
        placeholder.completed = False
        self._widget_content[widget.widget_id] = placeholder
        self.message._message.content.append(placeholder)
        await self.message.stream_delta()
        return widget

    def update_status(self, widget_id: str, status: WidgetStatus, error: str | None = None) -> None:
        widget = self._widgets.get(widget_id)
        if not widget:
            return
        widget.status = status
        widget.error = error
        widget.touch()
        content = self._widget_content.get(widget_id)
        if content:
            content.status = status
            content.error = error

    def append_thinking(self, widget_id: str, chunk: str) -> None:
        widget = self._widgets.get(widget_id)
        if not widget or not chunk:
            return
        widget.thinking += chunk
        widget.touch()
        content = self._widget_content.get(widget_id)
        if content:
            content.thinking = widget.thinking

    async def apply_final_chart(
        self,
        widget_id: str,
        chart: ThreadVegaChartContent,
        *,
        description: str,
    ) -> None:
        widget = self._widgets.get(widget_id)
        if widget:
            widget.status = "done"
            widget.result = {
                "spec": chart.chart_spec,
                "chart_spec_raw": chart.chart_spec_raw,
                "sub_type": chart.sub_type,
            }
            widget.error = None
            widget.description = description
            widget.touch()

        existing = self._widget_content.get(widget_id)
        target = chart if not isinstance(existing, ThreadVegaChartContent) else existing
        target.widget_id = widget_id
        target.description = description
        target.status = "done"
        target.error = None
        target.thinking = widget.thinking if widget else ""
        target.completed = True
        target.chart_spec_raw = chart.chart_spec_raw
        target.sub_type = chart.sub_type
        # Refresh parsed spec
        target._chart_spec = chart.chart_spec  # type: ignore[attr-defined]

        if existing is None:
            self._widget_content[widget_id] = target
            self.message._message.content.append(target)

        await self.message.stream_delta()

    async def apply_final_buttons(
        self,
        widget_id: str,
        quick_actions: ThreadQuickActionsContent,
        *,
        description: str,
    ) -> None:
        widget = self._widgets.get(widget_id)
        if widget:
            widget.status = "done"
            widget.error = None
            widget.description = description
            widget.touch()

        existing = self._widget_content.get(widget_id)
        target = existing if isinstance(existing, ThreadQuickActionsContent) else quick_actions
        target.widget_id = widget_id
        target.description = description
        target.status = "done"
        target.error = None
        target.thinking = widget.thinking if widget else ""
        target.completed = True
        target.actions = quick_actions.actions

        if existing is None or not isinstance(existing, ThreadQuickActionsContent):
            self._widget_content[widget_id] = target
            self.message._message.content.append(target)

        await self.message.stream_delta()

    def set_error(self, widget_id: str, error: str) -> None:
        self.update_status(widget_id, "error", error=error)

    def clear(self) -> None:
        """
        Clears all widgets (used on rollback).
        """
        self._widgets.clear()
        self._descriptions_seen.clear()
        self._widget_content.clear()

    def get_widget(self, widget_id: str) -> InlineWidget | None:
        return self._widgets.get(widget_id)

    def get_content(self, widget_id: str) -> ThreadVegaChartContent | ThreadQuickActionsContent | None:
        return self._widget_content.get(widget_id)
