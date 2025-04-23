import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from agent_platform.core.agent import Agent
from agent_platform.core.runs import Run, RunStep
from agent_platform.core.thread import Thread
from agent_platform.server.storage.errors import (
    InvalidUUIDError,
    ReferenceIntegrityError,
    RunNotFoundError,
    RunStepNotFoundError,
)
from agent_platform.server.storage.postgres import PostgresStorage


@pytest.mark.asyncio
async def test_run_crud_operations(
    storage: PostgresStorage,
    sample_user_id: str,
    sample_agent: Agent,
    sample_thread: Thread,
) -> None:
    """
    Test creating, retrieving, listing, upserting, and deleting a run.
    """
    # Ensure the agent and thread exist.
    await storage.upsert_agent(sample_user_id, sample_agent)
    await storage.upsert_thread(sample_user_id, sample_thread)

    sample_run = Run(
        run_id=str(uuid4()),
        agent_id=sample_agent.agent_id,
        thread_id=sample_thread.thread_id,
        created_at=datetime.now(UTC),
        finished_at=None,
        status="completed",
        metadata={"info": "run test"},
        run_type="async",
    )

    # Create the run record.
    await storage.create_run(sample_run)
    fetched = await storage.get_run(sample_run.run_id)
    assert fetched is not None
    assert fetched.run_id == sample_run.run_id
    assert fetched.status == "completed"

    # List runs by agent and thread.
    runs_for_agent = await storage.list_runs_for_agent(sample_run.agent_id)
    assert any(r.run_id == sample_run.run_id for r in runs_for_agent)

    runs_for_thread = await storage.list_runs_for_thread(sample_run.thread_id)
    assert any(r.run_id == sample_run.run_id for r in runs_for_thread)

    # Update (upsert) the run.
    updated_run = Run.model_validate(
        sample_run.model_dump() | {"status": "cancelled"},
    )
    await storage.upsert_run(updated_run)
    updated_run = await storage.get_run(sample_run.run_id)
    assert updated_run is not None
    assert updated_run.status == "cancelled"

    # Delete the run and verify deletion.
    await storage.delete_run(sample_run.run_id)
    with pytest.raises(RunNotFoundError):
        await storage.get_run(sample_run.run_id)
    with pytest.raises(RunNotFoundError):
        await storage.delete_run(sample_run.run_id)


@pytest.mark.asyncio
async def test_run_step_crud_operations(
    storage: PostgresStorage,
    sample_user_id: str,
    sample_agent: Agent,
    sample_thread: Thread,
) -> None:
    """
    Test creating a run step, listing by run_id, and retrieving by step_id.
    """
    # Ensure the agent and thread exist.
    await storage.upsert_agent(sample_user_id, sample_agent)
    await storage.upsert_thread(sample_user_id, sample_thread)

    sample_run = Run(
        run_id=str(uuid4()),
        agent_id=sample_agent.agent_id,
        thread_id=sample_thread.thread_id,
        created_at=datetime.now(UTC),
        finished_at=None,
        status="completed",
        metadata={"info": "run test"},
        run_type="async",
    )
    # Create the run record.
    await storage.create_run(sample_run)

    sample_run_step = RunStep(
        run_id=sample_run.run_id,
        step_id=str(uuid4()),
        step_status="completed",
        sequence_number=0,
        input_state_hash="hash_input",
        input_state={"input": "value"},
        output_state_hash="hash_output",
        output_state={"output": "result"},
        metadata={"step_info": "test"},
        created_at=datetime.now(UTC),
        finished_at=None,
    )
    # Create the run step.
    await storage.create_run_step(sample_run_step)

    # List run steps for the given run_id and verify our step is included.
    steps = await storage.list_run_steps(sample_run.run_id)
    assert any(s.step_id == sample_run_step.step_id for s in steps)

    # Retrieve by step_id.
    fetched_step = await storage.get_run_step(sample_run_step.step_id)
    assert fetched_step is not None
    assert fetched_step.step_id == sample_run_step.step_id


