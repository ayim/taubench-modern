"""
Experimental architectures for running agents.
"""

from importlib.metadata import version

__author__ = "Sema4.ai Engineering"
__copyright__ = "Copyright 2025, Sema4.ai"
__license__ = "Proprietary"
__summary__ = "Experimental architecture for the Agent Platform"
__version__ = version("agent_platform_architectures_experimental")

from agent_platform.architectures.experimental.exp_1 import entrypoint_exp_1
from agent_platform.architectures.experimental.exp_2 import entrypoint_exp_2
from agent_platform.architectures.experimental.exp_3 import entrypoint_exp_3

__all__ = [
    "entrypoint_exp_1",
    "entrypoint_exp_2",
    "entrypoint_exp_3",
]
