import uuid
from datetime import UTC, datetime, timedelta

import pytest
from freezegun import freeze_time

from agent_platform.core.agent import Agent, AgentArchitecture
from agent_platform.core.configurations.config_validation import ConfigType
from agent_platform.core.configurations.quotas import QuotaConfig, QuotasService
from agent_platform.core.runbook import Runbook
from agent_platform.core.thread import Thread
from agent_platform.server.data_retention_policy import retention_policy_worker
from agent_platform.server.storage import BaseStorage

# This test module verifies the functionality of the data retention policy
# which is responsible for cleaning up stale threads based on configured retention periods

pytest_plugins = ("server.tests.endpoints.conftest",)

# Test user identifiers
TEST_USER_SUB = f"tenant:test:user:{uuid.uuid4()}"  # Regular user identifier
TEST_SYSTEM_USER = f"tenant:{uuid.uuid4()}:system:system_user"  # System user identifier

# Agent identifiers for different test scenarios
USER_AGENT_ID = str(uuid.uuid4())  # Agent owned by regular user
SCOPED_AGENT_ID = str(uuid.uuid4())  # Agent with custom retention period
SYSTEM_AGENT_ID = str(uuid.uuid4())  # Agent owned by system user

# Default retention period from the quota service configuration
DEFAULT_RETENTION_PERIOD: QuotaConfig = QuotasService.CONFIG_TYPES[QuotasService.AGENT_THREAD_RETENTION_PERIOD_DAYS]


@pytest.fixture
async def stale_data_storage(storage: BaseStorage):
    """
    Fixture that sets up test data for retention policy tests.

    Creates users, agents, threads, and associated files with different timestamps
    to test the retention policy's behavior with different retention periods.

    Returns:
        A dictionary containing the storage instance and file removal arguments.
    """
    # Create test users
    test_user, _ = await storage.get_or_create_user(TEST_USER_SUB)
    test_system_user, _ = await storage.get_or_create_user(TEST_SYSTEM_USER)

    agents: list[Agent] = []
    # Expected rm args is a tuple (file_uuid, file_path) keyed by thread_id
    # This will be used to track which files should be deleted
    file_rm_args: dict[str, tuple[str, str]] = {}

    # Calculate the retention threshold based on the default retention period
    # Threads older than this threshold are candidates for deletion
    retention_threshold = datetime.now() - timedelta(days=DEFAULT_RETENTION_PERIOD.default_value)

    # Create a regular user agent with default retention period
    agent = Agent(
        agent_id=USER_AGENT_ID,
        name="Test Agent",
        description="Test Agent",
        user_id=test_user.user_id,
        runbook_structured=Runbook(raw_text="You are helpful agent", content=[]),
        version="1.0.0",
        agent_architecture=AgentArchitecture(
            name="agent_platform.architectures.default",
            version="1.0.0",
        ),
        platform_configs=[],
    )

    await storage.upsert_agent(test_user.user_id, agent)
    agents.append(agent)

    # Create an agent that will have a custom (scoped) retention period
    # This agent will be configured with a shorter retention period later
    agent_scoped = Agent(
        agent_id=SCOPED_AGENT_ID,
        name="Scoped Test Agent",
        description="Scoped Test Agent",
        user_id=test_user.user_id,
        runbook_structured=Runbook(raw_text="You are helpful agent", content=[]),
        version="1.0.0",
        agent_architecture=AgentArchitecture(
            name="agent_platform.architectures.default",
            version="1.0.0",
        ),
        platform_configs=[],
    )

    agents.append(agent_scoped)
    await storage.upsert_agent(test_user.user_id, agent_scoped)

    # Create a system agent owned by the system user
    # System agents typically have different retention policies
    system_agent = Agent(
        agent_id=SYSTEM_AGENT_ID,
        name="Test System Agent",
        description="Test System Agent",
        user_id=test_system_user.user_id,
        runbook_structured=Runbook(raw_text="You are helpful agent", content=[]),
        version="1.0.0",
        agent_architecture=AgentArchitecture(
            name="agent_platform.architectures.default",
            version="1.0.0",
        ),
        platform_configs=[],
    )

    await storage.upsert_agent(test_system_user.user_id, system_agent)
    agents.append(system_agent)

    # For each agent, create two threads:
    # 1. A "past" thread that is older than the retention threshold (candidate for deletion)
    # 2. A "future" thread that is newer than the retention threshold (should be kept)
    for a in agents:
        # Create a thread that is older than the retention threshold
        # This thread should be deleted by the retention policy
        past_thread = Thread(
            thread_id=str(uuid.uuid4()),
            agent_id=a.agent_id,
            user_id=a.user_id,
            name=f"{a.name} - PAST THRESHOLD",
            updated_at=retention_threshold - timedelta(days=1),  # Older than threshold
        )
        await storage.upsert_thread(a.user_id, past_thread)

        # Create a file associated with the past thread
        file_uuid = str(uuid.uuid4())
        await storage.put_file_owner(
            file_id=file_uuid,
            file_path=f"local://{file_uuid}",
            file_ref=f"test-file-ref-{a.name}",
            file_hash="test-hash",
            file_size_raw=1024,
            mime_type="text/plain",
            user_id=a.user_id,
            embedded=False,
            embedding_status=None,
            owner=past_thread,  # Associate file with the past thread
            file_path_expiration=None,
        )

        # Track the file for later verification of deletion
        file_rm_args[past_thread.thread_id] = (
            file_uuid,
            f"local://{file_uuid}",
        )

        # Create a thread that is newer than the retention threshold
        # This thread should be kept by the retention policy
        future_thread = Thread(
            thread_id=str(uuid.uuid4()),
            agent_id=a.agent_id,
            user_id=a.user_id,
            name=f"{a.name} - BEFORE THRESHOLD",
            updated_at=retention_threshold + timedelta(days=1),  # Newer than threshold
        )

        await storage.upsert_thread(a.user_id, future_thread)

        # Create a file associated with the future thread
        future_file_uuid = str(uuid.uuid4())
        await storage.put_file_owner(
            file_id=future_file_uuid,
            file_path=f"local://{future_file_uuid}",
            file_ref=f"test-file-ref-{a.agent_id}",
            file_hash="test-hash",
            file_size_raw=1024,
            mime_type="text/plain",
            user_id=a.user_id,
            embedded=False,
            embedding_status=None,
            owner=future_thread,  # Associate file with the future thread
            file_path_expiration=None,
        )

        # Track the file for later verification
        file_rm_args[future_thread.thread_id] = (
            future_file_uuid,
            f"local://{future_file_uuid}",
        )

    # Configure a custom (shorter) retention period for the scoped agent
    # This is 30 days less than the default retention period
    # Used to test agent-specific retention policies
    await storage.set_config(
        ConfigType.AGENT_THREAD_RETENTION_PERIOD,
        str(DEFAULT_RETENTION_PERIOD.default_value - 30),  # Shorter retention period
        namespace=f"agent_id:{SCOPED_AGENT_ID}",  # Scoped to specific agent
    )

    # Return the storage instance and file removal arguments for use in tests
    return {"storage": storage, "file_rm_args": file_rm_args}


