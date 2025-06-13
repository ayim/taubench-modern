import os
from unittest.mock import MagicMock, patch

import pytest

from agent_platform.core.agent.observability_config import ObservabilityConfig
from agent_platform.core.conditional_langsmith_processor import ConditionalLangSmithProcessor


@pytest.fixture
def processor():
    """Create a fresh ConditionalLangSmithProcessor for each test."""
    return ConditionalLangSmithProcessor()


@pytest.fixture
def mock_span():
    """Create a mock span with configurable attributes."""
    span = MagicMock()
    span.name = "test_span"
    span.context.trace_id = 0x12345
    span.context.span_id = 0x67890
    span.attributes = {}
    return span


@pytest.fixture
def langsmith_config_a():
    """Create LangSmith config for project A."""
    return ObservabilityConfig(
        type="langsmith",
        api_key="key_a",
        api_url="https://api.smith.langchain.com",
        settings={"project_name": "project_a"},
    )


@pytest.fixture
def langsmith_config_b():
    """Create LangSmith config for project B."""
    return ObservabilityConfig(
        type="langsmith",
        api_key="key_b",
        api_url="https://api.smith.langchain.com",
        settings={"project_name": "project_b"},
    )


@pytest.fixture(autouse=True)
def reset_processor_and_env(monkeypatch):
    # Unset global env vars before each test
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
    monkeypatch.delenv("LANGCHAIN_ENDPOINT", raising=False)
    monkeypatch.delenv("LANGCHAIN_PROJECT", raising=False)
    ConditionalLangSmithProcessor.reset_instance()
    yield
    ConditionalLangSmithProcessor.reset_instance()


