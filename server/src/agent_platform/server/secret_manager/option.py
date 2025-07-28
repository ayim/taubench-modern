import os
from enum import StrEnum

from agent_platform.server.secret_manager.aws_sm.aws_sm import AwsSecretManager
from agent_platform.server.secret_manager.base import BaseSecretManager
from agent_platform.server.secret_manager.environment.environment import EnvironmentSecretManager
from agent_platform.server.secret_manager.local_file.local_file import LocalFileSecretManager


class EncryptionKeySource(StrEnum):
    """
    Enum for the encryption key source.
    This enum is responsible for the encryption key source.
    """

    FILE = "file"
    ENVIRONMENT = "environment"
    AWS = "aws"


class SecretService:
    """
    Service for secrets management using a singleton pattern.
    This class is responsible for managing the secrets for the agent platform.
    """

    _instance: BaseSecretManager | None = None

    @classmethod
    def get_instance(cls) -> BaseSecretManager:
        """
        Get the singleton instance of the secret service.
        This method is responsible for getting the singleton instance of the secret service.

        Returns:
            The singleton instance of the secret service.
        """
        if cls._instance is None:
            cls._instance = cls._initialize_secret_manager()
        return cls._instance

    @classmethod
    def _initialize_secret_manager(cls) -> BaseSecretManager:
        """
        Initialize the appropriate secret manager implementation based on configuration.

        Returns:
            The initialized secret manager.

        Raises:
            ValueError: If the secret source type is not supported.
        """
        source = os.getenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY_SOURCE", "file")
        match source:
            case EncryptionKeySource.FILE:
                return LocalFileSecretManager()
            case EncryptionKeySource.ENVIRONMENT:
                return EnvironmentSecretManager()
            case EncryptionKeySource.AWS:
                kms_key_arn = os.getenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY_AWS_KMS_ARN") or None

                return AwsSecretManager(kms_key_arn=kms_key_arn)
            case _:
                raise ValueError(f"secret source type {source} not supported")
