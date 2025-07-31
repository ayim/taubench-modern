import asyncio
import zipfile
from http import HTTPStatus
from pathlib import Path
from urllib.parse import urljoin

import httpx
import structlog
from agent_platform.orchestrator.default_locations import get_agent_server_executable_path

from agent_platform.quality.models import AgentPackage, Platform
from agent_platform.quality.utils import safe_join_url

logger = structlog.get_logger(__name__)

TEST_API_KEY = "test"


class QualityOrchestrator:
    """Orchestrates starting agent-server and action servers for quality testing."""

    def __init__(
        self,
        data_dir: Path,
        agent_server_version: str | None,
        server_url: str = "http://localhost:8000",
        logs_dir: Path | None = None,
    ):
        self.server_url = server_url
        self.action_server_url = None
        self.data_dir = data_dir
        self.logs_dir = logs_dir or self.data_dir / "logs"
        self.agent_server_version = agent_server_version

        # Ensure logs directory exists
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        self._agent_server_process = None
        self._action_server_process = None
        self._started = False

        # Action server pool for parallel execution
        self._action_server_pool = {}  # agent_name -> ActionServerProcess
        self._action_server_urls = {}  # agent_name -> url

    async def start_infrastructure(
        self,
    ) -> str:
        """Start agent-server and required action servers for the given agent package.

        Returns the agent server URL.
        """
        if self._started:
            logger.info("Infrastructure already started")
            return self.server_url

        logger.info("Starting quality test infrastructure")

        # Clear the data directory if it exists (rmdir)
        if self.data_dir.exists():
            logger.info(f"Clearing data directory: {self.data_dir}")
            # shutil.rmtree(self.data_dir)

        # Ensure data directory exists and logs directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        # Start agent server
        await self._start_agent_server()

        # Wait for servers to be ready
        await self._wait_for_servers_ready()

        self._started = True
        logger.info(f"Infrastructure started, agent server at {self.server_url}")
        return self.server_url

    async def start_fresh_action_server(self, agent_zip_path: Path) -> str | None:
        """Start a fresh action server and import the required action packages."""

        # Check and stop any existing action server
        if self._action_server_process and self._action_server_process.started:
            logger.info("Stopping existing action server")
            self._action_server_process.stop()
            self._action_server_process = None
            logger.info("Existing action server stopped")

        # Extract action packages from the agent package
        action_packages = await self._extract_action_packages_from_agent(agent_zip_path)

        # Start action server and import action packages if any exist
        if action_packages:
            self.action_server_url = await self._start_action_server_with_packages(
                agent_zip_path, action_packages
            )
        else:
            logger.info("No action packages found in agent spec")
            self.action_server_url = None

        if self._action_server_process and self._action_server_process.started:
            logger.info(f"Fresh action server started on {self.action_server_url}")
            return self.action_server_url
        else:
            logger.error("Failed to start action server")
            return None

    async def upload_agent_with_platform_variants(
        self,
        agent_zip_path: Path,
        platforms: list[Platform],
        action_server_url: str | None = None,
        agent_package_metadata: dict | None = None,
    ) -> dict[str, str]:
        """Upload agent package multiple times, once per platform.

        Args:
            agent_zip_path: Path to the agent package zip file
            platforms: List of platforms to create variants for

        Returns:
            Dict mapping platform_name -> agent_id
        """

        logger.info(
            f"Uploading agent variants for {len(platforms)} platforms: "
            f"{[p.name for p in platforms]}"
        )

        base_name = agent_zip_path.stem
        agent_ids = {}

        # Upload one variant per platform
        for platform in platforms:
            platform_agent_name = f"{base_name}-{platform.name}"
            agent_id = await self._upload_agent_with_platform(
                agent_zip_path,
                platform_agent_name,
                platform,
                action_server_url,
                agent_package_metadata,
            )
            agent_ids[platform.name] = agent_id
            logger.info(f"Uploaded {platform_agent_name} with ID: {agent_id}")

        logger.info(f"Successfully uploaded {len(agent_ids)} agent variants")
        return agent_ids

    async def _upload_agent_with_platform(
        self,
        agent_zip_path: Path,
        agent_name: str,
        platform: Platform,
        action_server_url: str | None = None,
        agent_package_metadata: dict | None = None,
    ) -> str:
        """Upload single agent with specific platform configuration."""
        import base64

        # Read the zip file as base64
        with open(agent_zip_path, "rb") as f:
            package_base64 = base64.b64encode(f.read()).decode()

        # Prepare MCP servers configuration if we have one
        mcp_servers = []
        if action_server_url:
            # use actions always as MCP servers
            mcp_servers.append(
                {
                    "name": "Test",
                    "transport": "streamable-http",
                    "url": safe_join_url(action_server_url, "/mcp"),
                    "headers": {"Authorization": f"Bearer {TEST_API_KEY}"},
                }
            )

        if agent_package_metadata is not None and "docker_mcp_gateway" in agent_package_metadata:
            # don't allow custom catalog for now: just fail hard!
            if "catalog" in agent_package_metadata["docker-mcp-gateway"]:
                raise ValueError("Only default catalog is allowed when using docker_mcp_gateway")

            servers = agent_package_metadata["docker_mcp_gateway"].get("servers", {})
            server_names = list(servers.keys())
            if len(server_names) > 0:
                mcp_servers.append(
                    {
                        "name": "docker-mcp-gateway",
                        "transport": "auto",
                        "command": "docker",
                        "args": ["mcp", "gateway", "run", "--servers", ",".join(server_names)],
                    }
                )

        # Delete this agent if it already exists (get ID by name, and if it exists, delete it)
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.server_url}/api/v2/agents/by-name",
                params={"name": agent_name},
            )
            if response.status_code == HTTPStatus.OK:
                agent_id = response.json()["agent_id"]
                try:
                    await client.delete(f"{self.server_url}/api/v2/agents/{agent_id}")
                except Exception as e:
                    logger.error(f"Error deleting agent {agent_name}: {e}")

        # Upload agent with platform-specific configuration
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.server_url}/api/v2/agents/package",
                json={
                    "name": agent_name,
                    "description": "Quality test agent",
                    "agent_package_base64": package_base64,
                    "mcp_servers": mcp_servers,
                    "model": {"provider": "openai", "name": "gpt-4o"},
                },
                timeout=30.0,
            )
            response.raise_for_status()
            agent_data = response.json()
            agent_id = agent_data["agent_id"]

        return agent_id

    async def stop_infrastructure(self):
        """Stop all started servers."""
        if not self._started:
            return

        logger.info("Stopping quality test infrastructure")

        # Stop action server pool if it exists
        if self._action_server_pool:
            await self.stop_action_server_pool()

        # Stop action server
        if self._action_server_process:
            self._action_server_process.stop()
            self._action_server_process = None

        # Stop agent server
        if self._agent_server_process:
            self._agent_server_process.stop()
            self._agent_server_process = None

        self._started = False
        logger.info("Infrastructure stopped")

    async def _extract_action_packages_from_agent(self, agent_zip_path: Path) -> list[dict]:
        """Extract action package information from the agent spec."""
        logger.info("Extracting action packages from agent spec")

        try:
            from agent_platform.core.agent_spec.extract_spec import (
                extract_and_validate_agent_package,
            )

            # Extract and validate the agent package
            agent_package = await extract_and_validate_agent_package(path=agent_zip_path)
            spec = agent_package.spec

            # Get action packages from the spec
            action_packages = []
            agent_pkg = spec.get("agent-package", {})
            agents = agent_pkg.get("agents", [])

            # Action packages are defined per agent, so we need to look in each agent
            # For now, we'll take action packages from the first agent (the spec validation
            # ensures there's only one agent anyway)
            if agents and "action-packages" in agents[0]:
                action_packages = agents[0]["action-packages"]
                logger.info(f"Found {len(action_packages)} action packages in spec")
            else:
                logger.info("No action packages found in agent spec")

            return action_packages

        except Exception as e:
            logger.error(f"Failed to extract action packages from agent spec: {e}")
            return []

    async def _start_action_server_with_packages(
        self, agent_zip_path: Path, action_packages: list[dict]
    ) -> str:
        """Start action server and import the required action packages."""
        logger.info(f"Starting action server and importing {len(action_packages)} action packages")

        from agent_platform.orchestrator.bootstrap_action_server import ActionServerProcess
        from agent_platform.orchestrator.default_locations import get_action_server_executable_path

        # Unzip the agent package to a temporary directory
        tmp_agent_zip_dir = self.data_dir / "agent_zip"
        tmp_agent_zip_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(agent_zip_path, "r") as zip_ref:
            zip_ref.extractall(tmp_agent_zip_dir)

        # actions are in ./actions related to the zip
        actions_dir = tmp_agent_zip_dir / "actions"

        # Get action server executable
        action_server_executable = get_action_server_executable_path("2.10.0", download=True)

        # Create action server data directory
        action_server_data_dir = self.data_dir / "action_server"
        action_server_data_dir.mkdir(parents=True, exist_ok=True)

        # Initialize action server process
        self._action_server_process = ActionServerProcess(
            datadir=action_server_data_dir,
            executable_path=action_server_executable,
        )

        # Any nested zips in the actions dir need to be extracted
        # and imported into the action server
        for file in actions_dir.glob("**/*.zip"):
            # Extract the zip first
            with zipfile.ZipFile(file, "r") as zip_ref:
                zip_ref.extractall(file.parent)
                file.unlink()
            # Import the extracted action package
            self._action_server_process.import_action_package(file.parent, logs_dir=self.logs_dir)

        # Start the action server
        self._action_server_process.start(
            logs_dir=self.logs_dir,
            actions_sync=False,
            min_processes=2,
            max_processes=8,
            reuse_processes=True,
            lint=True,
            timeout=500,  # Can be slow (time to bootstrap env)
            additional_args=["--api-key", TEST_API_KEY],
            port=0,  # Let it choose an available port
        )
        actions_url = (
            f"http://{self._action_server_process.host}:{self._action_server_process.port}"
        )

        logger.info(f"Action server started on {actions_url}")
        return actions_url

    async def _start_agent_server(self):
        """Start the agent server."""
        # First check if the agent server is already running (via health check)
        logger.info(f"Checking if agent server is already running at {self.server_url}")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.server_url}/api/v2/health", timeout=1.0)
                logger.info(f"Health check response: {response.status_code}")
                if response.status_code == HTTPStatus.OK:
                    logger.info("Agent server is already running")
                    return
        except Exception as e:
            # Server not running, continue to start it
            logger.info(f"Health check failed: {e}")
            pass

        from agent_platform.orchestrator.bootstrap_agent_server import AgentServerProcess

        logger.info("Starting agent server")

        agent_server_data_dir = self.data_dir / "agent_server"
        agent_server_data_dir.mkdir(parents=True, exist_ok=True)

        executable_path = None
        if self.agent_server_version is not None:
            executable_path = get_agent_server_executable_path(
                version=self.agent_server_version, download=True
            )

        self._agent_server_process = AgentServerProcess(
            datadir=agent_server_data_dir, executable_path=executable_path
        )

        # Parse port from server_url
        from urllib.parse import urlparse

        parsed = urlparse(self.server_url)
        port = parsed.port or 8000

        self._agent_server_process.start(
            logs_dir=self.logs_dir,
            timeout=60,
            port=port,
        )

        logger.info(f"Agent server started on port {self._agent_server_process.port}")

    async def _wait_for_servers_ready(self):
        """Wait for all servers to be ready."""
        logger.info("Waiting for servers to be ready")

        async with httpx.AsyncClient() as client:
            # Wait for agent server to be ready
            for _attempt in range(30):  # 30 seconds timeout
                try:
                    response = await client.get(f"{self.server_url}/api/v2/health", timeout=1.0)
                    if response.status_code == HTTPStatus.OK:
                        logger.info("Agent server is ready")
                        break
                except (httpx.RequestError, httpx.TimeoutException):
                    pass
                await asyncio.sleep(1)
            else:
                raise RuntimeError("Agent server did not become ready in time")

            # Wait for action server to be ready if we started one
            if self._action_server_process and self._action_server_process.started:
                # Action servers don't have a standard health endpoint, so we just
                # trust that if the process started successfully, it's ready
                logger.info("Action server process started successfully")

        logger.info("All servers are ready")

    async def start_action_server_pool(self, agent_packages: list[AgentPackage]) -> dict[str, str]:
        """Start action servers for multiple agents in parallel.

        Args:
            agent_packages: List of agent packages to start action servers for

        Returns:
            Dict mapping agent_name -> action_server_url
        """
        logger.info(f"Starting action server pool for {len(agent_packages)} agents")

        # Start action servers in parallel
        tasks = []
        for agent_package in agent_packages:
            task = self._start_action_server_for_agent(agent_package)
            tasks.append(task)

        # Wait for all action servers to start
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results and build URL mapping
        action_server_urls = {}
        for i, result in enumerate(results):
            agent_package = agent_packages[i]
            if isinstance(result, Exception):
                logger.error(f"Failed to start action server for {agent_package.name}: {result}")
                # Continue with other agents
            else:
                action_server_urls[agent_package.name] = result
                logger.info(f"Action server for {agent_package.name}: {result}")

        logger.info(f"Started {len(action_server_urls)} action servers successfully")
        return action_server_urls

    async def _start_action_server_for_agent(self, agent_package: AgentPackage) -> str:
        """Start an action server for a specific agent package."""
        from agent_platform.orchestrator.bootstrap_action_server import ActionServerProcess
        from agent_platform.orchestrator.default_locations import get_action_server_executable_path

        logger.info(f"Starting action server for agent: {agent_package.name}")

        # Extract action packages from the agent
        action_packages = await self._extract_action_packages_from_agent(agent_package.zip_path)

        if not action_packages:
            logger.info(f"No action packages found for agent {agent_package.name}")
            # Return empty string to indicate no action server needed
            return ""

        # Unzip the agent package to a temporary directory
        tmp_agent_zip_dir = self.data_dir / "agent_zip" / agent_package.name
        tmp_agent_zip_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(agent_package.zip_path, "r") as zip_ref:
            zip_ref.extractall(tmp_agent_zip_dir)

        # actions are in ./actions related to the zip
        actions_dir = tmp_agent_zip_dir / "actions"

        # Get action server executable
        action_server_executable = get_action_server_executable_path("2.14.0", download=True)

        # Create agent-specific action server data directory
        action_server_data_dir = self.data_dir / "action_servers" / agent_package.name
        action_server_data_dir.mkdir(parents=True, exist_ok=True)

        # Initialize action server process
        action_server_process = ActionServerProcess(
            datadir=action_server_data_dir,
            executable_path=action_server_executable,
        )

        # Extract and import action packages
        for file in actions_dir.glob("**/*.zip"):
            # Extract the zip first
            with zipfile.ZipFile(file, "r") as zip_ref:
                zip_ref.extractall(file.parent)
                file.unlink()
            # Import the extracted action package
            action_server_process.import_action_package(file.parent, logs_dir=self.logs_dir)

        # Create agent-specific log directory
        agent_logs_dir = self.logs_dir / agent_package.name
        agent_logs_dir.mkdir(parents=True, exist_ok=True)

        # Start the action server with automatic port selection
        action_server_process.start(
            logs_dir=agent_logs_dir,
            actions_sync=False,
            min_processes=2,
            max_processes=8,
            reuse_processes=True,
            lint=True,
            timeout=500,  # Can be slow (time to bootstrap env)
            additional_args=["--api-key", TEST_API_KEY],
            port=0,  # Let it choose an available port
            env={"SEMA4AI_FILE_MANAGEMENT_URL": urljoin(self.server_url, "api/v2")},
        )

        actions_url = f"http://{action_server_process.host}:{action_server_process.port}"

        # Store in pool for cleanup
        self._action_server_pool[agent_package.name] = action_server_process
        self._action_server_urls[agent_package.name] = actions_url

        logger.info(f"Action server for {agent_package.name} started on {actions_url}")
        return actions_url

    async def stop_action_server_pool(self):
        """Stop all action servers in the pool."""
        logger.info(f"Stopping {len(self._action_server_pool)} action servers")

        for agent_name, action_server_process in self._action_server_pool.items():
            try:
                action_server_process.stop()
                logger.info(f"Stopped action server for {agent_name}")
            except Exception as e:
                logger.error(f"Failed to stop action server for {agent_name}: {e}")

        # Clear the pools
        self._action_server_pool.clear()
        self._action_server_urls.clear()
        logger.info("Action server pool cleanup complete")