class TestConditionalLangSmithProcessor:
    """Test the ConditionalLangSmithProcessor routing logic."""

    def test_init(self, processor):
        """Test processor initialization."""
        assert len(processor._processors) == 0
        assert len(processor._signatures) == 0

    @patch("agent_platform.core.conditional_langsmith_processor.OTLPSpanExporter")
    @patch("agent_platform.core.conditional_langsmith_processor.BatchSpanProcessor")
    def test_add_or_update_config_success(
        self, mock_batch_processor, mock_exporter, processor, langsmith_config_a
    ):
        """Test successfully adding a LangSmith config."""
        result = processor.add_or_update_config("agent_123", langsmith_config_a)

        assert result is True
        assert "agent_123" in processor._processors
        assert "agent_123" in processor._signatures

        # Verify exporter was created with correct params
        mock_exporter.assert_called_once_with(
            endpoint="https://api.smith.langchain.com/otel/v1/traces",
            headers={"x-api-key": "key_a", "Langsmith-Project": "project_a"},
        )

    def test_add_or_update_config_missing_api_key(self, processor):
        """Test adding config without API key fails."""
        config = ObservabilityConfig(
            type="langsmith",
            api_key="",
            api_url="https://api.smith.langchain.com",
            settings={"project_name": "test"},
        )
        result = processor.add_or_update_config("agent_123", config)

        assert result is False
        assert "agent_123" not in processor._processors

    def test_add_or_update_config_missing_project(self, processor):
        """Test adding config without project name fails."""
        config = ObservabilityConfig(
            type="langsmith",
            api_key="test_key",
            api_url="https://api.smith.langchain.com",
            settings={},  # No project_name
        )
        result = processor.add_or_update_config("agent_123", config)

        assert result is False
        assert "agent_123" not in processor._processors

    @patch("agent_platform.core.conditional_langsmith_processor.OTLPSpanExporter")
    @patch("agent_platform.core.conditional_langsmith_processor.BatchSpanProcessor")
    def test_add_or_update_config_unchanged(
        self, mock_batch_processor, mock_exporter, processor, langsmith_config_a
    ):
        """Test adding identical config returns False on second call."""
        # Add config first time
        result1 = processor.add_or_update_config("agent_123", langsmith_config_a)
        assert result1 is True

        # Add same config again - should return False (no change)
        result2 = processor.add_or_update_config("agent_123", langsmith_config_a)
        assert result2 is False

        # Should only be called once
        mock_exporter.assert_called_once()

    @patch("agent_platform.core.conditional_langsmith_processor.OTLPSpanExporter")
    @patch("agent_platform.core.conditional_langsmith_processor.BatchSpanProcessor")
    def test_agent_id_routing(
        self, mock_batch_processor, mock_exporter, processor, langsmith_config_a, mock_span
    ):
        """Test routing spans by agent_id."""
        # Setup
        processor.add_or_update_config("agent_123", langsmith_config_a)
        mock_span.attributes = {"agent_id": "agent_123"}

        # Test
        processor.on_end(mock_span)

        # Verify
        mock_processor = processor._processors["agent_123"]
        mock_processor.on_end.assert_called_once_with(mock_span)

    @patch("agent_platform.core.conditional_langsmith_processor.OTLPSpanExporter")
    @patch("agent_platform.core.conditional_langsmith_processor.BatchSpanProcessor")
    def test_agent_dot_id_fallback_routing(
        self, mock_batch_processor, mock_exporter, processor, langsmith_config_a, mock_span
    ):
        """Test routing spans by agent.id fallback."""
        # Setup
        processor.add_or_update_config("agent_123", langsmith_config_a)
        mock_span.attributes = {"agent.id": "agent_123"}  # Old format

        # Test
        processor.on_end(mock_span)

        # Verify
        mock_processor = processor._processors["agent_123"]
        mock_processor.on_end.assert_called_once_with(mock_span)

    def test_no_agent_id_skips_routing(self, processor, mock_span):
        """Test that spans without agent_id are skipped."""
        mock_span.attributes = {"some_other_attr": "value"}

        # Should not raise an exception
        processor.on_end(mock_span)

    def test_unknown_agent_id_skips_routing(self, processor, mock_span):
        """Test that spans with unknown agent_id are skipped."""
        mock_span.attributes = {"agent_id": "unknown_agent"}

        # Should not raise an exception
        processor.on_end(mock_span)

    def test_missing_span_attributes(self, processor, mock_span):
        """Test behavior when span has no attributes."""
        mock_span.attributes = None

        # Should not raise an exception
        processor.on_end(mock_span)

    @patch("agent_platform.core.conditional_langsmith_processor.OTLPSpanExporter")
    @patch("agent_platform.core.conditional_langsmith_processor.BatchSpanProcessor")
    def test_processor_exception_handling(
        self, mock_batch_processor, mock_exporter, processor, langsmith_config_a, mock_span
    ):
        """Test that processor exceptions are handled gracefully."""
        # Setup
        processor.add_or_update_config("agent_123", langsmith_config_a)
        mock_span.attributes = {"agent_id": "agent_123"}

        # Make the processor raise an exception
        mock_processor = processor._processors["agent_123"]
        mock_processor.on_end.side_effect = Exception("Test error")

        with patch("agent_platform.core.conditional_langsmith_processor.logger") as mock_logger:
            # Should not raise the exception
            processor.on_end(mock_span)

            # Should log the error
            mock_logger.error.assert_called_once()

    @patch("agent_platform.core.conditional_langsmith_processor.OTLPSpanExporter")
    @patch("agent_platform.core.conditional_langsmith_processor.BatchSpanProcessor")
    def test_multi_agent_isolation(
        self, mock_batch_processor, mock_exporter, processor, langsmith_config_a, langsmith_config_b
    ):
        """Test that different agents route to their correct exporters only."""
        # Make BatchSpanProcessor return different mock instances for each call
        mock_processor_a = MagicMock()
        mock_processor_b = MagicMock()
        mock_batch_processor.side_effect = [mock_processor_a, mock_processor_b]

        # Setup two different agents
        processor.add_or_update_config("agent_111", langsmith_config_a)
        processor.add_or_update_config("agent_222", langsmith_config_b)

        # Create spans for each agent
        span_agent_111 = MagicMock()
        span_agent_111.name = "span_from_agent_111"
        span_agent_111.attributes = {"agent_id": "agent_111"}

        span_agent_222 = MagicMock()
        span_agent_222.name = "span_from_agent_222"
        span_agent_222.attributes = {"agent_id": "agent_222"}

        # Test Agent 111 span routing
        processor.on_end(span_agent_111)

        # Verify only processor A was called
        mock_processor_a.on_end.assert_called_once_with(span_agent_111)
        mock_processor_b.on_end.assert_not_called()

        # Reset mocks
        mock_processor_a.reset_mock()
        mock_processor_b.reset_mock()

        # Test Agent 222 span routing
        processor.on_end(span_agent_222)

        # Verify only processor B was called
        mock_processor_b.on_end.assert_called_once_with(span_agent_222)
        mock_processor_a.on_end.assert_not_called()

    @patch("agent_platform.core.conditional_langsmith_processor.OTLPSpanExporter")
    @patch("agent_platform.core.conditional_langsmith_processor.BatchSpanProcessor")
    def test_config_update_shuts_down_old_processor(
        self, mock_batch_processor, mock_exporter, processor, langsmith_config_a, langsmith_config_b
    ):
        """Test that updating config properly shuts down old processor."""
        mock_processor_old = MagicMock()
        mock_processor_new = MagicMock()
        mock_batch_processor.side_effect = [mock_processor_old, mock_processor_new]

        # Add initial config
        result1 = processor.add_or_update_config("agent_123", langsmith_config_a)
        assert result1 is True

        # Update with different config
        result2 = processor.add_or_update_config("agent_123", langsmith_config_b)
        assert result2 is True

        # Verify old processor was shutdown
        mock_processor_old.shutdown.assert_called_once()

    def test_shutdown_all_processors(self, processor):
        """Test that shutdown properly shuts down all processors."""
        with (
            patch("agent_platform.core.conditional_langsmith_processor.OTLPSpanExporter"),
            patch(
                "agent_platform.core.conditional_langsmith_processor.BatchSpanProcessor"
            ) as mock_batch,
        ):
            mock_processor_a = MagicMock()
            mock_processor_b = MagicMock()
            mock_batch.side_effect = [mock_processor_a, mock_processor_b]

            # Add two configs
            config_a = ObservabilityConfig(
                type="langsmith",
                api_key="key_a",
                api_url="https://api.smith.langchain.com",
                settings={"project_name": "project_a"},
            )
            config_b = ObservabilityConfig(
                type="langsmith",
                api_key="key_b",
                api_url="https://api.smith.langchain.com",
                settings={"project_name": "project_b"},
            )

            processor.add_or_update_config("agent_a", config_a)
            processor.add_or_update_config("agent_b", config_b)

            # Shutdown
            processor.shutdown()

            # Verify both processors were shutdown
            mock_processor_a.shutdown.assert_called_once()
            mock_processor_b.shutdown.assert_called_once()

            # Verify mappings were cleared
            assert len(processor._processors) == 0
            assert len(processor._signatures) == 0

    @patch.dict(
        os.environ,
        {
            "LANGCHAIN_API_KEY": "global_key",
            "LANGCHAIN_ENDPOINT": "https://global-endpoint",
            "LANGCHAIN_PROJECT": "global_project",
        },
    )
    @patch("agent_platform.core.conditional_langsmith_processor.BatchSpanProcessor")
    def test_global_mode_ignores_per_agent_registration(self, mock_batch_processor):
        """Test that per-agent registration is ignored in global mode."""
        processor = ConditionalLangSmithProcessor()
        config = ObservabilityConfig(
            type="langsmith",
            api_key="agent_key",
            api_url="https://api.smith.langchain.com",
            settings={"project_name": "agent_project"},
        )
        result = processor.add_or_update_config("agent_123", config)
        assert result is True
        # Only the global processor should exist
        assert processor._global_processor is not None
        assert processor._processors == {}

    @patch.dict(
        os.environ,
        {
            "LANGCHAIN_API_KEY": "global_key",
            "LANGCHAIN_ENDPOINT": "https://global-endpoint",
            "LANGCHAIN_PROJECT": "global_project",
        },
    )
    @patch("agent_platform.core.conditional_langsmith_processor.BatchSpanProcessor")
    def test_global_processor_receives_spans(self, mock_batch_processor):
        """Test that the global processor receives spans in global mode."""
        mock_global_processor = MagicMock()
        mock_batch_processor.return_value = mock_global_processor
        processor = ConditionalLangSmithProcessor()
        mock_span = MagicMock()
        mock_span.name = "test_span"
        processor.on_end(mock_span)
        mock_global_processor.on_end.assert_called_once_with(mock_span)

    @patch.dict(
        os.environ,
        {
            "LANGCHAIN_API_KEY": "global_key",
            "LANGCHAIN_ENDPOINT": "https://global-endpoint",
            "LANGCHAIN_PROJECT": "global_project",
        },
    )
    @patch("agent_platform.core.conditional_langsmith_processor.BatchSpanProcessor")
    def test_global_processor_overrides_per_agent(self, mock_batch_processor):
        """
        Test that when both global and per-agent LangSmith configs exist,
        only the global processor receives spans.
        """
        # Mock the global processor
        mock_global_processor = MagicMock()
        mock_batch_processor.return_value = mock_global_processor
        processor = ConditionalLangSmithProcessor()

        # Try to register a per-agent processor
        config = ObservabilityConfig(
            type="langsmith",
            api_key="agent_key",
            api_url="https://api.smith.langchain.com",
            settings={"project_name": "agent_project"},
        )
        processor.add_or_update_config("agent_123", config)

        # Create a span with the agent_id
        mock_span = MagicMock()
        mock_span.name = "test_span"
        mock_span.attributes = {"agent_id": "agent_123"}

        # Process the span
        processor.on_end(mock_span)

        # Verify only the global processor received the span
        mock_global_processor.on_end.assert_called_once_with(mock_span)
        # Verify no per-agent processors exist
        assert processor._processors == {}

    @patch.dict(
        os.environ,
        {
            "LANGCHAIN_API_KEY": "global_key",
            "LANGCHAIN_ENDPOINT": "https://global-endpoint",
            "LANGCHAIN_PROJECT": "global_project",
        },
    )
    @patch("agent_platform.core.conditional_langsmith_processor.BatchSpanProcessor")
    def test_only_s4_and_global_langsmith_receive_on_end(self, mock_batch_processor):
        """
        Test that only the S4 observability processor and the global LangSmith processor
        receive on_end for each span, and no other processors receive spans.
        """
        # Mock the global LangSmith processor
        mock_global_processor = MagicMock()
        mock_batch_processor.return_value = mock_global_processor
        processor = ConditionalLangSmithProcessor()

        # Mock the S4 processor
        mock_otlp_processor = MagicMock()

        # Create a mock per-agent processor that should NOT receive spans
        mock_per_agent_processor = MagicMock()
        processor._processors["some_agent"] = mock_per_agent_processor

        # Simulate a tracer provider with all processors
        class DummyTracerProvider:
            def __init__(self):
                self._span_processors = [mock_otlp_processor, processor]

            def on_end(self, span):
                for proc in self._span_processors:
                    proc.on_end(span)

        tracer_provider = DummyTracerProvider()
        mock_span = MagicMock()
        mock_span.name = "test_span"
        mock_span.attributes = {"agent_id": "some_agent"}  # Add agent_id to test routing

        # Call on_end on both processors
        tracer_provider.on_end(mock_span)

        # Assert only the global processor and S4 processor received the span
        mock_otlp_processor.on_end.assert_called_once_with(mock_span)
        mock_global_processor.on_end.assert_called_once_with(mock_span)
        # Verify the per-agent processor did NOT receive the span
        mock_per_agent_processor.on_end.assert_not_called()
