from typing import Any

import pytest

from agent_platform.server.kernel.data_frames import (
    AgentServerDataFramesInterface,
    SqlGeneration,
)
from agent_platform.server.kernel.sql import (
    AgenticSqlStrategy,
    LegacySqlStrategy,
)


class MockAgent:
    """Mock agent for testing."""

    def __init__(self, extra: dict[str, Any]):
        self.extra = extra


class MockKernel:
    """Mock kernel for testing."""

    def __init__(self, agent: MockAgent):
        self.agent = agent


class TestAgentServerDataFramesInterface:
    """Tests for AgentServerDataFramesInterface._get_sql_generation_mode."""

    @pytest.mark.parametrize(
        "test_case",
        [
            ("legacy", SqlGeneration.LEGACY),
            ("agentic", SqlGeneration.AGENTIC),
            ("", SqlGeneration.LEGACY),
            ("AGENTIC", SqlGeneration.AGENTIC),
            ("LEGACY", SqlGeneration.LEGACY),
            ("invalid", ValueError()),
        ],
    )
    def test_sql_generation_mode(self, test_case: tuple[str, SqlGeneration]):
        """Test that default mode is LEGACY when sql_generation is not specified."""
        # Arrange
        if test_case[0]:
            mock_agent = MockAgent(extra={"agent_settings": {"sql_generation": test_case[0]}})
        else:
            mock_agent = MockAgent(extra={"agent_settings": {}})

        mock_kernel = MockKernel(agent=mock_agent)
        interface = AgentServerDataFramesInterface()
        interface.attach_kernel(mock_kernel)  # type: ignore[arg-type]

        if isinstance(test_case[1], Exception):
            with pytest.raises(type(test_case[1])):
                interface._get_sql_generation_mode()
        else:
            result = interface._get_sql_generation_mode()
            assert result == test_case[1]

    def test_legacy_strategy_creation(self):
        """Test that legacy mode creates LegacySqlStrategy."""
        strategy = LegacySqlStrategy()
        assert strategy.get_tools() == ()

    def test_agentic_strategy_creation(self):
        """Test that agentic mode creates AgenticSqlStrategy."""
        strategy = AgenticSqlStrategy()
        assert len(strategy.get_tools()) == 1
