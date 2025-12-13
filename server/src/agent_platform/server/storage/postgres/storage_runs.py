import json

from psycopg.errors import ForeignKeyViolation, UniqueViolation
from psycopg.types.json import Jsonb

from agent_platform.core.runs import Run, RunStep
from agent_platform.server.storage.common import CommonMixin
from agent_platform.server.storage.errors import (
    RecordAlreadyExistsError,
    ReferenceIntegrityError,
    RunNotFoundError,
    RunStepNotFoundError,
)
from agent_platform.server.storage.postgres.cursor import CursorMixin


class PostgresStorageRunsMixin(CursorMixin, CommonMixin):
    """
    Mixin providing PostgreSQL-based run and run step operations.

    This mixin implements methods to create, retrieve, list, upsert, and delete
    run records, as well as to create, list, and retrieve run step records.
    It assumes that a working `_cursor()` (which yields an async psycopg cursor)
    and `_validate_uuid()` method (for validating UUID strings) are available
    from the inherited CommonMixin.

    The PostgreSQL schema for runs is defined in the v2.agent_runs table,
    and for run steps in the v2.agent_run_steps table. JSON data is stored using
    PostgreSQL's native JSONB type.
    """

    # ---------------------------
    # Runs
    # ---------------------------
    async def create_run(self, run: Run) -> None:
        """Insert a new run record into the database."""
        self._validate_uuid(run.run_id)
        run_dict = run.model_dump()
        # Wrap the metadata dictionary in a Jsonb object so
        # that psycopg handles it properly.
        run_dict["metadata"] = Jsonb(run_dict["metadata"])
        try:
            async with self._cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO v2."agent_runs" (
                        run_id, agent_id, thread_id,
                        created_at, finished_at, status,
                        metadata, run_type
                    )
                    VALUES (
                        %(run_id)s, %(agent_id)s, %(thread_id)s,
                        %(created_at)s, %(finished_at)s, %(status)s,
                        %(metadata)s, %(run_type)s
                    )
                    """,
                    run_dict,
                )
        except UniqueViolation as e:
            if "duplicate key value violates unique constraint" in str(e):
                raise RecordAlreadyExistsError(
                    f"Run {run.run_id} already exists",
                ) from e
            raise e
        except ForeignKeyViolation as e:
            raise ReferenceIntegrityError(
                "Invalid foreign key reference updating run",
            ) from e
        except Exception:
            raise

    async def get_run(self, run_id: str) -> Run:
        """Retrieve a run record by its ID."""
        self._validate_uuid(run_id)
        async with self._cursor() as cur:
            await cur.execute(
                """
                SELECT *
                FROM v2."agent_runs"
                WHERE run_id = %(run_id)s
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
                FROM v2."agent_runs"
                WHERE agent_id = %(agent_id)s
                ORDER BY created_at
                """,
                {"agent_id": agent_id},
            )
            rows = await cur.fetchall()
        return [Run.model_validate(self._convert_run_json_fields(dict(row))) for row in rows]

    async def list_runs_for_thread(self, thread_id: str) -> list[Run]:
        """List all runs associated with a given thread."""
        self._validate_uuid(thread_id)
        async with self._cursor() as cur:
            await cur.execute(
                """
                SELECT *
                FROM v2."agent_runs"
                WHERE thread_id = %(thread_id)s
                ORDER BY created_at
                """,
                {"thread_id": thread_id},
            )
            rows = await cur.fetchall()
        return [Run.model_validate(self._convert_run_json_fields(dict(row))) for row in rows]

    async def upsert_run(self, run: Run) -> None:
        """Insert or update a run record in the database."""
        self._validate_uuid(run.run_id)
        run_dict = run.model_dump()
        # Wrap the metadata field in Jsonb for Postgres handling.
        run_dict["metadata"] = Jsonb(run_dict["metadata"])
        try:
            async with self._cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO v2."agent_runs" (
                        run_id, agent_id, thread_id,
                        created_at, finished_at, status,
                        metadata, run_type
                    )
                    VALUES (
                        %(run_id)s, %(agent_id)s, %(thread_id)s,
                        %(created_at)s, %(finished_at)s, %(status)s,
                        %(metadata)s, %(run_type)s
                    )
                    ON CONFLICT (run_id) DO UPDATE SET
                        agent_id = EXCLUDED.agent_id,
                        thread_id = EXCLUDED.thread_id,
                        finished_at = EXCLUDED.finished_at,
                        status = EXCLUDED.status,
                        metadata = EXCLUDED.metadata,
                        run_type = EXCLUDED.run_type
                    """,
                    run_dict,
                )
        except UniqueViolation as e:
            if "duplicate key value violates unique constraint" in str(e):
                raise RecordAlreadyExistsError(
                    f"Run {run.run_id} already exists",
                ) from e
            raise e
        except ForeignKeyViolation as e:
            raise ReferenceIntegrityError(
                "Invalid foreign key reference updating run",
            ) from e
        except Exception:
            raise

    async def delete_run(self, run_id: str) -> None:
        """
        Delete a run record from the database.

        Raises:
            RunNotFoundError: If no run with the given run_id exists.
        """
        self._validate_uuid(run_id)
        async with self._cursor() as cur:
            await cur.execute(
                """
                DELETE FROM v2."agent_runs"
                WHERE run_id = %(run_id)s
                """,
                {"run_id": run_id},
            )
            if cur.rowcount == 0:
                raise RunNotFoundError(f"Run {run_id} not found")

    def _convert_run_json_fields(self, run_dict: dict) -> dict:
        """
        Convert JSON fields in a run record to Python objects if necessary.

        In PostgreSQL with psycopg using a dict row factory, JSONB columns are generally
        returned as Python objects. This helper checks and converts them if needed.
        """
        if "metadata" in run_dict and isinstance(run_dict["metadata"], str):
            run_dict["metadata"] = json.loads(run_dict["metadata"])
        return run_dict

    # ---------------------------
    # Run Steps
    # ---------------------------
    async def create_run_step(self, run_step: RunStep) -> None:
        """Insert a new run step record into the database."""
        self._validate_uuid(run_step.step_id)
        run_step_dict = run_step.model_dump()
        # Wrap JSON fields in Jsonb
        run_step_dict["input_state"] = Jsonb(run_step_dict["input_state"])
        run_step_dict["output_state"] = Jsonb(run_step_dict["output_state"])
        run_step_dict["metadata"] = Jsonb(run_step_dict["metadata"])
        try:
            async with self._cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO v2."agent_run_steps" (
                        run_id, step_id, step_status,
                        sequence_number, input_state_hash, input_state,
                        output_state_hash, output_state, metadata,
                        created_at, finished_at
                    )
                    VALUES (
                        %(run_id)s, %(step_id)s, %(step_status)s,
                        %(sequence_number)s, %(input_state_hash)s, %(input_state)s,
                        %(output_state_hash)s, %(output_state)s, %(metadata)s,
                        %(created_at)s, %(finished_at)s
                    )
                    """,
                    run_step_dict,
                )
        except UniqueViolation as e:
            if "duplicate key value violates unique constraint" in str(e):
                raise RecordAlreadyExistsError(
                    f"Run step {run_step.step_id} already exists",
                ) from e
            raise e
        except ForeignKeyViolation as e:
            raise ReferenceIntegrityError(
                "Invalid foreign key reference updating run step",
            ) from e
        except Exception:
            raise

    async def list_run_steps(self, run_id: str) -> list[RunStep]:
        """List all run steps for a given run, ordered by sequence number."""
        self._validate_uuid(run_id)
        async with self._cursor() as cur:
            await cur.execute(
                """
                SELECT *
                FROM v2."agent_run_steps"
                WHERE run_id = %(run_id)s
                ORDER BY sequence_number
                """,
                {"run_id": run_id},
            )
            rows = await cur.fetchall()
        return [RunStep.model_validate(self._convert_run_step_json_fields(dict(row))) for row in rows]

    async def get_run_step(self, step_id: str) -> RunStep:
        """Retrieve a run step record by its ID."""
        self._validate_uuid(step_id)
        async with self._cursor() as cur:
            await cur.execute(
                """
                SELECT *
                FROM v2."agent_run_steps"
                WHERE step_id = %(step_id)s
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
        """
        Convert JSON fields in a run step record to Python objects if necessary.

        Checks the 'input_state', 'output_state', and 'metadata' fields for
        string values, converting them to dictionaries if needed.
        """
        for field in ["input_state", "output_state", "metadata"]:
            if field in run_step_dict and isinstance(run_step_dict[field], str):
                run_step_dict[field] = json.loads(run_step_dict[field])
        return run_step_dict
