import logging

from agent_platform.architectures.default.state import ArchState
from agent_platform.core import Kernel
from agent_platform.core import agent_architectures as aa

logger = logging.getLogger(__name__)


@aa.entrypoint
async def entrypoint_exp_3(kernel: Kernel, state: ArchState) -> ArchState:
    try:
        logger.info("Running experimental architecture 3")
        return state
    except Exception as e:
        logger.error("Error running experimental architecture 3", exc_info=True)
        raise e
    finally:
        logger.info("Experimental architecture 3 completed")
