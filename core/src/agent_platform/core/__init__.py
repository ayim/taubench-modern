"""This package defines the core data types and interfaces for the agent-server.

It includes modules for prompts, threads, kernel interfaces, kernel, memory,
and tools, providing a structured way to represent and interact with different
aspects of the agent system.
"""

from agent_platform.core import (
    actions,
    agent,
    agent_architectures,
    kernel,
    kernel_interfaces,
    memory,
    payloads,
    prompts,
    runs,
    storage,
    thread,
    tools,
)
from agent_platform.core.kernel import Kernel
from agent_platform.core.mcp.mcp_server import MCPServer, MCPServerSource
from agent_platform.core.user import User

__version__ = "1.1.0"

__all__ = [
    "Kernel",
    "MCPServer",
    "MCPServerSource",
    "User",
    "actions",
    "agent",
    "agent_architectures",
    "kernel",
    "kernel_interfaces",
    "memory",
    "payloads",
    "prompts",
    "runs",
    "storage",
    "thread",
    "tools",
]
