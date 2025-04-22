from abc import ABC, abstractmethod
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from uuid import uuid4

from opentelemetry.trace import Span, SpanContext, Status, StatusCode
from opentelemetry.util import types

from agent_platform.core.kernel_interfaces.kernel_mixin import UsesKernelMixin


@dataclass(frozen=True)
class OTelArtifact:
    """Stores information about an artifact to be linked to a span.

    Artifacts are used to represent larger bits of relevant information
    that can be linked to a span. This is useful for things like prompts,
    runbooks, files, images, etc.
    """

    name: str = field(metadata={"description": "The name of the artifact"})
    """The name of the artifact"""

    mime_type: str = field(metadata={"description": "The mime type of the artifact"})
    """The mime type of the artifact"""

    content: bytes = field(
        metadata={
            "description": ("The content of the artifact, which must be bytes"),
        },
    )
    """The content of the artifact, which must be bytes"""

    trace_id: str = field(
        metadata={
            "description": (
                "The trace ID to tie this artifact back to the original trace"
            ),
        },
    )
    """The trace ID to tie this artifact back to the original trace"""

    artifact_id: str = field(
        default_factory=lambda: str(uuid4()),
        metadata={"description": "The ID of the artifact"},
    )
    """The ID of the artifact"""

    correlated_user_id: str | None = field(
        default=None,
        metadata={"description": "The user ID to correlate the artifact to"},
    )
    """The user ID to correlate the artifact to"""

    correlated_agent_id: str | None = field(
        default=None,
        metadata={"description": "The agent ID to correlate the artifact to"},
    )
    """The agent ID to correlate the artifact to"""

    correlated_thread_id: str | None = field(
        default=None,
        metadata={"description": "The thread ID to correlate the artifact to"},
    )
    """The thread ID to correlate the artifact to"""

    correlated_run_id: str | None = field(
        default=None,
        metadata={"description": "The run ID to correlate the artifact to"},
    )
    """The run ID to correlate the artifact to"""

    correlated_message_id: str | None = field(
        default=None,
        metadata={"description": "The message ID to correlate the artifact to"},
    )
    """The message ID to correlate the artifact to"""

    def model_dump(self) -> dict:
        return {
            "name": self.name,
            "mime_type": self.mime_type,
            "content": self.content,
            "artifact_id": self.artifact_id,
            "trace_id": self.trace_id,
            "correlated_user_id": self.correlated_user_id,
            "correlated_agent_id": self.correlated_agent_id,
            "correlated_thread_id": self.correlated_thread_id,
            "correlated_run_id": self.correlated_run_id,
            "correlated_message_id": self.correlated_message_id,
        }

    @classmethod
    def model_validate(cls, data: dict) -> "OTelArtifact":
        return cls(
            name=data["name"],
            mime_type=data["mime_type"],
            content=(
                data["content"]
                if isinstance(data["content"], bytes)
                else data["content"].encode("utf-8")
            ),
            artifact_id=data["artifact_id"],
            trace_id=data["trace_id"],
            correlated_user_id=data["correlated_user_id"],
            correlated_agent_id=data["correlated_agent_id"],
            correlated_thread_id=data["correlated_thread_id"],
            correlated_run_id=data["correlated_run_id"],
            correlated_message_id=data["correlated_message_id"],
        )


