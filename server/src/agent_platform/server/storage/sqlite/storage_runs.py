import json

from aiosqlite import IntegrityError
from structlog import get_logger

from agent_platform.core.runs import Run, RunStep
from agent_platform.server.storage.errors import (
    RecordAlreadyExistsError,
    ReferenceIntegrityError,
    RunNotFoundError,
    RunStepNotFoundError,
)
from agent_platform.server.storage.sqlite.common import CommonMixin


class SQLiteStorageRunsMixin(CommonMixin):
    """
    Mixin providing SQLite-based run and run step operations.
    Assumes that helper methods such as `_cursor()` and
    `_validate_uuid()` are available.
    """

    _logger = get_logger(__name__)

    # ---------------------------
    # Runs
    # ---------------------------
    async def create_run(self, run: Run) -> None:
        """Insert a new run record."""
        self._validate_uuid(run.run_id)
        run_dict = run.model_dump()
        # Convert the metadata dict to a JSON string
        run_dict["metadata"] = json.dumps(run_dict["metadata"])
        try:
            async with self._cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO v2_agent_runs (
                        run_id, agent_id, thread_id,
                        created_at, finished_at, status,
                        metadata, run_type
                    )
                    VALUES (
                        :run_id, :agent_id, :thread_id,
                        :created_at, :finished_at, :status,
                        :metadata, :run_type
                    )
                    """,
                    run_dict,
                )
        except IntegrityError as e:
            if "UNIQUE constraint failed: v2_agent_runs.run_id" in str(e):
                raise RecordAlreadyExistsError(
                    f"Run {run.run_id} already exists",
                ) from e
            raise ReferenceIntegrityError(
                "Invalid foreign key reference updating run",
            ) from e

    async def get_run(self, run_id: str) -> Run:
        """Retrieve a run record by its ID."""
        self._validate_uuid(run_id)
        async with self._cursor() as cur:
            await cur.execute(
                """
                SELECT *
                FROM v2_agent_runs
                WHERE run_id = :run_id
                """,
                {"run_id": run_id},
            )
            row = await cur.fetchone()
        if not row:
            raise RunNotFoundError(f"Run {run_id} not found")
        run_dict = dict(row)
        run_dict = self._convert_run_json_fields(run_dict)
        return Run.model_validate(run_dict)

    async def list_runs_for_agent(self, agent_id: str) -> list[Run]:
        """List all runs associated with a given agent."""
        self._validate_uuid(agent_id)
        async with self._cursor() as cur:
            await cur.execute(
                """
                SELECT *
                FROM v2_agent_runs
                WHERE agent_id = :agent_id
                ORDER BY created_at
                """,
                {"agent_id": agent_id},
            )
            rows = await cur.fetchall()
        if not rows:
            return []
        return [Run.model_validate(self._convert_run_json_fields(dict(r))) for r in rows]

    async def list_runs_for_thread(self, thread_id: str) -> list[Run]:
        """List all runs associated with a given thread."""
        self._validate_uuid(thread_id)
        async with self._cursor() as cur:
            await cur.execute(
                """
                SELECT *
                FROM v2_agent_runs
                WHERE thread_id = :thread_id
                ORDER BY created_at
                """,
                {"thread_id": thread_id},
            )
            rows = await cur.fetchall()
        if not rows:
            return []
        return [Run.model_validate(self._convert_run_json_fields(dict(r))) for r in rows]

    async def upsert_run(self, run: Run) -> None:
        """Insert or update a run record."""
        self._validate_uuid(run.run_id)
        run_dict = run.model_dump()
        run_dict["metadata"] = json.dumps(run_dict["metadata"])
        try:
            async with self._cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO v2_agent_runs (
                        run_id, agent_id, thread_id,
                        created_at, finished_at, status,
                        metadata, run_type
                    )
                    VALUES (
                        :run_id, :agent_id, :thread_id,
                        :created_at, :finished_at, :status,
                        :metadata, :run_type
                    )
                    ON CONFLICT(run_id) DO UPDATE SET
                        agent_id = excluded.agent_id,
                        thread_id = excluded.thread_id,
                        finished_at = excluded.finished_at,
                        status = excluded.status,
                        metadata = excluded.metadata,
                        run_type = excluded.run_type
                    """,
                    run_dict,
                )
                if cur.rowcount == 0:
                    self._logger.warning("Upsert run had no effect", run_id=run.run_id)
        except IntegrityError as e:
            if "UNIQUE constraint failed: v2_agent_runs.run_id" in str(e):
                raise RecordAlreadyExistsError(
                    f"Run {run.run_id} already exists",
                ) from e
            raise ReferenceIntegrityError(
                "Invalid foreign key reference updating run",
            ) from e

    async def delete_run(self, run_id: str) -> None:
        """Delete a run record. Raises RunNotFoundError if the run does not exist."""
        self._validate_uuid(run_id)
        async with self._cursor() as cur:
            await cur.execute(
                """
                DELETE FROM v2_agent_runs
                WHERE run_id = :run_id
                """,
                {"run_id": run_id},
            )
            if cur.rowcount == 0:
                raise RunNotFoundError(f"Run {run_id} not found")

    def _convert_run_json_fields(self, run_dict: dict) -> dict:
        """Convert JSON string fields in a run record to Python objects."""
        if run_dict.get("metadata") is not None:
            run_dict["metadata"] = json.loads(run_dict["metadata"])
        else:
            run_dict["metadata"] = {}
        return run_dict

    # ---------------------------
    # Run Steps
    # ---------------------------
    async def create_run_step(self, run_step: RunStep) -> None:
        """Insert a new run step record."""
        self._validate_uuid(run_step.step_id)
        run_step_dict = run_step.model_dump()
        run_step_dict["input_state"] = json.dumps(run_step_dict["input_state"])
        run_step_dict["output_state"] = json.dumps(run_step_dict["output_state"])
        run_step_dict["metadata"] = json.dumps(run_step_dict["metadata"])
        try:
            async with self._cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO v2_agent_run_steps (
                        run_id, step_id, step_status,
                        sequence_number, input_state_hash, input_state,
                        output_state_hash, output_state, metadata,
                        created_at, finished_at
                    )
                    VALUES (
                        :run_id, :step_id, :step_status,
                        :sequence_number, :input_state_hash, :input_state,
                        :output_state_hash, :output_state, :metadata,
                        :created_at, :finished_at
                    )
                    """,
                    run_step_dict,
                )
        except IntegrityError as e:
            if "UNIQUE constraint failed: v2_agent_run_steps.step_id" in str(e):
                raise RecordAlreadyExistsError(
                    f"Run step {run_step.step_id} already exists",
                ) from e
            raise ReferenceIntegrityError(
                "Invalid foreign key reference updating run step",
            ) from e

    async def list_run_steps(self, run_id: str) -> list[RunStep]:
        """List all run steps for a given run (ordered by sequence number)."""
        self._validate_uuid(run_id)
        async with self._cursor() as cur:
            await cur.execute(
                """
                SELECT *
                FROM v2_agent_run_steps
                WHERE run_id = :run_id
                ORDER BY sequence_number
                """,
                {"run_id": run_id},
            )
            rows = await cur.fetchall()
        if not rows:
            return []
        return [RunStep.model_validate(self._convert_run_step_json_fields(dict(r))) for r in rows]

    async def get_run_step(self, step_id: str) -> RunStep:
        """Retrieve a run step record by its ID."""
        self._validate_uuid(step_id)
        async with self._cursor() as cur:
            await cur.execute(
                """
                SELECT *
                FROM v2_agent_run_steps
                WHERE step_id = :step_id
                """,
                {"step_id": step_id},
            )
            row = await cur.fetchone()
        if not row:
            raise RunStepNotFoundError(f"Run step {step_id} not found")
        run_step_dict = dict(row)
        run_step_dict = self._convert_run_step_json_fields(run_step_dict)
        return RunStep.model_validate(run_step_dict)

    def _convert_run_step_json_fields(self, run_step_dict: dict) -> dict:
        """Convert JSON string fields in a run step record to Python objects."""
        for field in ["input_state", "output_state", "metadata"]:
            if run_step_dict.get(field) is not None:
                run_step_dict[field] = json.loads(run_step_dict[field])
            else:
                run_step_dict[field] = {}
        return run_step_dict
