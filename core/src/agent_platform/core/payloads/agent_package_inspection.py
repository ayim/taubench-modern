"""Response payload for agent package inspection endpoint.

The structure follows the agent package specification defined in:
agent-spec/versions/v2/agent-package-specification-v2.json
"""

from dataclasses import dataclass, field

from agent_platform.core.agent_package.metadata.agent_metadata import AgentPackageMetadata


@dataclass(frozen=True)
class UploadedPackageInfo:
    """Information about an uploaded package file."""

    content_type: str = field(metadata={"description": "MIME type of the uploaded file."})
    size: int = field(metadata={"description": "Size of the file in bytes."})
    format: str = field(metadata={"description": "Format of the package (e.g., 'zip')."})


@dataclass(frozen=True)
class AgentPackageInspectionResponse(AgentPackageMetadata):
    """Response from agent package inspection endpoint.

    Extends AgentPackageMetadata with upload-specific information while maintaining
    a flat response structure and single source of truth for metadata fields.
    """

    uploaded_package: UploadedPackageInfo | None = field(
        default=None,
        metadata={"description": "Information about the uploaded package file, if applicable."},
    )
    """Information about the uploaded package file, if applicable."""

    @classmethod
    def from_metadata(
        cls,
        metadata: AgentPackageMetadata,
        uploaded_package: UploadedPackageInfo | None = None,
    ) -> "AgentPackageInspectionResponse":
        """Create response from AgentPackageMetadata."""
        return cls(
            release_note=metadata.release_note,
            version=metadata.version,
            icon=metadata.icon,
            name=metadata.name,
            description=metadata.description,
            model=metadata.model,
            architecture=metadata.architecture,
            reasoning=metadata.reasoning,
            knowledge=metadata.knowledge,
            datasources=metadata.datasources,
            question_groups=metadata.question_groups,
            conversation_starter=metadata.conversation_starter,
            welcome_message=metadata.welcome_message,
            metadata=metadata.metadata,
            action_packages=metadata.action_packages,
            mcp_servers=metadata.mcp_servers,
            docker_mcp_gateway=metadata.docker_mcp_gateway,
            docker_mcp_gateway_changes=metadata.docker_mcp_gateway_changes,
            agent_settings=metadata.agent_settings,
            document_intelligence=metadata.document_intelligence,
            selected_tools=metadata.selected_tools,
            uploaded_package=uploaded_package,
        )