async def test_retention_policy_worker__functional(stale_data_storage, monkeypatch):
    """
    Test that invokes server.data_retention_policy.retention_policy_worker().
    Asserts that only the threads and associated files of "Test System Agent" were deleted.
    """
    from agent_platform.server.file_manager import FileManagerService
    from agent_platform.server.storage import StorageService

    # Unpack the fixture data
    match stale_data_storage:
        case {"storage": storage, "file_rm_args": file_rm_args}:
            # Unpack dictionary
            pass
        case _:
            raise ValueError("Invalid stale_data_storage fixture")

    # Mock the StorageService.get_instance() to return our test storage
    # This ensures the retention policy worker uses our test data
    monkeypatch.setattr(StorageService, "get_instance", lambda: storage)

    # Mock the FileManagerService.get_instance() to return a mock that tracks deleted files
    # This allows us to verify which files were deleted by the retention policy
    deleted_files: set[tuple[str, str | None]] = set()

    class MockFileManager:
        async def rm(self, file_id: str, file_path: str | None = None):
            # Track deleted files for later verification
            deleted_files.add((file_id, file_path))

    mock_file_manager = MockFileManager()
    monkeypatch.setattr(FileManagerService, "get_instance", lambda: mock_file_manager)

    # Get users from the fixture for later queries
    user, _ = await storage.get_or_create_user(TEST_USER_SUB)
    system_user, _ = await storage.get_or_create_user(TEST_SYSTEM_USER)

    # Remove system agent threads from expected deletions
    # We're excluding system agent threads from our deletion expectations
    for item in await storage.list_threads_for_agent(system_user.user_id, SYSTEM_AGENT_ID):
        del file_rm_args[item.thread_id]

    # Call the retention policy worker - this is the function being tested
    await retention_policy_worker()

    # Get threads for each agent after worker execution to verify results
    system_agent_threads = await storage.list_threads_for_agent(system_user.user_id, SYSTEM_AGENT_ID)
    user_agent_threads = await storage.list_threads_for_agent(user.user_id, USER_AGENT_ID)
    scoped_agent_threads = await storage.list_threads_for_agent(user.user_id, SCOPED_AGENT_ID)

    # Verify system agent threads were not deleted
    assert len(system_agent_threads) == 2, "System agent should have both threads remaining"

    # Verify scoped agent threads were all deleted due to shorter retention period
    assert len(scoped_agent_threads) == 0, (
        "Scoped agent should have no threads since the retention period for it is 60 days"
    )

    # Verify regular user agent has only the newer thread remaining
    assert len(user_agent_threads) == 1, "User agent should have 1 thread remaining"
    remaining_thread = user_agent_threads[0]

    # Verify the remaining thread is the newer one
    assert remaining_thread.name == "Test Agent - BEFORE THRESHOLD", "Only future thread should remain for user agent"

    # Remove the remaining thread from expected deletions
    del file_rm_args[remaining_thread.thread_id]

    # Verify all expected files were deleted
    assert deleted_files == set(file_rm_args.values()), "Missmatch in deleted files"


