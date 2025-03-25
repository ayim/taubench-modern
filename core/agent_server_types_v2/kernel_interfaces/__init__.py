"""This module defines the interfaces that the kernel exposes
to Agent Architectures (AAs).

These interfaces provide a way for AAs to interact with the
agent-server, accessing functionality such as memory management,
tool execution, and user interaction.
"""

from agent_server_types_v2.kernel_interfaces.converters import ConvertersInterface
from agent_server_types_v2.kernel_interfaces.events import EventsInterface
from agent_server_types_v2.kernel_interfaces.files import FilesInterface
from agent_server_types_v2.kernel_interfaces.memory import MemoryInterface
from agent_server_types_v2.kernel_interfaces.model_platform import PlatformInterface
from agent_server_types_v2.kernel_interfaces.otel import OTelInterface
from agent_server_types_v2.kernel_interfaces.prompts import PromptsInterface
from agent_server_types_v2.kernel_interfaces.runbook import RunbookInterface
from agent_server_types_v2.kernel_interfaces.storage import StorageInterface
from agent_server_types_v2.kernel_interfaces.thread_state import ThreadStateInterface
from agent_server_types_v2.kernel_interfaces.tools import ToolsInterface
from agent_server_types_v2.kernel_interfaces.user_interactions import (
    UserInteractionsInterface,
)

__all__ = [
    "ConvertersInterface",
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
]
