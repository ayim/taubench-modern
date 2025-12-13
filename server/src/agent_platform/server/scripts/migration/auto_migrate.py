"""
Automatic migration logic for agent server startup.

This module implements the heuristic:
v1.agents count > 0 AND v2.agents count == 0 => Run the migrations
"""

import asyncio
import time

import structlog

from agent_platform.server.constants import SystemConfig, SystemPaths
from agent_platform.server.scripts.migration.agents import migrate_agents
from agent_platform.server.scripts.migration.storage import get_storage
from agent_platform.server.scripts.migration.threads import migrate_threads
from agent_platform.server.scripts.migration.user import migrate_users
from agent_platform.server.storage.postgres.postgres import PostgresConfig

logger = structlog.get_logger(__name__)


async def should_run_migration() -> bool:
    """
    Check if migration should be run based on the heuristic:
    v1.agents count > 0 AND v2.agents count == 0

    Returns:
        bool: True if migration should be run, False otherwise
    """
    # Determine database type based on environment
    db_type = SystemConfig.db_type
    dsn = PostgresConfig.dsn
    try:
        database_path = SystemPaths.domain_database_path
        storage = get_storage(db_type=db_type, db_path=str(database_path), db_url=dsn)
        await storage.connect()

        try:
            v1_count = await storage.count_v1_agents()
            v2_count = await storage.count_v2_agents()

            logger.info(f"Migration check: v1_agents={v1_count}, v2_agents={v2_count}")

            should_migrate = v1_count > 0 and v2_count == 0

            if should_migrate:
                logger.info("Migration heuristic met: v1 agents exist but no v2 agents found")
            else:
                logger.debug("Migration heuristic not met: skipping automatic migration")

            return should_migrate

        finally:
            await storage.close()

    except Exception as e:
        logger.error(f"Error checking migration status: {e}")
        # In case of error, don't run migration to be safe
        return False


async def run_automatic_migration() -> bool:
    """
    Run automatic migration if the heuristic is met.

    Returns:
        bool: True if migration was successful or not needed, False if migration failed
    """
    try:
        if not await should_run_migration():
            logger.debug("Automatic migration not needed")
            return True

        # Start timing the migration
        migration_start_time = time.time()
        logger.info("Starting automatic migration...")

        # Create and connect to storage once for both migrations
        db_type = SystemConfig.db_type
        dsn = PostgresConfig.dsn
        storage = get_storage(db_type=db_type, db_path=str(SystemPaths.domain_database_path), db_url=dsn)
        await storage.connect()

        try:
            # Run users migration
            users_start_time = time.time()
            logger.info("Running users migration...")
            await migrate_users(storage)
            users_duration = time.time() - users_start_time
            logger.info(f"Users migration completed in {users_duration:.2f} seconds")

            # Run agents migration
            agents_start_time = time.time()
            logger.info("Running agents migration...")
            await migrate_agents(storage)
            agents_duration = time.time() - agents_start_time
            logger.info(f"Agents migration completed in {agents_duration:.2f} seconds")

            # Run threads migration
            threads_start_time = time.time()
            logger.info("Running threads migration...")
            await migrate_threads(storage)
            threads_duration = time.time() - threads_start_time
            logger.info(f"Threads migration completed in {threads_duration:.2f} seconds")

        finally:
            # Always close the storage connection
            await storage.close()

        # Calculate total migration time
        total_migration_time = time.time() - migration_start_time
        logger.info(
            f"Automatic migration completed successfully in {total_migration_time:.2f} seconds "
            f"(agents: {agents_duration:.2f}s, users: {users_duration:.2f}s, threads: {threads_duration:.2f}s)"
        )
        return True

    except Exception as e:
        logger.error(f"Automatic migration failed: {e}")
        return False


def run_migration_sync() -> bool:
    """
    Synchronous wrapper for running automatic migration.

    Returns:
        bool: True if migration was successful or not needed, False if migration failed
    """
    try:
        return asyncio.run(run_automatic_migration())
    except Exception as e:
        logger.error(f"Error running automatic migration: {e}")
        return False
