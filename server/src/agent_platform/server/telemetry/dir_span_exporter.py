# ruff: noqa: C901
from __future__ import annotations

import json
import typing
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from opentelemetry.sdk.trace.export import (
    SpanExporter,
    SpanExportResult,
)
from structlog import get_logger

if typing.TYPE_CHECKING:
    from opentelemetry.sdk.trace import ReadableSpan

logger = get_logger(__name__)


class DirSpanExporter(SpanExporter):
    """
    A span exporter that exports traces to a directory.

    The output is a directory with the following structure:
    <output_dir>/
        <i:03d>_<agent_name>-<thread_name>/
            <name>_<status>_<duration>_<timestamp>.txt
            <name>_<status>_<duration>_<timestamp>.txt
            ...
    """

    # Maximum number of entries to keep in the disk (after this is reached the oldest ones are
    # deleted when a new entry is added).
    max_entries_in_disk = 100

    # Maximum number of trace id -> folder mappings to keep in memory.
    max_trace_id_to_folder_entries_in_memory = 200

    # Maximum length for a single line in the output.
    max_len_for_same_line = 150

    # Prefix for the output.
    prefix = "  "

    def __init__(self, output_dir: Path) -> None:
        """
        Args:
            output_dir: The directory to export traces to.
        """

        self._output_dir = output_dir
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._trace_id_to_folder: dict[int, Path] = {}

        self._span_name_to_attr_name_to_format_func = {
            "format_prompt": {
                "input.value": self._key_and_dict_to_str_simple,
                "output.value": self._key_and_dict_to_str_simple,
            },
        }

    def _get_dir_name(self, directory: Path, name: str) -> Path:
        import asyncio
        import os
        from functools import partial

        from sema4ai.common.text import slugify

        name = slugify(name)

        found_names = os.listdir(directory)

        # Now, we want to generate names following the pattern:
        # <i:03d>_<name>
        # So, go through the current names and find the highest i.
        highest_i = 0
        found_i_to_name: dict[int, list[str]] = {}
        number_of_entries = 0
        for found_name in found_names:
            try:
                i = int(found_name.split("_")[0])
            except Exception:
                continue  # Not a valid name, skip.
            else:
                highest_i = max(highest_i, i)
                found_i_to_name.setdefault(i, []).append(found_name)
                number_of_entries += 1

        new_name = f"{highest_i + 1:03d}_{name}"

        if number_of_entries >= self.max_entries_in_disk:
            # If we have too many entries, we need to delete the oldest ones
            # (but we do it in a thread to avoid blocking the main thread).
            loop = asyncio.get_running_loop()
            func = partial(
                self._remove_oldest_entries_in_thread,
                directory,
                found_i_to_name,
                number_of_entries,
                self.max_entries_in_disk,
            )
            # Run in the default executor in a thread.
            loop.run_in_executor(None, func)
        return directory / new_name

    @staticmethod
    def _remove_oldest_entries_in_thread(
        directory: Path,
        found_i_to_name: dict[int, list[str]],
        number_of_entries: int,
        max_entries: int,
    ) -> None:
        try:
            import shutil

            while number_of_entries >= max_entries:
                # We have too many entries, we need to delete the oldest ones.
                for key, names in sorted(found_i_to_name.items()):
                    while names and number_of_entries >= max_entries:
                        name = names.pop(0)
                        path = directory / name
                        logger.info("Removing trace dir entry", path=path)
                        shutil.rmtree(path, ignore_errors=True)
                        number_of_entries -= 1

                    found_i_to_name.pop(key)
        except Exception:
            logger.exception("Error removing oldest entries in thread")

    def _get_folder_output(self, trace_id: int, agent_name: str, thread_name: str) -> Path | None:
        folder = self._trace_id_to_folder.get(trace_id)
        if folder:
            return folder

        if agent_name == "unknow" or thread_name == "unknown":
            # We only start tracing after we have a valid agent and thread.
            return None

        folder = self._get_dir_name(directory=self._output_dir, name=f"{agent_name}-{thread_name}")
        folder.mkdir(parents=True, exist_ok=True)

        self._trace_id_to_folder[trace_id] = folder

        # We don't want ever-growing caches!
        max_items = self.max_trace_id_to_folder_entries_in_memory
        if len(self._trace_id_to_folder) > max_items:
            # FIFO should be fine for us.
            del self._trace_id_to_folder[next(iter(self._trace_id_to_folder))]

        return folder

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        import datetime

        from sema4ai.common.text import slugify

        for span in spans:
            if not span.context:
                continue
            trace_id = span.context.trace_id

            name = slugify(span.name)
            now = datetime.datetime.now()
            curtime_as_str = now.strftime("%Y%m%d_%H%M%S")

            status = str(span.status.status_code.name)

            start_time_ns = span.start_time
            end_time_ns = span.end_time
            if start_time_ns and end_time_ns:
                duration = end_time_ns - start_time_ns
                duration_s = duration / 1e9
                duration_str = f"{duration_s:.0f}s"
            else:
                duration_str = "NA"

            agent_name = "unknown"
            thread_name = "unknown"

            if span.attributes:
                agent_name = str(span.attributes.get("agent_name", "unknown"))
                thread_name = str(span.attributes.get("thread_name", "unknown"))

            folder = self._get_folder_output(trace_id, agent_name, thread_name)
            if folder is None:
                continue

            contents = self._span_to_pretty_str(span)
            with open(
                folder / f"{name}_{status}_{duration_str}_{curtime_as_str}.txt",
                "w",
                encoding="utf-8",
            ) as f:
                f.write(contents)

        return SpanExportResult.SUCCESS

    def _span_to_pretty_str(self, span: ReadableSpan) -> str:
        from opentelemetry.sdk import util

        start_time = span.start_time
        end_time = span.end_time

        contents: list[str] = []
        status_name = span.status.status_code.name
        status_description = span.status.description

        contents.append(f"Name: {span.name}")
        contents.append(f"Status Code: {status_name}")

        if status_description:
            contents.append(f"Status Description: {status_description}")

        if start_time:
            contents.append(f"Start Time: {util.ns_to_iso_str(start_time)}")

        if end_time:
            contents.append(f"End Time: {util.ns_to_iso_str(end_time)}")

        if start_time and end_time:
            duration_ns = end_time - start_time
            duration_s = duration_ns / 1e9
            duration_str = f"{duration_s:.2f}s"
            contents.append(f"Duration: {duration_str}")

        if span.events:
            contents.append("==== Events ====")
            for event in span.events:
                contents.append(f"Event: {event.name}")
                contents.append(f"Timestamp: {util.ns_to_iso_str(event.timestamp)}")
                if event.attributes:
                    for key, value in event.attributes.items():
                        contents.append(f"{key}: {value}")

        if span.attributes:
            contents.append("==== Attributes ====")
            attr_name_to_format_func = (
                self._span_name_to_attr_name_to_format_func.get(span.name) or {}
            )

            for key, value in span.attributes.items():
                func = attr_name_to_format_func.get(key)
                if not func:
                    func = self._key_and_dict_to_str_pretty
                contents.append(func(key, value))
        return "\n".join(contents)

    @classmethod
    def _key_and_dict_to_str_pretty(cls, key: str, value: Any) -> str:
        from agent_platform.server.telemetry.pretty_print import pretty_print

        loaded_value = value
        if isinstance(value, str):
            try:
                loaded_value = json.loads(value)
            except json.JSONDecodeError:
                # Not valid json, just print the raw values with the default
                # formatter.
                pass

        s = pretty_print(str(loaded_value))
        return cls._key_val_as_string(key, s)

    @classmethod
    def _key_val_as_string(cls, key: str, s: Any) -> str:
        from textwrap import indent

        if not isinstance(s, str):
            s = str(s)

        prefix = cls.prefix
        if len(s) < cls.max_len_for_same_line and "\n" not in s:
            return f"{key}: {indent(s, prefix).lstrip()}"
        else:
            return f"{key}:\n{indent(s, prefix)}"

    @classmethod
    def _key_and_dict_to_str_simple(cls, key: str, value: Any) -> str:
        loaded_value = value
        if isinstance(value, str):
            try:
                loaded_value = json.loads(value)
            except json.JSONDecodeError:
                # Not valid json, just print the raw values with the default
                # formatter.
                pass

        if isinstance(loaded_value, dict):
            s = cls._dict_to_str_simple(loaded_value)
        else:
            s = loaded_value
        return cls._key_val_as_string(key, s)

    @classmethod
    def _dict_to_str_simple(cls, value: dict) -> str:
        contents: list[str] = []
        for key, item in value.items():
            contents.append(cls._key_and_dict_to_str_simple(key, item))
        return "\n".join(contents)

    def shutdown(self) -> None:
        pass
