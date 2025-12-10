from dataclasses import dataclass, field

from agent_platform.core.configurations import FieldMetadata


@dataclass(frozen=True)
class AgentPackageConfig:
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

    actions_dirname: str = field(
        default="actions",
        metadata=FieldMetadata(description="The directory containing Action Packages."),
    )
    """The directory containing Action Packages."""

    semantic_data_models_dirname: str = field(
        default="semantic-data-models",
        metadata=FieldMetadata(description="The directory containing semantic data models."),
    )
    """The directory containing semantic data models."""

    action_package_spec_filename: str = field(
        default="package.yaml",
        metadata=FieldMetadata(description="The filename of the Action Package specification."),
    )
    """The filename of the Action Package specification."""

    action_package_metadata_filename: str = field(
        default="__action_server_metadata__.json",
        metadata=FieldMetadata(description="The filename of the Action Package metadata."),
    )
    """The filename of the Action Package metadata."""
