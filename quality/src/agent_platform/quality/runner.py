from __future__ import annotations

import asyncio
import base64
import json
import os
import shutil
import traceback
from collections import defaultdict
from dataclasses import asdict, dataclass
from http import HTTPStatus
from pathlib import Path
from typing import Any

import httpx
import structlog
import yaml

from agent_platform.quality.agent_runner import AgentRunner
from agent_platform.quality.evaluators import EvaluatorEngine
from agent_platform.quality.models import (
    ActionPackageSecret,
    ActionSecret,
    ActionSecrets,
    AgentPackage,
    OAuthAccessToken,
    Platform,
    SFAuthorizationOverride,
    TestCase,
    TestResultGroup,
    ThreadResult,
)
from agent_platform.quality.oauth import OAuthManager
from agent_platform.quality.orchestrator import QualityOrchestrator
from agent_platform.quality.results_manager import QualityResultsManager
from agent_platform.quality.sdm_setup import SDMSetup

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

PREINSTALLED_AGENT_PREFIX = "@preinstalled-"


@dataclass(frozen=True)
class AgentRunContext:
    platform_agent_ids: dict[str, str]
    package_oauth_secrets: list[ActionPackageSecret]
    action_server_url: str


class QualityTestRunner:
    """Orchestrates quality testing with automatic infrastructure management."""

    def __init__(  # noqa: PLR0913
        self,
        test_threads_dir: Path,
        test_agents_dir: Path,
        datadir: Path,
        agent_server_version: str | None,
        server_url: str = "http://localhost:8000",
        is_in_github_actions: bool = False,
        agent_architecture_name_override: str | None = None,
        test_data_dir: Path | None = None,
    ):
        self.test_threads_dir = test_threads_dir
        self.test_agents_dir = test_agents_dir
        self.server_url = server_url
        self.test_data_dir = (
            Path(test_data_dir)
            if test_data_dir is not None
            else (test_threads_dir.parent / "test-data")
        )

        # Initialize components
        self.orchestrator = QualityOrchestrator(
            server_url=server_url,
            data_dir=datadir,
            agent_server_version=agent_server_version,
            agent_architecture_name_override=agent_architecture_name_override,
        )
        self.agent_runner = AgentRunner(server_url=server_url)
        self.evaluator = EvaluatorEngine(server_url=server_url)
        self.oauth = OAuthManager(data_dir=datadir)
        self.is_in_github_actions = is_in_github_actions
        self.sdm_setup = SDMSetup(server_url=server_url, test_data_root=self.test_data_dir)

        # Serialize access to shared sf-auth.json credentials file.
        self._sf_auth_lock = asyncio.Lock()

        # Discover agents early so we can expose them to the UI
        self.discovered_agents = self.discover_agents()

        # Initialize results manager with the same datadir as orchestrator and discovered agents
        self.results_manager = QualityResultsManager(
            self.orchestrator.data_dir, self.discovered_agents
        )

    def discover_agents(self) -> list[AgentPackage]:
        """Discover available agent packages including preinstalled test agents."""
        logger.info(f"Discovering agents in {self.test_agents_dir}")

        agents: list[AgentPackage] = []

        # 1. Discover zip-based agents
        for zip_path in self.test_agents_dir.glob("*.zip"):
            name = zip_path.stem
            agents.append(
                AgentPackage(
                    name=name,
                    path=self.test_agents_dir / name,  # May not exist
                    zip_path=zip_path,
                    is_preinstalled=False,
                )
            )

        # 2. Discover preinstalled agents based on test-case directories + server metadata
        try:
            preinstalled = self._discover_preinstalled_agents()
            agents.extend(preinstalled)
            logger.info(f"Found {len(preinstalled)} preinstalled agents")
        except Exception as e:
            logger.warning(f"Failed to discover preinstalled agents: {e}")

        logger.info(f"Found {len(agents)} total agent packages")
        return agents

    def _discover_preinstalled_agents(self) -> list[AgentPackage]:  # noqa: C901
        """Discover preinstalled agents based on test directories and server metadata.

        We infer which preinstalled agents are needed from directories under
        test_threads_dir whose name starts with '@preinstalled-'. For each such
        directory, we resolve a corresponding hidden preinstalled agent on the
        server by querying the metadata-based search endpoint.

        This keeps the runner generic and driven by tests, without hard-coding
        specific feature or project tags.
        """
        from http import HTTPStatus

        logical_names: set[str] = set()
        for test_dir in self.test_threads_dir.iterdir():
            if test_dir.is_dir() and test_dir.name.startswith(PREINSTALLED_AGENT_PREFIX):
                logical_names.add(test_dir.name)

        if not logical_names:
            logger.info("No preinstalled agent test directories found")
            return []

        preinstalled_packages: list[AgentPackage] = []
        search_url = f"{self.server_url}/api/v2/agents/search/by-metadata"

        for logical_name in sorted(logical_names):
            feature_key = logical_name.removeprefix(PREINSTALLED_AGENT_PREFIX)
            params = {
                "visibility": "hidden",
                "feature": feature_key,
            }
            try:
                with httpx.Client(timeout=10.0) as client:
                    response = client.get(search_url, params=params)
                if response.status_code != HTTPStatus.OK:
                    logger.warning(
                        f"Metadata search for preinstalled agent '{logical_name}' failed "
                        f"(status {response.status_code})",
                    )
                    continue

                agents_data = response.json() or []
            except Exception as e:
                logger.warning(
                    f"Metadata search for preinstalled agent '{logical_name}' errored: {e}",
                )
                continue

            if not agents_data:
                logger.warning(
                    f"No preinstalled agent found for logical name '{logical_name}' using metadata "
                    f"{params}",
                )
                continue
            if not isinstance(agents_data, list):
                logger.warning(
                    f"Preinstalled agent search result is not a list for '{logical_name}': "
                    f"{agents_data}",
                )
                continue

            agent_data = agents_data[0]

            if not isinstance(agent_data, dict):
                logger.warning(
                    f"Preinstalled agent search result is not a dict for '{logical_name}': "
                    f"{agent_data}",
                )
                continue

            agent_id = agent_data.get("id")
            if not agent_id:
                logger.warning(
                    f"Preinstalled agent search result missing agent_id for '{logical_name}': "
                    f"{agent_data}",
                )
                continue

            preinstalled_packages.append(
                AgentPackage(
                    name=logical_name,
                    path=Path("preinstalled") / logical_name,
                    zip_path=None,
                    is_preinstalled=True,
                    preinstalled_key=logical_name,
                    agent_id=agent_id,
                )
            )

        return preinstalled_packages

    def discover_test_cases(
        self, agent_name: str | None = None, tests_filter: list[str] | None = None
    ) -> list[TestCase]:
        """Discover test cases, optionally filtered by agent name and test names.

        When tests_filter is provided, YAML files whose 'name' does not match are skipped
        without full parsing to avoid loading unrelated auth config (e.g., Snowflake).
        """
        logger.info(f"Discovering test cases in {self.test_threads_dir}")

        test_cases = []

        for test_dir in self.test_threads_dir.iterdir():
            if test_dir.is_dir():
                if agent_name and test_dir.name != agent_name:
                    continue

                for yml_path in test_dir.glob("*.yml"):
                    if tests_filter:
                        try:
                            with open(yml_path, encoding="utf-8") as f:
                                raw = yaml.safe_load(f)
                            test_name = raw.get("name")
                            if test_name not in tests_filter:
                                continue
                        except Exception:
                            # If we can't read minimally, fall back to full parse
                            pass

                    test_case = TestCase.from_file(yml_path)
                    test_cases.append(test_case)

        logger.info(f"Found {len(test_cases)} test cases")
        return test_cases

    async def run_tests_for_all_agents_fully_parallel(  # noqa: C901, PLR0912, PLR0915
        self,
        selected_agents: list[str],
        max_concurrent_agents: int = 2,
        platform_filter: str | None = None,
        tests_filter: list[str] | None = None,
    ) -> dict[str, list[ThreadResult]]:
        """Run tests for all agents with full parallelization (agents + platforms).

        Args:
            max_concurrent_agents: Maximum number of agents to run concurrently
            platform_filter: Optional platform name to limit execution to.
        """
        agents = self.discover_agents()
        if not agents:
            logger.warning("No agent packages found")
            self.results_manager.complete_run("No agent packages found")
            return {}

        if selected_agents:
            agents = [agent for agent in agents if agent.name in selected_agents]
        if not agents:
            logger.warning("No agents found after filtering by selected_agents")
            self.results_manager.complete_run("No agents found after filtering by selected_agents")
            return {}

        # If specific tests are requested, skip agents that have no matching test cases
        if tests_filter:
            filtered_agents: list[AgentPackage] = []
            for agent in agents:
                agent_tests = self.discover_test_cases(agent.name, tests_filter=tests_filter)
                if any(test_case.name in tests_filter for test_case in agent_tests):
                    filtered_agents.append(agent)
                else:
                    logger.info(
                        "Skipping agent %s because no test cases matched the provided tests filter",
                        agent.name,
                    )

            agents = filtered_agents

            if not agents:
                logger.warning("No agents found after applying tests filter")
                self.results_manager.complete_run("No agents found after applying tests filter")
                return {}

        logger.info(
            f"Starting fully parallel execution for {len(agents)} agents "
            f"(max {max_concurrent_agents} concurrent)"
        )

        results = {}
        overall_error = None
        infrastructure_started = False
        action_server_pool_started = False

        try:
            # Start shared infrastructure
            logger.info("Starting shared infrastructure for all agents")
            await self.orchestrator.start_infrastructure()
            infrastructure_started = True

            # Start action server pool for all agents in parallel
            logger.info("Starting action server pool for all agents")
            action_server_urls = await self.orchestrator.start_action_server_pool(agents)
            action_server_pool_started = True

            # Create semaphore to limit concurrent agents
            semaphore = asyncio.Semaphore(max_concurrent_agents)

            async def run_agent_with_semaphore(
                agent: AgentPackage,
            ) -> tuple[str, list[ThreadResult]]:
                """Run a single agent with semaphore protection."""
                async with semaphore:
                    try:
                        logger.info(f"Starting parallel execution for agent: {agent.name}")
                        action_server_url = action_server_urls.get(agent.name, "")

                        agent_results = await self._run_agent_fully_parallel(
                            agent,
                            action_server_url,
                            platform_filter,
                            tests_filter,
                        )
                        logger.info(
                            f"Completed agent: {agent.name} with {len(agent_results)} results"
                        )
                        return agent.name, agent_results

                    except Exception as e:
                        logger.exception(f"Failed to run tests for agent {agent.name}: {e}")
                        return agent.name, []

            # Run all agents in parallel (with semaphore limiting concurrency)
            tasks = [run_agent_with_semaphore(agent) for agent in agents]
            agent_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for result in agent_results:
                if isinstance(result, Exception):
                    logger.error(f"Agent execution failed with exception: {result}")
                    if overall_error is None:
                        overall_error = f"Agent execution failed: {result}"
                elif isinstance(result, tuple) and len(result) == 2:  # noqa: PLR2004
                    agent_name, test_results = result
                    results[agent_name] = test_results
                else:
                    logger.error(f"Unexpected result type: {type(result)}")

            # Mark run as complete
            self.results_manager.complete_run(overall_error)
            return results

        except Exception as e:
            logger.error(f"Failed to run tests for all agents in parallel: {e}")
            self.results_manager.complete_run(str(e))
            raise

        finally:
            # Stop action server pool
            if action_server_pool_started:
                logger.info("Stopping action server pool")
                await self.orchestrator.stop_action_server_pool()

            # Stop shared infrastructure
            if infrastructure_started:
                logger.info("Stopping shared infrastructure")
                await self.orchestrator.stop_infrastructure()

            try:
                await self.sdm_setup.cleanup()
            except Exception as cleanup_error:  # pragma: no cover - best-effort cleanup
                logger.warning("Failed to clean up SDM resources", error=str(cleanup_error))

    async def _run_agent_fully_parallel(
        self,
        agent_package: AgentPackage,
        action_server_url: str,
        platform_filter: str | None,
        tests_filter: list[str] | None,
    ) -> list[ThreadResult]:
        """Run all tests for a single agent with full parallelization."""
        logger.info(f"Running agent tests (fully parallel): {agent_package.name}")

        try:
            # Discover test cases for this agent
            test_cases = self.discover_test_cases(agent_package.name, tests_filter=tests_filter)

            if not test_cases:
                logger.error(
                    f"No test cases found for agent {agent_package.name} after applying filters."
                )
                return []

            agent_package_metadata = await agent_package.extract_package_metadata()
            target_platforms = self._collect_target_platforms(
                test_cases, platform_filter, agent_package.name
            )
            package_oauth_secrets = await self._build_package_oauth_secrets(agent_package_metadata)

            logger.info(
                "Creating agent variants for platforms: %s",
                [p.name for p in target_platforms],
            )

            # Upload agent variants (one per platform)
            platform_agent_ids = await self.orchestrator.upload_agent_with_platform_variants(
                agent_package,
                target_platforms,
                action_server_url,
                agent_package_metadata[0],
            )
            run_context = AgentRunContext(
                platform_agent_ids=platform_agent_ids,
                package_oauth_secrets=package_oauth_secrets,
                action_server_url=action_server_url,
            )

            # Initialize agent testing in results manager
            self.results_manager.start_agent_testing(
                agent_package, test_cases, platform_filter=platform_filter
            )

            # Run each test case with all its platforms in parallel
            # (But we are _sequential_ at the level of a test case!!)
            all_results = []
            for test_case in test_cases:
                platforms_to_run = self._get_platforms_for_test_case(test_case, platform_filter)
                if not platforms_to_run:
                    logger.info(
                        "Skipping test case %s for agent %s because platform '%s' is not targeted.",
                        test_case.name,
                        agent_package.name,
                        platform_filter,
                    )
                    continue

                case_results = await self._run_test_case_with_optional_override(
                    agent_package,
                    test_case,
                    platforms_to_run,
                    run_context,
                )
                all_results.extend(case_results)

            # Mark agent testing as complete
            self.results_manager.complete_agent_testing(agent_package.name)
            return all_results

        except Exception as e:
            logger.error(f"Failed to run tests for agent {agent_package.name}: {e}")
            # Mark agent testing as failed
            self.results_manager.complete_agent_testing(agent_package.name, str(e))
            raise

    def _get_platforms_for_test_case(
        self, test_case: TestCase, platform_filter: str | None
    ) -> list[Platform]:
        """Return the list of platforms to run for a test case given the filter."""
        if platform_filter is None:
            return list(test_case.target_platforms)
        platforms_accepted = set(platform_filter.split(","))
        return [p for p in test_case.target_platforms if p.name in platforms_accepted]

    def _collect_target_platforms(
        self,
        test_cases: list[TestCase],
        platform_filter: str | None,
        agent_name: str,
    ) -> list[Platform]:
        """Aggregate and validate platforms for the provided test cases."""
        all_platforms = set()
        for test_case in test_cases:
            all_platforms.update(self._get_platforms_for_test_case(test_case, platform_filter))

        if platform_filter and not all_platforms:
            raise ValueError(
                f"No test targets found for platform '{platform_filter}' in agent '{agent_name}'."
            )

        if not all_platforms:
            raise ValueError(
                f"No target platforms defined for tests associated with agent '{agent_name}'."
            )

        return list(all_platforms)

    async def _run_test_case_with_optional_override(
        self,
        agent_package: AgentPackage,
        test_case: TestCase,
        platforms_to_run: list[Platform],
        run_context: AgentRunContext,
    ) -> list[ThreadResult]:
        """Run a test case, applying sf-auth overrides when required."""
        if not test_case.sf_auth_override:
            return await self._run_test_case_with_platforms(
                agent_package,
                test_case,
                platforms_to_run,
                run_context,
            )

        async with self._sf_auth_override(test_case.sf_auth_override):
            return await self._run_test_case_with_platforms(
                agent_package,
                test_case,
                platforms_to_run,
                run_context,
            )

    async def _build_package_oauth_secrets(
        self, agent_package_metadata: list[dict[str, Any]]
    ) -> list[ActionPackageSecret]:
        """Construct OAuth secrets defined in the package metadata."""
        package_oauth_secrets: list[ActionPackageSecret] = []

        if isinstance(agent_package_metadata, dict):
            agent_package_metadata = [agent_package_metadata]

        for agent_meta in agent_package_metadata:
            if not isinstance(agent_meta, dict):
                continue
            for pkg in agent_meta.get("action_packages", []):
                package_action_oauth_secrets: list[ActionSecrets] = []
                for _, action in pkg.get("secrets", {}).items():
                    action_name = action.get("action")
                    secrets = action.get("secrets", {})
                    oauth_secrets: list[ActionSecret] = []

                    for secret_name, secret_info in secrets.items():
                        if secret_info.get("type") != "OAuth2Secret":
                            continue

                        provider = secret_info.get("provider")
                        credentials = await self.oauth.get_oauth_credentials(provider=provider)
                        if credentials is None:
                            raise ValueError(f"No oauth credentials for provider {provider}")

                        access_token = OAuthAccessToken(
                            provider=provider,
                            scopes=credentials.get("scope").split(" "),
                            access_token=credentials.get("access_token"),
                        )
                        oauth_secrets.append(ActionSecret(name=secret_name, value=access_token))

                    package_action_oauth_secrets.append(
                        ActionSecrets(name=action_name, secrets=oauth_secrets)
                    )

                package_oauth_secrets.append(
                    ActionPackageSecret(name=pkg.get("name"), actions=package_action_oauth_secrets)
                )

        return package_oauth_secrets

    async def _run_test_case_with_platforms(  # noqa: C901
        self,
        agent_package: AgentPackage,
        test_case: TestCase,
        platforms: list[Platform],
        run_context: AgentRunContext,
    ) -> list[ThreadResult]:
        """Run a single test case across all of its target platforms."""

        all_results: list[ThreadResult] = []
        platform_tasks = []

        # For preinstalled agents with SDMs, create unique agent clones per test case
        # to avoid SDM bleeding between tests (SDMs are agent-scoped, not thread-scoped)
        # TODO: Remove this workaround once server import endpoint is updated to attach
        # SDMs to threads instead of agents
        test_case_agent_ids: dict[str, str] = {}
        created_clones: list[str] = []

        needs_unique_clones = (
            agent_package.is_preinstalled and test_case.sdms and len(test_case.sdms) > 0
        )

        if needs_unique_clones:
            for platform in platforms:
                base_agent_id = run_context.platform_agent_ids[platform.name]
                clone_id = await self.orchestrator.create_test_case_agent_clone(
                    base_agent_id=base_agent_id,
                    platform=platform,
                    test_case_name=test_case.name,
                )
                test_case_agent_ids[platform.name] = clone_id
                created_clones.append(clone_id)
        else:
            test_case_agent_ids = run_context.platform_agent_ids

        try:
            for platform in platforms:
                agent_id = test_case_agent_ids[platform.name]

                await self.update_action_secrets(
                    agent_id,
                    test_case.action_secrets + run_context.package_oauth_secrets,
                    run_context.action_server_url,
                )

                self.results_manager.start_test(agent_package.name, test_case, platform)

                task = self._run_test_case_on_platform(agent_id, test_case, platform)
                platform_tasks.append(task)

            test_results = await asyncio.gather(*platform_tasks, return_exceptions=True)

            for i, result in enumerate(test_results):
                if isinstance(result, Exception):
                    platform = platforms[i]
                    logger.error(
                        f"Test case failed: {test_case.file_path} on platform {platform.name}",
                        error=str(result),
                    )
                    error_result = ThreadResult(
                        test_case=test_case,
                        platform=platform,
                        agent_messages=[],
                        evaluation_results=[],
                        success=False,
                        agent_id=test_case_agent_ids.get(platform.name),
                        error=str(result),
                    )
                    all_results.append(error_result)
                    self.results_manager.complete_test(agent_package.name, error_result, 1)
                elif isinstance(result, TestResultGroup):
                    for index, thread_result in enumerate(result.thread_results):
                        all_results.append(thread_result)
                        self.results_manager.complete_test(agent_package.name, thread_result, index)

        except Exception as e:
            logger.error(f"Failed to execute test case {test_case.name} in parallel: {e}")
            for platform in platforms:
                error_result = ThreadResult(
                    test_case=test_case,
                    platform=platform,
                    agent_messages=[],
                    evaluation_results=[],
                    success=False,
                    agent_id=test_case_agent_ids.get(platform.name),
                    error=str(e),
                )
                all_results.append(error_result)
                self.results_manager.complete_test(agent_package.name, error_result, 1)

        finally:
            # Clean up test-case-specific agent clones
            for clone_id in created_clones:
                await self.orchestrator.delete_agent(clone_id)

        return all_results

    async def get_oauth_connections(
        self,
    ) -> defaultdict[str, defaultdict[str, list[Any]]]:
        scopes_by_provider = defaultdict(lambda: defaultdict(list))

        for agent in self.discovered_agents:
            data = await agent.extract_package_metadata()

            for agent_meta in data:
                for pkg in agent_meta.get("action_packages", []):
                    for path, endpoint in pkg.get("secrets", {}).items():
                        secrets = endpoint.get("secrets", {})
                        for _, secret_info in secrets.items():
                            if secret_info.get("type") == "OAuth2Secret":
                                provider = secret_info.get("provider")
                                for scope in secret_info.get("scopes", []):
                                    scopes_by_provider[provider][scope].append(
                                        {
                                            "action": endpoint.get("action"),
                                            "path": path,
                                            "package": endpoint.get("actionPackage"),
                                        }
                                    )

        return scopes_by_provider

    async def update_action_secrets(  # noqa: C901 PLR0912 PLR0915
        self,
        agent_id: str,
        action_secrets: list[ActionPackageSecret],
        action_server_base_url: str | None = None,
    ) -> None:
        """Update the action secrets for an agent."""
        logger.info(f"Updating action secrets for agent {agent_id}")

        if not action_secrets:
            logger.debug("No action secrets defined in the test case to update.")
            return

        for package_secret_config in action_secrets:
            package_name = package_secret_config.name
            logger.info(f"Processing secrets for package: {package_name} on agent {agent_id}")

            action_server_base_url = (
                action_server_base_url
                if action_server_base_url
                else self.orchestrator.action_server_url
            )

            if not action_server_base_url:
                logger.warning(
                    f"No action server base URL found for agent {agent_id}. "
                    "Skipping secrets update."
                )
                continue

            secrets_endpoint = f"{action_server_base_url.rstrip('/')}/api/secrets"

            secrets_to_set_for_package = {}
            try:
                for action_config in package_secret_config.actions:
                    for secret_item in action_config.secrets:
                        value = secret_item.value
                        if isinstance(value, str) and value.startswith("$"):
                            env_var_name = value[1:]
                            env_value = os.getenv(env_var_name)
                            if env_value is None:
                                logger.error(
                                    f"Environment variable '{env_var_name}' for secret "
                                    f"'{secret_item.name}' in package '{package_name}' "
                                    "is not set."
                                )
                                raise ValueError(
                                    f"Environment variable '{env_var_name}' not set, "
                                    f"required for secret '{secret_item.name}' "
                                    f"in package '{package_name}'."
                                )
                            value = env_value
                        secrets_to_set_for_package[secret_item.name] = (
                            value if isinstance(value, str) else asdict(value)
                        )
            except ValueError as e:  # Catches the missing env var error
                logger.error(
                    f"Failed to prepare secrets for package '{package_name}' on "
                    f"agent {agent_id}: {e}"
                )
                continue  # to the next package_secret_config

            if not secrets_to_set_for_package:
                logger.info(
                    f"No secrets to set for package '{package_name}' on "
                    f"agent {agent_id} after processing."
                )
                continue

            payload_data_dict = {
                "secrets": secrets_to_set_for_package,
                "scope": {"action-package": package_name},
            }

            payload_data_json_str = json.dumps(payload_data_dict)
            ctx_info = base64.b64encode(payload_data_json_str.encode("utf-8")).decode("utf-8")

            request_body = {"data": ctx_info}

            try:
                logger.debug(
                    f"Setting secrets for Action Package: {package_name} at {secrets_endpoint}",
                )
                post_response = None
                async with httpx.AsyncClient() as client:
                    post_response = await client.post(
                        secrets_endpoint,
                        json=request_body,
                        headers={"Content-Type": "application/json"},
                    )

                response_text = post_response.text
                if not post_response or post_response.status_code != HTTPStatus.OK:
                    logger.warning(
                        f"POST to {secrets_endpoint} for package '{package_name}' failed: "
                        f"{post_response.status_code} - {response_text}"
                    )
                    continue

                try:
                    # The expected response is the JSON string "ok"
                    if json.loads(response_text) != "ok":
                        logger.warning(
                            f"POST to {secrets_endpoint} for package '{package_name}' "
                            f"returned an unexpected body: {response_text}"
                        )
                        continue
                except json.JSONDecodeError:
                    logger.warning(
                        f"POST to {secrets_endpoint} for package '{package_name}' "
                        f"returned non-JSON body: {response_text}"
                    )
                    continue

                logger.info(
                    f"Successfully set secrets for Action Package: '{package_name}' "
                    f"at {secrets_endpoint}"
                )

            except httpx.RequestError as e:
                logger.error(
                    f"Request error during POST to {secrets_endpoint} for package "
                    f"'{package_name}': {e}",
                    exc_info=True,
                )
                continue
            except Exception as e:
                logger.error(
                    f"Unexpected error during POST to {secrets_endpoint} for package "
                    f"'{package_name}': {e}",
                    exc_info=True,
                )
                continue

    async def _run_test_case_on_platform(
        self,
        agent_id: str,
        test_case: TestCase,
        platform: Platform,
    ) -> TestResultGroup:
        """Run a single test case on a specific platform with all setup."""

        # TODO we could average over the evaluations
        tasks = [
            self._run_single_test(agent_id, test_case, platform) for _ in range(test_case.trials)
        ]
        results = await asyncio.gather(*tasks)

        return TestResultGroup(thread_results=results)

    async def _run_single_test(
        self, agent_id: str, test_case: TestCase, platform: Platform
    ) -> ThreadResult:
        """Run a single test case on a specific platform."""
        logger.info(f"Running test on platform: {platform.name}")

        try:
            if test_case.sdms and test_case.thread is None:
                raise ValueError("SDM setup is only supported for thread-based test cases.")

            on_thread_created = None
            if test_case.sdms and test_case.thread is not None:

                async def _on_thread_created(thread_id: str) -> None:
                    await self.sdm_setup.ensure_sdms_for_thread(
                        thread_id=thread_id,
                        sdm_configs=test_case.sdms,
                        agent_id=agent_id,
                    )

                on_thread_created = _on_thread_created

            # Run the conversation
            test_run = await self.agent_runner.run_test_case(
                agent_id,
                test_case,
                platform.name,
                on_thread_created=on_thread_created,
            )

            # Fetch thread files before evaluations so evaluators can access file attachments
            thread_files = (
                await self.agent_runner.get_thread_files(thread_id=test_run.thread_id)
                if test_run.thread_id is not None
                else []
            )

            # Run evaluations
            evaluation_results = []
            for evaluation in test_case.evaluations:
                try:
                    result = await self.evaluator.evaluate(
                        evaluation,
                        test_run.agent_messages,
                        test_run.workitem_result,
                        thread_files,
                    )
                    evaluation_results.append(result)
                except Exception as e:
                    logger.error(f"Evaluation failed: {evaluation.kind}", error=str(e))
                    # Continue with other evaluations

            # Determine overall success
            success = all(result.passed for result in evaluation_results)

            return ThreadResult(
                test_case=test_case,
                platform=platform,
                agent_messages=test_run.agent_messages,
                evaluation_results=evaluation_results,
                success=success,
                agent_id=agent_id,
                thread_id=test_run.thread_id,
                thread_files=thread_files,
            )

        except Exception as e:
            logger.error(
                "Test execution failed",
                extra={
                    "test_case": test_case.name,
                    "platform": platform.name,
                    "agent_id": agent_id,
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                },
            )

            return ThreadResult(
                test_case=test_case,
                platform=platform,
                agent_messages=[],
                evaluation_results=[],
                success=False,
                agent_id=agent_id,
                error=str(e),
            )

    class _SFAuthOverrideGuard:
        def __init__(
            self,
            runner: QualityTestRunner,
            sf_auth_override: SFAuthorizationOverride | None,
        ) -> None:
            self._runner = runner
            self._sf_auth_override = sf_auth_override
            self._lock_acquired = False
            self._applied = False

        async def __aenter__(self) -> bool:
            if self._runner.is_in_github_actions or self._sf_auth_override is None:
                return False

            await self._runner._sf_auth_lock.acquire()
            self._lock_acquired = True

            self._applied = self._runner._update_sf_auth_json_locked(self._sf_auth_override)

            if not self._applied:
                # Release immediately so other agents are not blocked.
                self._runner._sf_auth_lock.release()
                self._lock_acquired = False

            return self._applied

        async def __aexit__(self, exc_type, exc, tb) -> None:
            try:
                if self._applied:
                    self._runner._restore_sf_auth_json_locked()
            finally:
                if self._lock_acquired and self._runner._sf_auth_lock.locked():
                    self._runner._sf_auth_lock.release()

    def _sf_auth_override(
        self, sf_auth_override: SFAuthorizationOverride | None
    ) -> QualityTestRunner._SFAuthOverrideGuard:
        return QualityTestRunner._SFAuthOverrideGuard(self, sf_auth_override)

    def _update_sf_auth_json_locked(self, sf_auth_override: SFAuthorizationOverride) -> bool:
        """Update sf-auth.json with the given override. Lock must be held."""
        if self.is_in_github_actions:
            return False

        try:
            # Create a backup of the current sf-auth.json if not already present.
            backup_path = Path.home() / ".sema4ai" / "sf-auth-backup.json"
            if not backup_path.exists():
                shutil.copy(Path.home() / ".sema4ai" / "sf-auth.json", backup_path)
        except Exception as e:
            logger.error(f"Failed to create sf-auth.json backup: {e!s}")
            logger.warning("Will not override sf-auth.json")
            return False

        try:
            with open(Path.home() / ".sema4ai" / "sf-auth.json", "w") as f:
                json.dump(
                    {
                        "linkingDetails": {
                            "account": sf_auth_override.account,
                            "privateKeyPath": sf_auth_override.private_key_path,
                            "privateKeyPassphrase": sf_auth_override.private_key_passphrase,
                            "user": sf_auth_override.user,
                            "role": sf_auth_override.role,
                            "authenticator": "SNOWFLAKE_JWT",
                            "applicationUrl": "",
                        }
                    },
                    f,
                )
        except Exception as e:
            logger.error(f"Failed to override sf-auth.json: {e!s}")
            return False

        return True

    def _restore_sf_auth_json_locked(self) -> None:
        """Restore sf-auth.json to the original state. Lock must be held."""
        if self.is_in_github_actions:
            return

        try:
            backup_path = Path.home() / ".sema4ai" / "sf-auth-backup.json"
            if backup_path.exists():
                backup_path.rename(Path.home() / ".sema4ai" / "sf-auth.json")
        except Exception as e:
            logger.error(f"Failed to restore sf-auth.json: {e!s}")
