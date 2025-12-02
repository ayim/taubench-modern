"""This module defines the interfaces that the kernel exposes
to Agent Architectures (AAs).

These interfaces provide a way for AAs to interact with the
agent-server, accessing functionality such as memory management,
tool execution, and user interaction.
"""

from agent_platform.core.kernel_interfaces.converters import ConvertersInterface
from agent_platform.core.kernel_interfaces.data_frames import DataFramesInterface
from agent_platform.core.kernel_interfaces.documents import DocumentsInterface
from agent_platform.core.kernel_interfaces.events import EventsInterface
from agent_platform.core.kernel_interfaces.files import FilesInterface
from agent_platform.core.kernel_interfaces.memory import MemoryInterface
from agent_platform.core.kernel_interfaces.model_platform import PlatformInterface
from agent_platform.core.kernel_interfaces.otel import OTelInterface
from agent_platform.core.kernel_interfaces.prompts import PromptsInterface
from agent_platform.core.kernel_interfaces.runbook import RunbookInterface
from agent_platform.core.kernel_interfaces.storage import StorageInterface
from agent_platform.core.kernel_interfaces.thread_state import ThreadStateInterface
from agent_platform.core.kernel_interfaces.tools import ToolsInterface
from agent_platform.core.kernel_interfaces.user_interactions import (
    UserInteractionsInterface,
)
from agent_platform.core.kernel_interfaces.work_item import WorkItemInterface

__all__ = [
    "ConvertersInterface",
    "DataFramesInterface",
    "DocumentsInterface",
    "EventsInterface",
    "FilesInterface",
    "MemoryInterface",
    "OTelInterface",
    "PlatformInterface",
    "PromptsInterface",
    "RunbookInterface",
    "StorageInterface",
    "ThreadStateInterface",
    "ToolsInterface",
    "UserInteractionsInterface",
    "WorkItemInterface",
]
