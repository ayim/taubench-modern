"""Agent package metadata generation.

This module provides the main entry points for generating agent package metadata
from agent packages, mirroring the Go implementation in golang-agent-cli/cmd/package_metadata.go.

The main entry point is:
- `AgentMetadataGenerator`: Class-based API for generating metadata

Architecture Overview:
    The metadata generation process:
    1. Parses the agent spec (agent-spec.yaml)
    2. Collects raw metadata from action packages
    3. Processes MCP servers, datasources, and action packages
    4. Returns AgentPackageMetadata for the single agent in the package

Note: Agent Packages must contain exactly one agent (enforced by spec validation).
"""

from __future__ import annotations

import time
from importlib.metadata import version
from typing import cast, get_args

import structlog

from agent_platform.core.agent_package.handler.action_package import ActionPackageHandler
from agent_platform.core.agent_package.handler.agent_package import AgentPackageHandler
from agent_platform.core.agent_package.metadata.agent_metadata import (
    AgentPackageActionPackageMetadata,
    AgentPackageDatasource,
    AgentPackageDockerMcpGateway,
    AgentPackageMcpServer,
    AgentPackageMetadata,
    AgentPackageMetadataKnowledge,
)
from agent_platform.core.agent_package.spec import (
    SpecActionPackage,
    SpecAgent,
    SpecAgentReasoning,
    SpecKnowledge,
    SpecMCPServer,
)
from agent_platform.core.selected_tools import SelectedToolConfig, SelectedTools

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Type alias for collection of ActionPackageHandlers
type ActionPackageHandlerByPath = tuple[str, ActionPackageHandler]


