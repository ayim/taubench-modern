"""SQL Generation Agent module.

This module contains the SQL generation agent preinstalled agent logic and runbook.
The SQL generation subagent is invoked by parent agents to generate SQL queries against
semantic data models (SDMs).
"""

from agent_platform.server.sql_generation.preinstalled_agent import (
    ensure_sql_generation_agent,
)

__all__ = [
    "ensure_sql_generation_agent",
]
