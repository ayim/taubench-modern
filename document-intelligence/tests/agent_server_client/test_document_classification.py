"""
Unit tests for document classification using the agent server client.
"""

import pytest
import structlog

from sema4ai_docint.agent_server_client.client import AgentServerClient
from sema4ai_docint.agent_server_client.exceptions import DocumentClassificationError

logger = structlog.getLogger(__name__)


# Not a part of the DocumentClassification suite.
def test_update_filename_scores():
    """Test that the default layout score is 1.0 and other layouts are not affected."""
    filename_scores = {"default": 0.5, "other": 0.3}

    updated_scores = AgentServerClient._update_filename_scores(filename_scores)
    assert updated_scores == {"default": 1.0, "other": 0.3}


class TestChooseLayout:
    """Unit tests for _choose_layout method."""

    def test_empty_available_layouts_raises_error(self, agent_server_client: AgentServerClient):
        """Test that empty available_layouts raises DocumentClassificationError."""
        image_scores: dict[str, float] = {}
        filename_scores: dict[str, float] = {}
        available_layouts: list[str] = []

        with pytest.raises(DocumentClassificationError, match="available schemas"):
            agent_server_client._choose_layout(image_scores, filename_scores, available_layouts)

    def test_high_confidence_early_return_single_layout(
        self, agent_server_client: AgentServerClient
    ):
        """Test that a single layout with score >= 0.95 bypasses filename check."""
        image_scores = {"layout_a": 0.96, "layout_b": 0.3, "layout_c": 0.2}
        filename_scores: dict[str, float] = {}  # Not used when early return
        available_layouts = ["layout_a", "layout_b", "layout_c"]

        result = agent_server_client._choose_layout(
            image_scores, filename_scores, available_layouts
        )

        assert result == "layout_a"

    def test_multiple_high_confidence_layouts_continues_to_weighted_scoring(
        self, agent_server_client: AgentServerClient
    ):
        """Test that multiple layouts with score >= 0.95 continues to weighted scoring."""
        image_scores = {"layout_a": 0.96, "layout_b": 0.95, "layout_c": 0.2}
        filename_scores = {"layout_a": 0.4, "layout_b": 0.6}
        available_layouts = ["layout_a", "layout_b", "layout_c"]

        result = agent_server_client._choose_layout(
            image_scores, filename_scores, available_layouts
        )

        # Should use weighted scoring: layout_b wins (0.95*0.6 + 0.6*0.4 = 0.81)
        assert result == "layout_b"

    def test_weighted_scoring_combines_image_and_filename(
        self, agent_server_client: AgentServerClient
    ):
        """Test that final scores are correctly weighted (image * 0.6 + filename * 0.4)."""
        image_scores = {"layout_a": 0.8, "layout_b": 0.6}
        filename_scores = {"layout_a": 0.5, "layout_b": 0.9}
        available_layouts = ["layout_a", "layout_b"]

        result = agent_server_client._choose_layout(
            image_scores, filename_scores, available_layouts
        )

        # layout_a: 0.8*0.6 + 0.5*0.4 = 0.48 + 0.20 = 0.68
        # layout_b: 0.6*0.6 + 0.9*0.4 = 0.36 + 0.36 = 0.72
        # layout_b should win
        assert result == "layout_b"

    def test_threshold_validation_above_threshold_returns_layout(
        self, agent_server_client: AgentServerClient
    ):
        """Test that layout with score >= 0.7 threshold is returned."""
        image_scores = {"layout_a": 0.7, "layout_b": 0.5}
        filename_scores = {"layout_a": 0.8, "layout_b": 0.3}
        available_layouts = ["layout_a", "layout_b"]

        result = agent_server_client._choose_layout(
            image_scores, filename_scores, available_layouts
        )

        # layout_a: 0.7*0.6 + 0.8*0.4 = 0.42 + 0.32 = 0.74 (above threshold)
        assert result == "layout_a"

    def test_threshold_validation_below_threshold_raises_error(
        self, agent_server_client: AgentServerClient
    ):
        """Test that layout with score < 0.7 threshold raises DocumentClassificationError."""
        image_scores = {"layout_a": 0.4, "layout_b": 0.3}
        filename_scores = {"layout_a": 0.5, "layout_b": 0.4}
        available_layouts = ["layout_a", "layout_b"]

        with pytest.raises(DocumentClassificationError, match="Unknown"):
            agent_server_client._choose_layout(image_scores, filename_scores, available_layouts)
