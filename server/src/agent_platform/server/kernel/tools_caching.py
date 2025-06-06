import asyncio
import time
from collections.abc import Coroutine
from dataclasses import dataclass, field
from typing import Any, Literal

import structlog
from cachetools import TTLCache

from agent_platform.core.agent import Agent
from agent_platform.core.configurations import Configuration, FieldMetadata
from agent_platform.core.tools import ToolDefinition

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ToolCacheConfig(Configuration):
    """Some minimal configuration for the tool cache.

    Key is allowing clients to _disable_ caching if, for any
    reason, things are not working as smooth as we hope."""

    enabled: bool = field(
        default=True,
        metadata=FieldMetadata(
            description="Enable/disable tool-definition caching",
            env_vars=[
                "SEMA4AI_AGENT_SERVER_TOOL_CACHE_ENABLED",
            ],
        ),
    )
    """Enable/disable tool-definition caching"""

    ttl_seconds: int = field(
        default=30 * 60,
        metadata=FieldMetadata(
            description="TTL for successful cache entries (seconds)",
            env_vars=[
                "SEMA4AI_AGENT_SERVER_TOOL_CACHE_TTL_SECONDS",
            ],
        ),
    )
    """TTL for successful cache entries (seconds)"""

    negative_ttl_seconds: int = field(
        default=5 * 60,
        metadata=FieldMetadata(
            description="TTL for failed cache entries (seconds)",
            env_vars=[
                "SEMA4AI_AGENT_SERVER_TOOL_CACHE_NEGATIVE_TTL_SECONDS",
            ],
        ),
    )
    """TTL for failed cache entries (seconds)"""

    max_cache_size: int = field(
        default=2048,
        metadata=FieldMetadata(
            description="Maximum number of entries in the cache",
            env_vars=["SEMA4AI_AGENT_SERVER_TOOL_CACHE_MAX_SIZE"],
        ),
    )
    """Maximum number of entries in the cache"""


@dataclass(frozen=True)
class CachedToolDefinitionsReport:
    """Reports some stats on the tool cache."""

    cached_action_packages: list[dict[str, Any]]
    cached_mcp_servers: list[dict[str, Any]]
    total_success_cache_hits: int
    total_success_cache_misses: int
    total_success_cache_entries: int
    total_negative_cache_hits: int
    total_negative_cache_misses: int
    total_negative_cache_entries: int
    average_success_cache_hit_ratio: float
    average_negative_cache_hit_ratio: float
    average_time_to_fetch_action_packages: float
    average_time_to_fetch_mcp_servers: float


