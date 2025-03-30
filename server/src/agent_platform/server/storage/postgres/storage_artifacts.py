from datetime import datetime, timedelta

from psycopg.errors import IntegrityError

from agent_platform.core.kernel_interfaces.otel import OTelArtifact
from agent_platform.server.storage.errors import (
    ArtifactNotFoundError,
    RecordAlreadyExistsError,
)
from agent_platform.server.storage.postgres.common import CommonMixin


class PostgresStorageArtifactsMixin(CommonMixin):
    """Mixin for PostgreSQL artifact operations."""

    async def create_otel_artifact(self, artifact: OTelArtifact) -> None:
        """Create a new artifact."""
        self._validate_uuid(artifact.artifact_id)
        async with self._cursor() as cur:
            try:
                await cur.execute(
                    """
                    INSERT INTO v2.otel_artifact (
                        artifact_id, name, mime_type, content, to_be_deleted_at,
                        trace_id, correlated_user_id, correlated_agent_id,
                        correlated_thread_id, correlated_run_id,
                        correlated_message_id
                    )
                    VALUES (
                        %(artifact_id)s, %(name)s, %(mime_type)s,
                        %(content)s, %(to_be_deleted_at)s,
                        %(trace_id)s, %(correlated_user_id)s,
                        %(correlated_agent_id)s, %(correlated_thread_id)s,
                        %(correlated_run_id)s, %(correlated_message_id)s
                    )
                    """,
                    {
                        "artifact_id": artifact.artifact_id,
                        "name": artifact.name,
                        "mime_type": artifact.mime_type,
                        "content": artifact.content,
                        "to_be_deleted_at": datetime.now() + timedelta(days=7),
                        "trace_id": artifact.trace_id,
                        "correlated_user_id": artifact.correlated_user_id,
                        "correlated_agent_id": artifact.correlated_agent_id,
                        "correlated_thread_id": artifact.correlated_thread_id,
                        "correlated_run_id": artifact.correlated_run_id,
                        "correlated_message_id": artifact.correlated_message_id,
                    },
                )
            except IntegrityError as e:
                raise RecordAlreadyExistsError(
                    f"Artifact {artifact.artifact_id} already exists",
                ) from e

    async def get_otel_artifact(self, artifact_id: str) -> OTelArtifact:
        """Get an artifact by ID."""
        self._validate_uuid(artifact_id)
        async with self._cursor() as cur:
            await cur.execute(
                """
                SELECT * FROM v2.otel_artifact WHERE artifact_id = %(artifact_id)s
                """,
                {"artifact_id": artifact_id},
            )
            row = await cur.fetchone()
            if not row:
                raise ArtifactNotFoundError(f"Artifact {artifact_id} not found")
            return OTelArtifact.model_validate(row)

    async def get_otel_artifacts(
        self,
        artifact_ids: list[str] | None = None,
    ) -> list[OTelArtifact]:
        """Get a list of otel artifacts by IDs or all if ids is None."""
        async with self._cursor() as cur:
            await cur.execute(
                """
                SELECT * FROM v2.otel_artifact
                WHERE %(artifact_ids)s IS NULL OR artifact_id = ANY(%(artifact_ids)s)
                """,
                {"artifact_ids": artifact_ids},
            )
            rows = await cur.fetchall()
            return [OTelArtifact.model_validate(row) for row in rows]

    async def search_otel_artifacts(  # noqa: PLR0913
        self,
        trace_id: str | None = None,
        user_id: str | None = None,
        agent_id: str | None = None,
        thread_id: str | None = None,
        run_id: str | None = None,
        message_id: str | None = None,
    ) -> list[OTelArtifact]:
        """Search for otel artifacts by the given correlation IDs."""
        if trace_id is not None:
            self._validate_uuid(trace_id)
        if user_id is not None:
            self._validate_uuid(user_id)
        if agent_id is not None:
            self._validate_uuid(agent_id)
        if thread_id is not None:
            self._validate_uuid(thread_id)
        if run_id is not None:
            self._validate_uuid(run_id)
        if message_id is not None:
            self._validate_uuid(message_id)

        async with self._cursor() as cur:
            await cur.execute(
                """
                SELECT * FROM v2.otel_artifact
                WHERE (
                    (trace_id = %(trace_id)s OR %(trace_id)s IS NULL) AND
                    (correlated_user_id = %(user_id)s OR %(user_id)s IS NULL) AND
                    (correlated_agent_id = %(agent_id)s OR %(agent_id)s IS NULL) AND
                    (correlated_thread_id = %(thread_id)s OR %(thread_id)s IS NULL) AND
                    (correlated_run_id = %(run_id)s OR %(run_id)s IS NULL) AND
                    (correlated_message_id = %(message_id)s OR %(message_id)s IS NULL)
                )
                """,
                {
                    "trace_id": trace_id,
                    "user_id": user_id,
                    "agent_id": agent_id,
                    "thread_id": thread_id,
                    "run_id": run_id,
                    "message_id": message_id,
                },
            )
            rows = await cur.fetchall()
            return [OTelArtifact.model_validate(row) for row in rows]

    async def cleanup_otel_artifacts(self) -> int:
        """Cleanup expired artifacts."""
        async with self._cursor() as cur:
            await cur.execute(
                """
                DELETE FROM v2.otel_artifact WHERE to_be_deleted_at < CURRENT_TIMESTAMP
                """,
            )
            return cur.rowcount

    async def delete_all_otel_artifacts(self) -> int:
        """Delete all otel artifacts."""
        async with self._cursor() as cur:
            await cur.execute("DELETE FROM v2.otel_artifact")
            return cur.rowcount
