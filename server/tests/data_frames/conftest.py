"""Test configuration for data_frames tests."""

import typing

import pytest

# Import storage fixtures so they're available to all tests in this directory
from server.tests.storage_fixtures import *  # noqa: F403

if typing.TYPE_CHECKING:
    from tests.data_frames.fixtures import StorageStub

    from agent_platform.server.data_frames.data_frames_kernel import DataFramesKernel


@pytest.fixture
def storage_stub() -> "StorageStub":
    """Create a StorageStub for testing data frames."""
    from tests.data_frames.fixtures import StorageStub

    return StorageStub()


@pytest.fixture
def data_frames_kernel(storage_stub: "StorageStub") -> "DataFramesKernel":
    """Create a DataFramesKernel for testing."""
    from agent_platform.server.auth import AuthedUser
    from agent_platform.server.data_frames.data_frames_kernel import DataFramesKernel
    from agent_platform.server.storage.base import BaseStorage

    base_storage = typing.cast(BaseStorage, storage_stub)
    user = typing.cast(AuthedUser, storage_stub.thread.user)
    return DataFramesKernel(base_storage, user, storage_stub.thread.tid)
