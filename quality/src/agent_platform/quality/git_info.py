"""Git information utilities for quality test exports.

This module provides functionality to capture git commit information
from the monorepo for tracking test results over time.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)


def get_git_commit_sha(cwd: Path | None = None) -> str | None:
    """Get the current git commit SHA.

    Args:
        cwd: Working directory to run git command in. Defaults to current directory.

    Returns:
        The full git commit SHA, or None if git is not available or not in a git repo.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
            timeout=5.0,
        )
        commit_sha = result.stdout.strip()
        logger.debug("Captured git commit SHA", sha=commit_sha)
        return commit_sha
    except subprocess.CalledProcessError as e:
        logger.warning("Failed to get git commit SHA", error=str(e))
        return None
    except FileNotFoundError:
        logger.warning("git command not found")
        return None
    except subprocess.TimeoutExpired:
        logger.warning("git command timed out")
        return None
    except Exception as e:
        logger.warning("Unexpected error getting git commit SHA", error=str(e))
        return None
