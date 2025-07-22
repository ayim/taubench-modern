"""Unit tests for AwsSecretManager."""

import pytest

from agent_platform.server.secret_manager.aws_sm.aws_sm import AwsSecretManager
from agent_platform.server.secret_manager.base import BaseSecretManager


class TestAwsSecretManager:
    """Test suite for AwsSecretManager."""

    def setup_method(self):
        """Set up test environment."""
        self.manager = AwsSecretManager()

    def test_inheritance(self):
        """Test that AwsSecretManager inherits from BaseSecretManager."""
        assert isinstance(self.manager, BaseSecretManager)

    def test_init(self):
        """Test initialization of AwsSecretManager."""
        manager = AwsSecretManager()
        assert manager is not None

    def test_setup_raises_not_implemented(self):
        """Test that setup method raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="AWS Secret Manager is not yet supported"):
            self.manager.setup()

    def test_store_raises_not_implemented(self):
        """Test that store method raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="AWS Secret Manager is not yet supported"):
            self.manager.store("test data")

    def test_fetch_raises_not_implemented(self):
        """Test that fetch method raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="AWS Secret Manager is not yet supported"):
            self.manager.fetch("test reference")

    def test_setup_exception_type(self):
        """Test that setup raises the correct exception type."""
        with pytest.raises(NotImplementedError):
            self.manager.setup()

    def test_multiple_instances(self):
        """Test that multiple instances can be created."""
        manager1 = AwsSecretManager()
        manager2 = AwsSecretManager()

        assert manager1 is not manager2
        assert isinstance(manager1, AwsSecretManager)
        assert isinstance(manager2, AwsSecretManager)

    def test_abstract_methods_implementation(self):
        """Test that all abstract methods are implemented (raising NotImplementedError)."""
        # This ensures that the class can be instantiated despite having abstract base
        manager = AwsSecretManager()

        # All methods should exist and be callable (though they raise NotImplementedError)
        assert hasattr(manager, "setup")
        assert hasattr(manager, "store")
        assert hasattr(manager, "fetch")
        assert callable(manager.setup)
        assert callable(manager.store)
        assert callable(manager.fetch)

    def test_error_message_consistency(self):
        """Test that all methods have consistent error messages."""
        expected_message = "AWS Secret Manager is not yet supported"

        with pytest.raises(NotImplementedError, match=expected_message):
            self.manager.setup()

        with pytest.raises(NotImplementedError, match=expected_message):
            self.manager.store("test")

        with pytest.raises(NotImplementedError, match=expected_message):
            self.manager.fetch("test")
