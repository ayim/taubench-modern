from abc import ABC, abstractmethod


class MigrationError(Exception):
    """Base exception for all migration-related errors."""


class MigrationLockError(MigrationError):
    """Exception raised when a migration lock cannot be acquired."""


class MigrationTimeoutError(MigrationError):
    """Exception raised when a migration takes too long to apply."""


class InvalidMigrationFilenameError(MigrationError):
    """Exception raised when a migration filename is invalid."""


class MigrationsProvider(ABC):
    """Abstract base class for migrations providers."""

    @abstractmethod
    async def run_migrations(self) -> None:
        """Apply all migrations."""
