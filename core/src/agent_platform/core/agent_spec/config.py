from dataclasses import dataclass, field

from agent_platform.core.configurations import Configuration, FieldMetadata


@dataclass(frozen=True)
class AgentSpecConfig(Configuration):
    max_size_bytes: int = field(
        default=50_000_000,
        metadata=FieldMetadata(description="The maximum size of the agent package in bytes."),
    )
    """The maximum size of the agent package in bytes."""

    metadata_filename: str = field(
        default="__agent_package_metadata__.json",
        metadata=FieldMetadata(description="The filename of the agent package metadata."),
    )
    """The filename of the agent package metadata."""

    agent_spec_filename: str = field(
        default="agent-spec.yaml",
        metadata=FieldMetadata(description="The filename of the agent package specification."),
    )
    """The filename of the agent package specification."""

    runbook_filename: str = field(
        default="runbook.md",
        metadata=FieldMetadata(description="The filename of the runbook."),
    )
    """The filename of the runbook."""

    knowledge_dir: str = field(
        default="knowledge/",
        metadata=FieldMetadata(description="The directory of the knowledge files."),
    )
    """The directory of the knowledge files."""

    conversation_guide_filename: str = field(
        default="conversation-guide.yaml",
        metadata=FieldMetadata(description="The filename of the conversation guide."),
    )
    """The filename of the conversation guide."""
