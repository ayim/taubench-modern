from abc import ABC, abstractmethod


class BaseSecretManager(ABC):
    """
    Base class for the secret manager.
    This class is responsible for managing the secrets for the agent platform.
    """

    @abstractmethod
    def setup(self) -> None:
        """
        Setup the secret manager.
        This method is responsible for setting up the secret manager.
        """

    @abstractmethod
    def store(self, data: str) -> str:
        """
        Store data securely and return a reference to retrieve it later.

        For envelope encryption implementations, this encrypts the data and returns
        the encrypted result. For cloud secret managers, this stores the data
        remotely and returns an identifier/ARN.

        Args:
            data: The plaintext data to store securely

        Returns:
            A string that can be stored in the database and later passed to fetch()
        """

    @abstractmethod
    def fetch(self, stored_reference: str) -> str:
        """
        Retrieve data that was previously stored using store().

        For envelope encryption implementations, this decrypts the data.
        For cloud secret managers, this retrieves the data using the reference.

        Args:
            stored_reference: The return value from a previous store() call

        Returns:
            The original plaintext data
        """