class WrappedSpan(Span):
    def __init__(self, otel_interface: "OTelInterface", span: Span):
        self.otel_interface = otel_interface
        self.kernel = otel_interface.kernel
        self.span = span

    def end(self, end_time: int | None = None) -> None:
        self.span.end(end_time)

    def get_span_context(self) -> SpanContext:
        return self.span.get_span_context()

    def set_attributes(self, attributes: Mapping[str, types.AttributeValue]) -> None:
        self.span.set_attributes(attributes)

    def set_attribute(self, key: str, value: types.AttributeValue) -> None:
        self.span.set_attribute(key, value)

    def add_event(
        self,
        name: str,
        attributes: types.Attributes | None = None,
        timestamp: int | None = None,
    ) -> None:
        self.span.add_event(name, attributes=attributes, timestamp=timestamp)

    def update_name(self, name: str) -> None:
        self.span.update_name(name)

    def is_recording(self) -> bool:
        return self.span.is_recording()

    def set_status(
        self,
        status: Status | StatusCode,
        description: str | None = None,
    ) -> None:
        self.span.set_status(status, description)

    def record_exception(
        self,
        exception: BaseException,
        attributes: types.Attributes = None,
        timestamp: int | None = None,
        escaped: bool = False,
    ) -> None:
        self.span.record_exception(
            exception,
            attributes=attributes,
            timestamp=timestamp,
            escaped=escaped,
        )

    def add_event_with_artifacts(
        self,
        name: str,
        *artifacts: tuple[str, str | bytes],
        attributes: dict[str, types.AttributeValue] | None = None,
    ):
        """Add an event to the span with the given name and artifacts.

        The artifacts will be linked to the span and the event will
        have the artifact ids included in the attributes. Artifact creation
        happens asynchronously in the background without blocking.
        """
        from mimetypes import guess_type

        # Infer mime type from file extension
        mime_types = []
        for artifact_name, _ in artifacts:
            mime_type = guess_type(artifact_name)[0]
            if mime_type is None:
                # Put in some of these fallbacks, as I've found on OSX
                # guess_type doesn't always work for yaml...
                if artifact_name.endswith(".json"):
                    mime_type = "application/json"
                elif artifact_name.endswith(".yaml"):
                    mime_type = "text/yaml"
                elif artifact_name.endswith(".yml"):
                    mime_type = "text/yaml"
                else:
                    raise ValueError(
                        f"Could not infer mime type for artifact {artifact_name}",
                    )
            mime_types.append(mime_type)

        # Generate artifact IDs upfront
        artifact_id_map = {}
        for artifact_name, _ in artifacts:
            artifact_id = str(uuid4())
            artifact_id_map[f"{artifact_name}_aid"] = artifact_id

        # Add the event with the artifact IDs immediately
        self.span.add_event(
            name,
            attributes={
                **(attributes or {}),
                **artifact_id_map,
            },
        )

        # Enqueue artifact creation tasks
        for i, (artifact_name, artifact_content) in enumerate(artifacts):
            self.otel_interface.enqueue_artifact_creation(
                artifact_name,
                mime_types[i],
                artifact_content,
                artifact_id=artifact_id_map[f"{artifact_name}_aid"],
            )


class OTelInterface(ABC, UsesKernelMixin):
    @abstractmethod
    @contextmanager
    def span(
        self,
        name: str,
        attributes: dict[str, types.AttributeValue] | None = None,
    ) -> Generator[WrappedSpan, None, None]:
        """Create a new span with the given name and attributes.

        The span will be active until the context manager is exited.
        """
        pass

    @property
    @abstractmethod
    def active_span(self) -> WrappedSpan:
        """The currently active span.

        If no span is active, this will raise a `RuntimeError`.
        """
        pass

    @property
    @abstractmethod
    def context(self) -> SpanContext:
        """The currently active span's context.

        If no span is active, this will raise a `RuntimeError`.
        """
        pass

    @property
    @abstractmethod
    def trace_id(self) -> str:
        """Get the trace ID of the current active span as a hex string.

        This can be used as a correlation ID to connect logs, traces,
        and other observability data across services.

        If no span is active, this will raise a `RuntimeError`.
        """
        pass

    @abstractmethod
    async def create_artifact(
        self,
        name: str,
        mime_type: str,
        content: str | bytes,
        artifact_id: str | None = None,
    ) -> OTelArtifact:
        """Create an artifact and save it to the storage.

        Use this to help link larger artifacts such as prompts,
        runbooks, files, images, etc., to the current span. This
        avoids the anti-pattern of adding large amounts of data
        to the span attributes, which can cause performance issues
        and make the span difficult to read.

        This will save the artifact to the storage and return an
        OTelArtifact object that can be used to link to the span.

        Parameters:
            name: The name of the artifact
            mime_type: The mime type of the artifact
            content: The content of the artifact
            artifact_id: Optional custom ID for the artifact. If not
                provided, a new UUID will be generated.

        Returns:
            An OTelArtifact object that can be used to link to the span.
        """
        pass

    @abstractmethod
    def enqueue_artifact_creation(
        self,
        name: str,
        mime_type: str,
        content: str | bytes,
        artifact_id: str,
    ) -> None:
        """Enqueue an artifact for creation without blocking.

        This method adds the artifact creation task to a queue that will
        be processed asynchronously. This is used by the add_event_with_artifacts
        method to avoid blocking the main thread.
        """
        pass