class ToolDefinitionCache:
    """Singleton managing successful & negative TTL caches for tool definitions."""

    _instance: "ToolDefinitionCache | None" = None

    # ------------------------------------------------------------------ creation

    def __new__(cls):  # (singleton factory)
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_once()
        return cls._instance

    @classmethod
    def reinitialize(cls) -> None:
        """Reinitialize the singleton instance for unit testing purposes."""
        cls._instance = None
        cls()._init_once()

    # ------------------------------------------------------------------ init-once

    def _init_once(self) -> None:
        self._success_cache: TTLCache[str, tuple[list[ToolDefinition], list[str]]] = TTLCache(
            maxsize=ToolCacheConfig.max_cache_size,
            ttl=ToolCacheConfig.ttl_seconds,
        )
        self._negative_cache: TTLCache[str, list[str]] = TTLCache(
            maxsize=ToolCacheConfig.max_cache_size,
            ttl=ToolCacheConfig.negative_ttl_seconds,
        )
        self._cache_guard = asyncio.Lock()
        self._refresh_locks: dict[str, asyncio.Lock] = {}
        self._success_hits: int = 0
        self._success_misses: int = 0
        self._negative_hits: int = 0
        self._negative_misses: int = 0
        self._fetch_times_by_kind: dict[str, list[float]] = {
            "action_packages": [],
            "mcp_servers": [],
        }
        self._keys_by_kind: dict[str, list[str]] = {
            "action_packages": [],
            "mcp_servers": [],
        }

    # ------------------------------------------------------------------ utilities

    def _lock_for(self, key: str) -> asyncio.Lock:
        return self._refresh_locks.setdefault(key, asyncio.Lock())

    async def _store_failure(self, key: str, issues: list[str]) -> None:
        # Careful for concurrency: use the guard to ensure that the cache is
        # updated atomically
        async with self._cache_guard:
            self._negative_cache[key] = issues

    def _hit(self, negative: bool) -> None:
        if negative:
            self._negative_hits += 1
        else:
            self._success_hits += 1

    def _miss(self, negative: bool) -> None:
        if negative:
            self._negative_misses += 1
        else:
            self._success_misses += 1

    async def _fetch_record(
        self,
        kind: Literal["action_packages", "mcp_servers"],
        key: str,
        fetch_coro: Coroutine[Any, Any, tuple[list[ToolDefinition], list[str]]],
    ) -> tuple[list[ToolDefinition], list[str]]:
        start = time.perf_counter()
        tools, issues = await fetch_coro
        self._fetch_times_by_kind[kind].append(time.perf_counter() - start)
        self._keys_by_kind[kind].append(key)
        return tools, issues

    # ------------ public ---------------------------------------------------

    async def get_or_fetch(
        self,
        kind: Literal["action_packages", "mcp_servers"],
        key: str,
        fetch_coro: Coroutine[Any, Any, tuple[list[ToolDefinition], list[str]]],
    ) -> tuple[list[ToolDefinition], list[str]]:
        # ------------------------------------------------ fast path (no lock)
        if ToolCacheConfig.enabled:
            if (val := self._success_cache.get(key)) is not None:
                self._hit(negative=False)
                return val
            if (issues := self._negative_cache.get(key)) is not None:
                self._hit(negative=True)
                return [], issues

        # ------------------------------------------------ critical section
        # If someone else is fetching the same key right at this moment,
        # wait for them to finish (TODO: best effort perhaps in the scenario
        # of access from independent event loops? Do we ever have that?)
        lock = self._lock_for(key)
        async with lock:
            # re-check after we acquired the lock
            if ToolCacheConfig.enabled:
                if (val := self._success_cache.get(key)) is not None:
                    self._hit(negative=False)
                    return val
                if (issues := self._negative_cache.get(key)) is not None:
                    self._hit(negative=True)
                    return [], issues

            # cache miss --> fetch
            tools, issues = await self._fetch_record(kind, key, fetch_coro)
            self._miss(negative=bool(issues))

            if not ToolCacheConfig.enabled:
                # No caching, return immediately
                return tools, issues

            # store taking TTL differences into account
            if issues:
                self._negative_cache[key] = issues
            else:
                self._success_cache[key] = (tools, issues)

            return tools, issues

    # --------------------------- maintenance / diagnostics --------------------

    def clear_all(self) -> None:
        self._success_cache.clear()
        self._negative_cache.clear()
        logger.info("Cleared ALL tool caches (singleton)")

    def clear_for_agent(self, agent: Agent) -> None:
        removed_action_server_urls = []
        removed_mcp_server_urls = []
        for url in {ap.url for ap in agent.action_packages if ap.url}:
            self._success_cache.pop(url, None)
            self._negative_cache.pop(url, None)
            removed_action_server_urls.append(url)
        for url in {mcp.url for mcp in agent.mcp_servers if mcp.url}:
            self._success_cache.pop(url, None)
            self._negative_cache.pop(url, None)
            removed_mcp_server_urls.append(url)
        logger.info(
            f"Cleared tool cache for agent {agent.agent_id}; removed action"
            f"servers:\n{'\n'.join(removed_action_server_urls)} and "
            f"MCP servers:\n{'\n'.join(removed_mcp_server_urls)}"
        )

    def report(self) -> CachedToolDefinitionsReport:
        def _get_cache_value(key: str) -> dict[str, Any] | None:
            in_success_cache = key in self._success_cache
            return {
                "key": key,
                "cache_type": "success" if in_success_cache else "negative",
                "definitions": [
                    definition.model_dump() for definition in self._success_cache[key][0]
                ]
                if in_success_cache
                else [],
                "issues": (
                    self._success_cache[key][1] if in_success_cache else self._negative_cache[key]
                ),
            }

        total_success_cache_interactions = self._success_hits + self._success_misses
        total_negative_cache_interactions = self._negative_hits + self._negative_misses

        cached_action_packages = [
            _get_cache_value(key) for key in self._keys_by_kind["action_packages"]
        ]
        cached_mcp_servers = [_get_cache_value(key) for key in self._keys_by_kind["mcp_servers"]]

        report = CachedToolDefinitionsReport(
            cached_action_packages=[value for value in cached_action_packages if value is not None],
            cached_mcp_servers=[value for value in cached_mcp_servers if value is not None],
            total_success_cache_hits=self._success_hits,
            total_success_cache_misses=self._success_misses,
            total_success_cache_entries=len(self._success_cache),
            total_negative_cache_hits=self._negative_hits,
            total_negative_cache_misses=self._negative_misses,
            total_negative_cache_entries=len(self._negative_cache),
            average_success_cache_hit_ratio=(
                self._success_hits / total_success_cache_interactions
                if total_success_cache_interactions
                else 0.0
            ),
            average_negative_cache_hit_ratio=(
                self._negative_hits / total_negative_cache_interactions
                if total_negative_cache_interactions
                else 0.0
            ),
            average_time_to_fetch_action_packages=(
                sum(self._fetch_times_by_kind["action_packages"])
                / len(self._fetch_times_by_kind["action_packages"])
                if self._fetch_times_by_kind["action_packages"]
                else 0.0
            ),
            average_time_to_fetch_mcp_servers=(
                sum(self._fetch_times_by_kind["mcp_servers"])
                / len(self._fetch_times_by_kind["mcp_servers"])
                if self._fetch_times_by_kind["mcp_servers"]
                else 0.0
            ),
        )
        return report