@pytest.mark.asyncio
async def test_run_list_empty(storage: PostgresStorage) -> None:
    """
    Test that listing runs for a non-existent agent/thread returns an empty list.
    """
    non_existent = str(uuid4())
    runs_agent = await storage.list_runs_for_agent(non_existent)
    runs_thread = await storage.list_runs_for_thread(non_existent)
    assert runs_agent == []
    assert runs_thread == []


@pytest.mark.asyncio
async def test_invalid_uuid_run(storage: PostgresStorage) -> None:
    """
    Test that providing an invalid UUID for a run operation raises InvalidUUIDError.
    """
    with pytest.raises(InvalidUUIDError):
        await storage.get_run("not-a-uuid")


@pytest.mark.asyncio
async def test_run_deletion_cascades_run_steps(
    storage: PostgresStorage,
    sample_user_id: str,
    sample_agent: Agent,
    sample_thread: Thread,
) -> None:
    """
    Test that deleting a run record cascades to delete its associated run steps.
    """
    # Ensure the agent and thread exist.
    await storage.upsert_agent(sample_user_id, sample_agent)
    await storage.upsert_thread(sample_user_id, sample_thread)

    # Create a run.
    sample_run = Run(
        run_id=str(uuid4()),
        agent_id=sample_agent.agent_id,
        thread_id=sample_thread.thread_id,
        created_at=datetime.now(UTC),
        finished_at=None,
        status="completed",
        metadata={"info": "cascade deletion test"},
        run_type="async",
    )
    await storage.create_run(sample_run)

    # Create a run step associated with the run.
    sample_run_step = RunStep(
        run_id=sample_run.run_id,
        step_id=str(uuid4()),
        step_status="completed",
        sequence_number=1,
        input_state_hash="hash_input",
        input_state={"input": "value"},
        output_state_hash="hash_output",
        output_state={"output": "result"},
        metadata={"step_info": "cascade deletion test"},
        created_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )
    await storage.create_run_step(sample_run_step)

    # Verify the run step exists.
    fetched_step = await storage.get_run_step(sample_run_step.step_id)
    assert fetched_step is not None

    # Delete the run.
    await storage.delete_run(sample_run.run_id)

    # After deleting the run, the run step should have been cascaded away.
    with pytest.raises(RunStepNotFoundError):
        await storage.get_run_step(sample_run_step.step_id)


@pytest.mark.asyncio
async def test_run_update_invalid_foreign_keys(
    storage: PostgresStorage,
    sample_user_id: str,
    sample_agent: Agent,
    sample_thread: Thread,
) -> None:
    """
    Test that updating a run with non-existent agent_id or thread_id is rejected.
    """
    # Create valid agent and thread.
    await storage.upsert_agent(sample_user_id, sample_agent)
    await storage.upsert_thread(sample_user_id, sample_thread)
    valid_run = Run(
        run_id=str(uuid4()),
        agent_id=sample_agent.agent_id,
        thread_id=sample_thread.thread_id,
        created_at=datetime.now(UTC),
        finished_at=None,
        status="completed",
        metadata={"info": "foreign key test"},
        run_type="async",
    )
    await storage.create_run(valid_run)

    # Modify run with invalid foreign keys.
    invalid_run = Run.model_validate(
        valid_run.model_dump() | {"agent_id": str(uuid4()), "thread_id": str(uuid4())},
    )
    with pytest.raises(ReferenceIntegrityError):
        await storage.upsert_run(invalid_run)


@pytest.mark.asyncio
async def test_run_not_found_error(storage: PostgresStorage) -> None:
    """
    Test that attempting to delete a non-existent run raises RunNotFoundError.
    """
    non_existent_run_id = str(uuid4())
    with pytest.raises(RunNotFoundError):
        await storage.get_run(non_existent_run_id)
    with pytest.raises(RunNotFoundError):
        await storage.delete_run(non_existent_run_id)


