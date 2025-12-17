"""Base evaluator interface for quality testing."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, TypeVar

from agent_platform.quality.models import Evaluation

if TYPE_CHECKING:
    import httpx

    from agent_platform.quality.models import TestResult

TEvaluation = TypeVar("TEvaluation", bound=Evaluation)


class Evaluator[TEvaluation: Evaluation](ABC):
    """Abstract base class for evaluators.

    Defines the standard API for all evaluator implementations:
    - Constructor takes evaluation config and common infrastructure (client, server_url)
    - evaluate() method accepts evaluation-specific kwargs and returns a TestResult
    """

    def __init__(
        self,
        evaluation: TEvaluation,
        client: httpx.AsyncClient,
        server_url: str,
    ):
        """Initialize the evaluator.

        Args:
            evaluation: The evaluation configuration (type varies by evaluator).
            client: HTTP client for API calls.
            server_url: Base URL for the server.
        """
        self.evaluation = evaluation
        self.client = client
        self.server_url = server_url

    @abstractmethod
    async def evaluate(self, **kwargs) -> TestResult:
        """Execute the evaluation and return results.

        Args:
            **kwargs: Evaluation-specific arguments (e.g., thread_id, test_directory,
                     agent_messages, thread_files, workitem).

        Returns:
            TestResult with passed/failed status, actual values, and error details.
        """
        ...
