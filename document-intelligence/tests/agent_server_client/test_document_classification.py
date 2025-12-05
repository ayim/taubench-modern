"""
Integration tests for document classification using the agent server client.
"""

import logging

from sema4ai_docint.agent_server_client.client import AgentServerClient

logger = logging.getLogger(__name__)


# Not a part of the DocumentClassification suite.
def test_update_filename_scores():
    """Test that the default layout score is 1.0 and other layouts are not affected."""
    filename_scores = {"default": 0.5, "other": 0.3}

    updated_scores = AgentServerClient._update_filename_scores(filename_scores)
    assert updated_scores == {"default": 1.0, "other": 0.3}
