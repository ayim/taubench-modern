from structlog import get_logger

from agent_platform.server.secret_manager.base import BaseSecretManager

logger = get_logger(__name__)


class AwsSecretManager(BaseSecretManager):
    def __init__(self):
        pass

    def setup(self):
        raise NotImplementedError("AWS Secret Manager is not yet supported")

    def store(self, data: str) -> str:
        """Store data in AWS Secrets Manager and return the ARN/reference."""
        raise NotImplementedError("AWS Secret Manager is not yet supported")

    def fetch(self, stored_reference: str) -> str:
        """Retrieve data from AWS Secrets Manager using the ARN/reference."""
        raise NotImplementedError("AWS Secret Manager is not yet supported")
