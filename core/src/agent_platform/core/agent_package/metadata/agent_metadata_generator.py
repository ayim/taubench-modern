"""Agent package metadata generation.

This module provides the main entry points for generating agent package metadata
from agent packages.

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
from agent_platform.core.selected_tools import SelectedTools

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Type alias for collection of ActionPackageHandlers
type ActionPackageHandlerByPath = tuple[str, ActionPackageHandler]


class AgentMetadataGenerator:
    """Generates agent package metadata from an agent package.

    This class provides class methods for metadata generation:
    - generate_from_handler: Reads all data from an AgentPackageHandler
    - generate_from_data: Uses provided data directly (useful during package building)

    Works with in-memory zip files via AgentPackageHandler, avoiding
    disk extraction for efficient server-side processing.
    """

    def __init__(self, handler: AgentPackageHandler) -> None:
        """Initialize the generator with a package handler.

        Args:
            handler: Package handler for reading files from the agent package.

        Note: Consider using the classmethod generate_from_handler() instead.
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

        Note: Consider using the classmethod generate_from_handler() instead.
        """
        return await self.generate_from_handler(self._handler)

    @classmethod
    async def generate_from_handler(cls, handler: AgentPackageHandler) -> AgentPackageMetadata:
        """Generate agent metadata by reading all data from a handler.

        This is the primary entry point when you have a complete agent package.

        Args:
            handler: Package handler for reading files from the agent package.

        Returns:
            AgentPackageMetadata for the agent in the package.

        Raises:
            FileNotFoundError: If agent spec file not found.
            ValueError: If spec is invalid.
        """
        logger.debug("Reading agent spec from package...")

        agent = await handler.get_spec_agent()
        logger.debug(f"Processing agent: {agent.name}")

        # Gather all Action Package handlers
        action_package_handlers = await handler.get_action_packages_handlers()
        logger.debug(f"Found {len(action_package_handlers)} action packages")

        # Read auxiliary files from the handler
        question_groups = await handler.read_conversation_guide()
        icon = await handler.load_agent_package_icon()
        changelog = await handler.load_changelog()
        readme = await handler.load_readme()

        # Generate metadata using the data-based method
        metadata = await cls._generate_from_data(
            agent,
            action_package_handlers,
            question_groups=question_groups,
            icon=icon,
            changelog=changelog,
            readme=readme,
        )

        logger.debug("Metadata generation complete")
        return metadata

    @classmethod
    async def _generate_from_data(
        cls,
        agent: SpecAgent,
        action_package_handlers: list[ActionPackageHandlerByPath],
        *,
        question_groups: list,
        icon: str,
        changelog: str,
        readme: str,
    ) -> AgentPackageMetadata:
        """Generate metadata for the agent from provided data.

        This is the primary entry point when building packages where action package
        data is already available in memory, avoiding the need to flush and reopen
        the zip writer.

        Args:
            agent: The agent from the spec.
            action_package_handlers: List of tuples containing the action package path and handler.
            question_groups: Conversation guide question groups.
            icon: Base64-encoded icon.
            changelog: Changelog content.
            readme: Readme content.

        Returns:
            AgentPackageMetadata for the agent in the package.
        """
        logger.debug(f"Generating metadata for agent: {agent.name}")

        # Extract model
        model = agent.model
        logger.debug(f"Found model: {model.name if model else ''} with provider: {model.provider if model else ''}")

        # Extract architecture
        architecture = agent.architecture
        logger.debug(f"Found architecture: {architecture if architecture else ''}")

        # Extract reasoning
        reasoning = cls._extract_reasoning(agent)
        logger.debug(f"Found reasoning: {reasoning}")

        # Extract knowledge
        knowledge = cls._extract_knowledge(agent.knowledge or [])
        logger.debug(f"Found number of knowledge items: {len(knowledge)}")

        # Extract document intelligence
        document_intelligence = agent.document_intelligence
        logger.debug(f"Found document intelligence: {document_intelligence}")

        # Extract agent settings
        agent_settings = agent.agent_settings or {}
        logger.debug(f"Found number of agent settings: {len(agent_settings)}")

        # Extract metadata
        metadata = agent.metadata.model_dump() if agent.metadata else {}

        # Extract selected tools
        selected_tools = cls._extract_selected_tools(agent)
        logger.debug(f"Number of selected tools: {len(selected_tools.tools)}")

        # Extract welcome message
        welcome_message = agent.welcome_message or ""
        logger.debug(f"Found welcome message: {bool(welcome_message)}")

        # Extract conversation starter
        conversation_starter = agent.conversation_starter or ""
        logger.debug(f"Found conversation starter: {bool(conversation_starter)}")

        # Extract datasources (async)
        datasources = await cls._extract_datasources(action_package_handlers)
        logger.debug(f"Number of datasources: {len(datasources)}")

        logger.debug(f"Number of question groups: {len(question_groups)}")

        # Process action packages (async)
        action_packages = await cls._process_action_packages(action_package_handlers, agent.action_packages)
        logger.debug(f"Number of action packages: {len(action_packages)}")

        # Process MCP servers
        mcp_servers = cls._process_mcp_servers(agent.mcp_servers or [])
        logger.debug(f"Number of MCP servers: {len(mcp_servers)}")

        # Process Docker MCP Gateway
        docker_mcp_gateway = AgentPackageDockerMcpGateway.from_spec(agent.docker_mcp_gateway)
        logger.debug(f"Found Docker MCP Gateway: {bool(docker_mcp_gateway)}")

        logger.debug(f"Agent icon loaded: {bool(icon)}")
        logger.debug(f"Changelog loaded: {bool(changelog)}")
        logger.debug(f"Readme loaded: {bool(readme)}")

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
            agent_platform_version=cls._get_agent_platform_version(),
            created_at=cls._get_created_at(),
            metadata=metadata,
        )

    @staticmethod
    def _extract_reasoning(agent: SpecAgent) -> SpecAgentReasoning:
        """Extract and validate reasoning from agent spec."""
        if agent.reasoning in get_args(SpecAgentReasoning):
            return cast(SpecAgentReasoning, agent.reasoning)
        # We keep the default value "disabled" for backwards compatibility.
        raise ValueError("Invalid reasoning in Agent Package specification")

    @staticmethod
    def _extract_knowledge(
        knowledge_spec: list[SpecKnowledge],
    ) -> list[AgentPackageMetadataKnowledge]:
        """Extract knowledge files from agent spec."""
        return [AgentPackageMetadataKnowledge.from_spec(k) for k in knowledge_spec]

    @staticmethod
    def _extract_selected_tools(agent: SpecAgent) -> SelectedTools:
        """Extract selected tools from agent spec."""
        if not agent.selected_tools:
            return SelectedTools(tools=[])
        return agent.selected_tools.to_selected_tools()

    @staticmethod
    async def _extract_datasources(
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

    @staticmethod
    async def _process_action_packages(
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

    @staticmethod
    def _process_mcp_servers(
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

    @staticmethod
    def _get_agent_platform_version() -> str:
        """Get the agent platform server version for metadata tagging."""
        return version("agent_platform_server")

    @staticmethod
    def _get_created_at() -> int:
        """Get the current Unix timestamp in seconds."""
        return int(time.time())