@pytest.mark.asyncio
async def test_run_reupsert_idempotency(
    storage: PostgresStorage,
    sample_user_id: str,
    sample_agent: Agent,
    sample_thread: Thread,
) -> None:
    """
    Create a run and repeatedly update it using upsert.
    Verify that no duplicate records are created and that
    the final state reflects the last update.
    """
    # Ensure the agent and thread exist.
    await storage.upsert_agent(sample_user_id, sample_agent)
    await storage.upsert_thread(sample_user_id, sample_thread)

    initial_run = Run(
        run_id=str(uuid4()),
        agent_id=sample_agent.agent_id,
        thread_id=sample_thread.thread_id,
        created_at=datetime.now(UTC),
        finished_at=None,
        status="created",
        metadata={"info": "reupsert test"},
        run_type="sync",
    )
    await storage.create_run(initial_run)

    # Repeatedly update the run with new status values.
    statuses = ["completed", "cancelled", "failed"]
    for status in statuses:
        current_run = await storage.get_run(initial_run.run_id)
        updated_run = Run.model_validate(
            current_run.model_dump()
            | {
                "status": status,
                "finished_at": datetime.now(UTC),
            },
        )
        await storage.upsert_run(updated_run)

    final_run = await storage.get_run(initial_run.run_id)
    assert final_run.status == "failed", "The final run status should be 'failed'"


@pytest.mark.asyncio
async def test_run_ordering(
    storage: PostgresStorage,
    sample_user_id: str,
    sample_agent: Agent,
    sample_thread: Thread,
) -> None:
    """
    Create several runs for the same agent with slight delays.
    Then list runs for that agent and verify they are
    ordered by the created_at timestamp.
    """
    # Ensure the agent and thread exist.
    await storage.upsert_agent(sample_user_id, sample_agent)
    await storage.upsert_thread(sample_user_id, sample_thread)

    run_ids = []
    # Create three runs with a small delay in between to ensure different timestamps.
    for i in range(3):
        run = Run(
            run_id=str(uuid4()),
            agent_id=sample_agent.agent_id,
            thread_id=sample_thread.thread_id,
            created_at=datetime.now(UTC),
            finished_at=None,
            status="cancelled",
            metadata={"info": f"ordering test {i}"},
            run_type="sync",
        )
        await storage.create_run(run)
        run_ids.append(run.run_id)
        await asyncio.sleep(0.01)

    # Retrieve all runs for the agent.
    runs = await storage.list_runs_for_agent(sample_agent.agent_id)
    # Filter to only those runs created in this test.
    created_runs = [r for r in runs if r.run_id in run_ids]

    # Check that the runs are in ascending order by created_at.
    for i in range(1, len(created_runs)):
        assert created_runs[i - 1].created_at <= created_runs[i].created_at, (
            "Runs are not ordered by created_at ascending"
        )


@pytest.mark.asyncio
async def test_concurrent_run_creation(
    storage: PostgresStorage,
    sample_user_id: str,
    sample_agent: Agent,
    sample_thread: Thread,
) -> None:
    """
    Create multiple run records concurrently and verify that:
      - Each created run can be fetched and has the correct status.
      - All created runs appear in the listing for the given agent.
    """

    async def create_run():
        run = Run(
            run_id=str(uuid4()),
            agent_id=sample_agent.agent_id,
            thread_id=sample_thread.thread_id,
            created_at=datetime.now(UTC),
            finished_at=None,
            status="running",
            metadata={"info": "concurrent test"},
            run_type="async",
        )
        await storage.create_run(run)
        return run.run_id

    # Ensure the agent and thread exist.
    await storage.upsert_agent(sample_user_id, sample_agent)
    await storage.upsert_thread(sample_user_id, sample_thread)

    # Launch concurrent run creations.
    run_ids = await asyncio.gather(*(create_run() for _ in range(5)))

    # Verify that each run can be retrieved and has the expected status.
    for run_id in run_ids:
        run = await storage.get_run(run_id)
        assert run is not None, f"Run with ID {run_id} not found"
        assert run.status == "running", f"Run with ID {run_id} has incorrect status"

    # Check that the created runs appear in the listing for the agent.
    runs = await storage.list_runs_for_agent(sample_agent.agent_id)
    listed_run_ids = {r.run_id for r in runs}
    for run_id in run_ids:
        assert run_id in listed_run_ids, (
            f"Run with ID {run_id} is not listed in agent runs"
        )
