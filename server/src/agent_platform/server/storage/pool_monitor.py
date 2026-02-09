"""
Database Connection Pool Monitor

This module provides a background task that continuously monitors
the PostgreSQL connection pool and logs warnings when approaching limits.

The monitor tracks:
- Pool size and available connections
- Requests waiting for connections
- Pool utilization percentage

It also exports OTel metrics for the pool state.
"""

import asyncio
import logging
from collections.abc import Iterable
from dataclasses import dataclass, field

from opentelemetry import metrics
from opentelemetry.metrics import Observation
from sqlalchemy.pool import QueuePool

from agent_platform.core.configurations import Configuration, FieldMetadata
from agent_platform.server.storage import StorageService

logger = logging.getLogger(__name__)

# Create a dedicated meter for database pool metrics
_db_pool_meter = metrics.get_meter("agent_platform.storage.postgres.pool")


def _get_queue_pool() -> QueuePool | None:
    """Get the QueuePool from the storage engine, or None if unavailable."""
    try:
        storage = StorageService.get_instance()
        pool = storage._sa_engine.pool
        if not isinstance(pool, QueuePool):
            logger.warning("Expected QueuePool but got %s", type(pool).__name__)
            return None
        return pool
    except RuntimeError:
        # Engine not initialized yet
        return None


def _get_pool_idle_connections(options) -> Iterable[Observation]:
    """Callback to report idle pool connections."""
    pool = _get_queue_pool()
    if pool is not None:
        yield Observation(value=pool.checkedin(), attributes={"db.system": "postgresql"})


def _get_pool_in_use_connections(options) -> Iterable[Observation]:
    """Callback to report checked out connections."""
    pool = _get_queue_pool()
    if pool is not None:
        yield Observation(value=pool.checkedout(), attributes={"db.system": "postgresql"})


def _get_pool_overflow_connections(options) -> Iterable[Observation]:
    """Callback to report overflow connections currently in use.

    Note: QueuePool.overflow() returns the internal _overflow counter which starts at
    -pool_size and increments as overflow connections are created. The actual number
    of overflow connections in use is max(0, pool.overflow()).
    """
    pool = _get_queue_pool()
    if pool is not None:
        yield Observation(value=max(0, pool.overflow()), attributes={"db.system": "postgresql"})


def _get_pool_base_connections(options) -> Iterable[Observation]:
    """Callback to report base configured pool size."""
    pool = _get_queue_pool()
    if pool is not None:
        # pool.size() returns the base pool size
        yield Observation(value=pool.size(), attributes={"db.system": "postgresql"})


# Register observable gauges
_pool_idle_gauge = _db_pool_meter.create_observable_gauge(
    name="db.pool.connections.idle",
    description="Number of idle connections in the pool",
    unit="connections",
    callbacks=[_get_pool_idle_connections],
)

_pool_in_use_gauge = _db_pool_meter.create_observable_gauge(
    name="db.pool.connections.in_use",
    description="Number of connections currently checked out",
    unit="connections",
    callbacks=[_get_pool_in_use_connections],
)

_pool_overflow_gauge = _db_pool_meter.create_observable_gauge(
    name="db.pool.connections.overflow",
    description="Number of overflow connections in use",
    unit="connections",
    callbacks=[_get_pool_overflow_connections],
)

_pool_size_gauge = _db_pool_meter.create_observable_gauge(
    name="db.pool.size",
    description="Maximum configured pool size",
    unit="connections",
    callbacks=[_get_pool_base_connections],
)


@dataclass(frozen=True)
class PoolMonitorSettings(Configuration):
    """Settings for the pool monitor."""

    # How often to check pool stats (seconds)
    check_interval: int = field(
        default=60,
        metadata=FieldMetadata(
            description="The frequency in seconds to report the database " + "connection pool statistics.",
            env_vars=[
                "SEMA4AI_AGENT_SERVER_DATABASE_POOL_MONITOR_INTERVAL",
                "DATABASE_POOL_MONITOR_INTERVAL",
            ],
        ),
    )


async def pool_monitor_loop(shutdown_event: asyncio.Event) -> None:
    """
    Background loop that monitors the connection pool.

    Checks pool stats every 5 seconds and logs when utilization >= 85%.

    Args:
        shutdown_event: Event to signal shutdown (for lifespan integration)
    """
    logger.info(f"Starting database connection pool monitor (interval={PoolMonitorSettings.check_interval}s)")

    event_wait_task = asyncio.create_task(shutdown_event.wait())
    while not shutdown_event.is_set():
        try:
            pool = _get_queue_pool()
            if pool is not None:
                status = pool.status()
                logger.info(f"SQLAlchemy Database connection pool status: {status}")

        except Exception as e:
            logger.error(f"Error in pool monitor loop: {e}", exc_info=e)

        # In a timeout we'll unblock instead of waiting for the event (otherwise, if
        # the event is set we'll unblock right away).
        await asyncio.wait([event_wait_task], timeout=PoolMonitorSettings.check_interval)
