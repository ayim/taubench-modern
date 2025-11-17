from importlib.metadata import version

from agent_platform.architectures.experimental.consistency.state import ConsistencyArchState
from agent_platform.core import Kernel
from agent_platform.core import agent_architectures as aa

__author__ = "Sema4.ai Engineering"
__copyright__ = "Copyright 2025, Sema4.ai"
__license__ = "Proprietary"
__summary__ = "Consistency-focused experimental agent architecture"
__version__ = version("agent_platform_architectures_experimental")


@aa.entrypoint
async def entrypoint_exp_2(kernel: Kernel, state: ConsistencyArchState) -> ConsistencyArchState:
    from agent_platform.architectures.experimental.consistency.entrypoint import (
        entrypoint_consistency,
    )

    return await entrypoint_consistency(kernel, state)