class AgentMetadataGenerator:
    """Generates agent package metadata from an agent package.

    This class orchestrates the metadata generation process, including
    parsing the agent spec, collecting action package metadata, and
    generating the final metadata structure.

    Works with in-memory zip files via AgentPackageHandler, avoiding
    disk extraction for efficient server-side processing.

    Attributes:
        _handler: Package handler for reading files from the zip.
    """

    def __init__(self, handler: AgentPackageHandler) -> None:
        """Initialize the generator with a package handler.

        Args:
            handler: Package handler for reading files from the agent package.
        """
        self._handler = handler

    async def generate(self) -> AgentPackageMetadata:
        """Generate agent metadata from the package.

        Reads the agent spec and generates comprehensive metadata for the agent,
        including action packages, MCP servers, datasources, and knowledge files.

        Returns:
            AgentPackageMetadata for the agent in the package.

        Raises:
            FileNotFoundError: If agent spec file not found.
            ValueError: If spec is invalid.
        """
        logger.debug("Reading agent spec from package...")

        agent = await self._handler.get_spec_agent()

        logger.debug(f"Processing agent: {agent.name}")

        # Gather all Action Package handlers
        action_package_handlers = await self._handler.get_action_packages_handlers()
        logger.debug(f"Found {len(action_package_handlers)} action packages")

        # Generate metadata
        metadata = await self._generate_agent_metadata(agent, action_package_handlers)

        logger.debug("Metadata generation complete")
        return metadata

    async def _generate_agent_metadata(
        self, agent: SpecAgent, action_package_handlers: list[ActionPackageHandlerByPath]
    ) -> AgentPackageMetadata:
        """Generate metadata for the agent from the spec and action package handlers.

        Args:
            agent: The agent from the spec.
            action_package_handlers: List of tuples containing the action package path and handler.

        Returns:
            AgentPackageMetadata for the agent in the package.
        """
        # Extract model
        model = agent.model
        logger.debug(f"Found model: {model.name if model else ''} with provider: {model.provider if model else ''}")

        # Extract architecture
        architecture = agent.architecture
        logger.debug(
            f"Found architecture: {architecture if architecture else ''}",
        )

        # Extract reasoning
        reasoning = self._extract_reasoning(agent)
        logger.debug(
            f"Found reasoning: {reasoning}",
        )

        # Extract knowledge
        knowledge = self._extract_knowledge(agent.knowledge or [])
        logger.debug(
            f"Found number of knowledge items: {len(knowledge)}",
        )

        # Extract document intelligence
        document_intelligence = agent.document_intelligence
        logger.debug(
            f"Found document intelligence: {document_intelligence}",
        )

        # Extract agent settings
        agent_settings = agent.agent_settings or {}
        logger.debug(
            f"Found number of agent settings: {len(agent_settings)}",
        )

        # Extract metadata
        metadata = agent.metadata.model_dump() if agent.metadata else {}

        # Extract selected tools
        selected_tools = self._extract_selected_tools(agent)
        logger.debug(
            f"Number of selected tools: {len(selected_tools.tools)}",
        )

        # Extract welcome message
        welcome_message = agent.welcome_message or ""
        logger.debug(
            f"Found welcome message: {bool(welcome_message)}",
        )

        # Extract conversation starter
        conversation_starter = agent.conversation_starter or ""
        logger.debug(
            f"Found conversation starter: {bool(conversation_starter)}",
        )

        # Extract datasources (async)
        datasources = await self._extract_datasources(action_package_handlers)
        logger.debug(
            f"Number of datasources: {len(datasources)}",
        )

        # Read conversation guide (async)
        question_groups = await self._handler.read_conversation_guide()
        logger.debug(
            f"Number of question groups: {len(question_groups)}",
        )

        # Process action packages (async)
        action_packages = await self._process_action_packages(action_package_handlers, agent.action_packages)
        logger.debug(
            f"Number of action packages: {len(action_packages)}",
        )

        # Process MCP servers
        mcp_servers = self._process_mcp_servers(agent.mcp_servers or [])
        logger.debug(
            f"Number of MCP servers: {len(mcp_servers)}",
        )

        # Process Docker MCP Gateway
        docker_mcp_gateway = AgentPackageDockerMcpGateway.from_spec(agent.docker_mcp_gateway)
        logger.debug(
            f"Found Docker MCP Gateway: {bool(docker_mcp_gateway)}",
        )

        # Load agent package icon
        icon = await self._handler.load_agent_package_icon()
        logger.debug(
            f"Agent icon loaded: {bool(icon)}",
        )

        # Load changelog
        changelog = await self._handler.load_changelog()
        logger.debug(
            f"Changelog loaded: {bool(changelog)}",
        )

        # Load readme
        readme = await self._handler.load_readme()
        logger.debug(
            f"Readme loaded: {bool(readme)}",
        )

        return AgentPackageMetadata(
            release_note="",
            version=agent.version,
            icon=icon,
            name=agent.name,
            description=agent.description,
            model=model,
            architecture=architecture,
            reasoning=reasoning,
            knowledge=knowledge,
            datasources=datasources,
            question_groups=question_groups,
            conversation_starter=conversation_starter,
            welcome_message=welcome_message,
            action_packages=action_packages,
            mcp_servers=mcp_servers,
            docker_mcp_gateway=docker_mcp_gateway,
            agent_settings=agent.agent_settings or {},
            document_intelligence=agent.document_intelligence,
            selected_tools=selected_tools,
            changelog=changelog,
            readme=readme,
            agent_platform_version=self._get_agent_platform_version(),
            created_at=self._get_created_at(),
            metadata=metadata,
        )

    def _extract_reasoning(self, agent: SpecAgent) -> SpecAgentReasoning:
        """Extract and validate reasoning from agent spec."""
        if agent.reasoning in get_args(SpecAgentReasoning):
            return cast(SpecAgentReasoning, agent.reasoning)
        # We keep the default value "disabled" for backwards compatibility.
        raise ValueError("Invalid reasoning in Agent Package specification")

    def _extract_knowledge(
        self,
        knowledge_spec: list[SpecKnowledge],
    ) -> list[AgentPackageMetadataKnowledge]:
        """Extract knowledge files from agent spec."""
        return [AgentPackageMetadataKnowledge.from_spec(k) for k in knowledge_spec]

    def _extract_selected_tools(self, agent: SpecAgent) -> SelectedTools:
        """Extract selected tools from agent spec."""
        if not agent.selected_tools or not agent.selected_tools.tools:
            return SelectedTools(tools=[])
        return SelectedTools(tools=[SelectedToolConfig(name=t.name) for t in agent.selected_tools.tools])

    async def _extract_datasources(
        self,
        action_package_handlers: list[ActionPackageHandlerByPath],
    ) -> list[AgentPackageDatasource]:
        """Extract datasources from all action package metadata.

        Args:
            raw_metadatas: Dictionary of action package path to raw metadata.

        Returns:
            List of AgentPackageDatasource instances.
        """
        from agent_platform.core.agent_package.metadata.action_packages import ActionPackageMetadataReader

        datasources: list[AgentPackageDatasource] = []
        for action_package_path, action_package_handler in action_package_handlers:
            raw_metadata = await action_package_handler.read_metadata_dict()
            datasources.extend(
                await ActionPackageMetadataReader(action_package_handler).extract_datasources(
                    action_package_path, raw_metadata
                )
            )
        return datasources

    async def _process_action_packages(
        self,
        action_package_handlers: list[ActionPackageHandlerByPath],
        action_packages_spec: list[SpecActionPackage],
    ) -> list[AgentPackageActionPackageMetadata]:
        """Process action packages for an agent."""
        from agent_platform.core.agent_package.metadata.action_packages import ActionPackageMetadataReader

        action_packages: list[AgentPackageActionPackageMetadata] = []
        for action_package_path, action_package_handler in action_package_handlers:
            action_package_reader = ActionPackageMetadataReader(action_package_handler)
            action_package_spec = next(
                (ap_spec for ap_spec in action_packages_spec if ap_spec.path == action_package_path),
                None,
            )
            if not action_package_spec:
                logger.warning(
                    "Action package spec not found",
                    action_package_path=action_package_path,
                )
                continue
            ap_metadata = await action_package_reader.get_agent_package_action_packages_metadata(
                await action_package_handler.read_metadata_dict(),
                action_package_spec,
            )
            action_packages.append(ap_metadata)
        return action_packages

    def _process_mcp_servers(
        self,
        mcp_servers_spec: list[SpecMCPServer],
    ) -> list[AgentPackageMcpServer]:
        """Process MCP servers for an agent."""
        mcp_servers: list[AgentPackageMcpServer] = []
        for mcp_spec in mcp_servers_spec:
            try:
                mcp_metadata = AgentPackageMcpServer.from_spec(mcp_spec)
                mcp_servers.append(mcp_metadata)
            except ValueError as e:
                logger.warning("Failed to process MCP server", error=str(e))
        return mcp_servers

    def _get_agent_platform_version(self) -> str:
        """Get the agent platform server version for metadata tagging."""
        return version("agent_platform_server")

    def _get_created_at(self) -> int:
        """Get the current Unix timestamp in seconds."""
        return int(time.time())
