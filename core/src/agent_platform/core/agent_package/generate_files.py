from agent_platform.core.agent import Agent
from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel


async def generate_agent_package_files(agent: Agent, semantic_data_models: list[SemanticDataModel]):
    """Generate agent package files based on Agent state."""
    raise NotImplementedError("Not implemented")