async def test_retention_policy_worker__scoped_agent(stale_data_storage, monkeypatch):
    """
    Test that invokes server.data_retention_policy.retention_policy_worker() with a time shift.

    This test specifically focuses on the behavior of the scoped agent
    with a custom retention period.

    It uses freeze_time to simulate running the worker 30 days in the past, which affects
    which threads are considered stale based on their retention periods.
    """
    from agent_platform.server.file_manager import FileManagerService
    from agent_platform.server.storage import StorageService

    # Unpack the fixture data
    match stale_data_storage:
        case {"storage": storage, "file_rm_args": file_rm_args}:
            # Unpack dictionary
            pass
        case _:
            raise ValueError("Invalid stale_data_storage fixture")

    # Mock the StorageService.get_instance() to return our test storage
    # This ensures the retention policy worker uses our test data
    monkeypatch.setattr(StorageService, "get_instance", lambda: storage)

    # Mock the FileManagerService.get_instance() to return a mock that tracks deleted files
    # This allows us to verify which files were deleted by the retention policy
    deleted_files: set[tuple[str, str | None]] = set()

    class MockFileManager:
        async def rm(self, file_id: str, file_path: str | None = None):
            # Track deleted files for later verification
            deleted_files.add((file_id, file_path))

    mock_file_manager = MockFileManager()
    monkeypatch.setattr(FileManagerService, "get_instance", lambda: mock_file_manager)

    # Get users from the fixture for later queries
    user, _ = await storage.get_or_create_user(TEST_USER_SUB)
    system_user, _ = await storage.get_or_create_user(TEST_SYSTEM_USER)

    # Remove system agent threads from expected deletions
    # We're excluding system agent threads from our deletion expectations
    for item in await storage.list_threads_for_agent(system_user.user_id, SYSTEM_AGENT_ID):
        del file_rm_args[item.thread_id]

    # Remove user agent threads from expected deletions
    # We're excluding user agent threads from our deletion expectations in this test
    for item in await storage.list_threads_for_agent(user.user_id, USER_AGENT_ID):
        del file_rm_args[item.thread_id]

    # Move back 30 days to test time-dependent behavior
    # This affects which threads are considered stale based on their retention periods
    with freeze_time(datetime.now(UTC) - timedelta(days=30)):
        # Call the retention policy worker - this is the function being tested
        await retention_policy_worker()

    # Get threads for each agent after worker execution to verify results
    system_agent_threads = await storage.list_threads_for_agent(system_user.user_id, SYSTEM_AGENT_ID)
    user_agent_threads = await storage.list_threads_for_agent(user.user_id, USER_AGENT_ID)
    scoped_agent_threads = await storage.list_threads_for_agent(user.user_id, SCOPED_AGENT_ID)

    # Verify system agent threads were not deleted
    assert len(system_agent_threads) == 2, "System agent should have both threads remaining"

    # Verify user agent threads were not deleted (retention period is 90 days)
    assert len(user_agent_threads) == 2, (
        "User agent should have both threads remaining singe the retention period is 90 days"
    )

    # Verify scoped agent has only one thread remaining (the newer one)
    # This is because it has a custom shorter retention period
    assert len(scoped_agent_threads) == 1

    # Get the remaining thread for verification
    remaining_thread = scoped_agent_threads[0]

    # Verify the remaining thread is the newer one
    assert remaining_thread.name == "Scoped Test Agent - BEFORE THRESHOLD", (
        "Only future thread should remain for scoped agent"
    )

    # Remove the remaining thread from expected deletions
    del file_rm_args[remaining_thread.thread_id]

    # Verify all expected files were deleted
    assert deleted_files == set(file_rm_args.values()), "Missmatch in deleted files"
