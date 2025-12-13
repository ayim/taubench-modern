import asyncio
import logging
import time
import zipfile
from collections import Counter
from contextlib import ExitStack, contextmanager
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import httpx
import pytest

from agent_platform.core.work_items.work_item import WorkItemStatus
from agent_platform.server.work_items.rest import WorkItemsListResponse
from server.tests.integration.integration_fixtures import start_agent_server

TERMINAL_STATUSES = {
    WorkItemStatus.COMPLETED,
    WorkItemStatus.ERROR,
    WorkItemStatus.NEEDS_REVIEW,
}

TEST_API_KEY = "test"


@contextmanager
def start_action_server_with_package(
    action_package_zip: Path,
    tmpdir: Path,
    logs_dir: Path,
    node_id: str,
    action_server_executable_path: Path,
):
    """Context manager to start an action server with a specific action package."""
    from agent_platform.orchestrator.bootstrap_action_server import ActionServerProcess

    logger = logging.getLogger("start_action_server")
    logger.debug(f"Starting action server for {node_id}")

    # Create action server data directory
    action_server_data_dir = tmpdir / "action_server_data"
    action_server_data_dir.mkdir(parents=True, exist_ok=True)

    # Initialize action server process
    action_server_process = ActionServerProcess(
        datadir=action_server_data_dir,
        executable_path=action_server_executable_path,
    )

    # Extract and import the action package
    extract_dir = tmpdir / "extracted_actions"
    extract_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(action_package_zip, "r") as zip_ref:
        zip_ref.extractall(extract_dir)

    # Import the extracted action package
    action_server_process.import_action_package(extract_dir, logs_dir=logs_dir)

    # Start the action server
    action_server_process.start(
        logs_dir=logs_dir,
        actions_sync=False,
        min_processes=2,
        max_processes=8,
        reuse_processes=True,
        lint=True,
        timeout=500,  # Can be slow (time to bootstrap env)
        additional_args=["--api-key", TEST_API_KEY],
        port=0,  # Let it choose an available port
    )

    actions_url = f"http://{action_server_process.host}:{action_server_process.port}"
    logger.debug(f"Action server for {node_id} started on {actions_url}")

    try:
        yield actions_url
    finally:
        logger.debug(f"Stopping action server for {node_id}")
        action_server_process.stop()
        logger.debug(f"Action server for {node_id} stopped")


async def _wait_for_terminal_status(
    client: httpx.AsyncClient,
    query_base_url: str,
    work_item_id: str,
    timeout: float = 180.0,
    poll_interval: float = 1.0,
) -> WorkItemStatus:
    """Poll the REST API until the work item reaches a terminal status."""
    deadline = time.monotonic() + timeout
    last_status = WorkItemStatus.PENDING

    while time.monotonic() < deadline:
        response = await client.get(f"{query_base_url}/api/v2/work-items/{work_item_id}?results=true")
        response.raise_for_status()
        payload = response.json()
        last_status = WorkItemStatus(payload["status"])
        messages = payload.get("messages", [])
        if len(messages) > 1 and last_status in TERMINAL_STATUSES:
            return last_status

        await asyncio.sleep(poll_interval)

    raise AssertionError(f"Work item {work_item_id} did not reach a terminal status. Last status: {last_status}")


async def _fetch_work_item_details(
    client: httpx.AsyncClient,
    work_item_ids: list[str],
    query_targets: list[str],
    status_by_id: dict[str, WorkItemStatus],
    not_completed_ids: list[str],
) -> str:
    """Fetch and format details about work items that didn't complete."""
    details = ""
    for wii in not_completed_ids:
        work_item_index = work_item_ids.index(wii)
        query_base_url = query_targets[work_item_index]
        response = await client.get(f"{query_base_url}/api/v2/work-items/{wii}?results=true")
        response.raise_for_status()
        work_item_data = response.json()
        thread_id = work_item_data.get("thread_id")

        # Fetch messages from the thread endpoint
        messages = []
        if thread_id:
            thread_response = await client.get(f"{query_base_url}/api/v2/threads/{thread_id}")
            thread_response.raise_for_status()
            thread_data = thread_response.json()
            messages = thread_data.get("messages", [])

        details += f"\nFinal Work Item {wii} (status: {status_by_id[wii].value}):\n"
        details += f"  Thread ID: {thread_id}\n"
        details += f"  Messages: {messages}\n"
    return details


def choose_url() -> str:
    import random

    return random.choice(
        [
            "https://sema4.ai",
            "https://openai.com",
            "https://www.google.com",
            "https://www.apple.com",
            "https://www.microsoft.com",
            "https://www.amazon.com",
            "https://about.meta.com",
            "https://www.netflix.com",
            "https://www.nvidia.com",
            "https://www.ibm.com",
            "https://stripe.com",
            "https://www.datadoghq.com",
            "https://www.snowflake.com",
            "https://slack.com",
            "https://github.com",
            "https://about.gitlab.com",
            "https://www.cloudflare.com",
            "https://zoom.us",
            "https://shopify.com",
            # "https://www.salesforce.com",
            "https://twilio.com",
            "https://www.atlassian.com",
            # "https://www.oracle.com",
            # "https://www.sap.com",
            # "https://www.reddit.com",
            # "notaurl",
            # "http://bad",
            # "https://",
            # "http://example..com",
            # "http://invalid_domain",
            # "ftp://wrong.com",
        ]
    )


@pytest.mark.integration
@pytest.mark.parallel_work_items
@pytest.mark.postgresql
@pytest.mark.asyncio
async def test_work_items_complete_across_multiple_servers(
    tmp_path_factory: pytest.TempPathFactory,
    base_logs_directory,
    action_server_executable_path: Path,
    openai_api_key: str,
    request: pytest.FixtureRequest,
    server_count: int = 2,
    total_work_items: int = 40,
) -> None:
    """Ensure work items reach terminal states while multiple agent-server instances run."""
    import testing.postgresql

    # Skip this test unless explicitly requested with -m parallel_work_items
    if "parallel_work_items" not in request.config.option.markexpr:
        pytest.skip("Skipping parallel_work_items test. Run with '-m parallel_work_items' to execute.")

    if openai_api_key is None:
        pytest.fail("OPENAI_API_KEY is not set")

    # Get path to the browsing action package
    test_dir = Path(__file__).parent
    action_package_zip = test_dir / "1.3.3.zip"
    if not action_package_zip.exists():
        pytest.fail(f"Action package not found at {action_package_zip}")

    with testing.postgresql.Postgresql() as postgres:
        parsed = urlparse(postgres.url())
        db_name = parsed.path.lstrip("/")

        base_env: dict[str, str] = {
            "SEMA4AI_AGENT_SERVER_DB_TYPE": "postgres",
            "LOG_LEVEL": "INFO",
            "POSTGRES_HOST": parsed.hostname or "localhost",
            "POSTGRES_PORT": str(parsed.port or 5432),
            "POSTGRES_DB": db_name or "postgres",
            "POSTGRES_USER": parsed.username or "postgres",
            "POSTGRES_PASSWORD": parsed.password or "",
            "S4_AGENT_SERVER_FILE_MANAGER_TYPE": "local",
            "OPENAI_API_KEY": openai_api_key,
            "WORKITEMS_WORK_ITEM_TIMEOUT": "360",
            "WORKITEMS_EXECUTION_MODE": "slots",
            "WORKITEMS_TRANSACTION_LOG": "true",
        }

        base_urls: list[str] = []
        action_server_urls: list[str] = []

        with ExitStack() as stack:
            # Launch N instances of the agent server with corresponding action servers
            for index in range(server_count):
                tmpdir = tmp_path_factory.mktemp(f"agent-server-{index}")
                logs_dir = base_logs_directory / "work-items-cluster" / f"server-{index}"
                logs_dir.mkdir(parents=True, exist_ok=True)

                env = base_env.copy()
                env["S4_AGENT_SERVER_NODE_ID"] = f"cluster-node-{index}"

                # Start agent server
                server_url = stack.enter_context(start_agent_server(str(tmpdir), logs_dir, env=env))
                base_urls.append(server_url)

                # Start corresponding action server
                action_tmpdir = tmp_path_factory.mktemp(f"action-server-{index}")
                action_logs_dir = logs_dir / "action-server"
                action_logs_dir.mkdir(parents=True, exist_ok=True)

                action_server_url = stack.enter_context(
                    start_action_server_with_package(
                        action_package_zip,
                        action_tmpdir,
                        action_logs_dir,
                        f"cluster-node-{index}",
                        action_server_executable_path,
                    )
                )
                action_server_urls.append(action_server_url)

            assert base_urls, "Expected at least one running agent server instance"
            assert action_server_urls, "Expected at least one running action server instance"

            # Create an agent on the first server with MCP configuration
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Prepare MCP server configuration pointing to the first action server
                mcp_servers = [
                    {
                        "name": "Sema4.ai",
                        "transport": "streamable-http",
                        "url": f"{action_server_urls[0]}/mcp",
                        "headers": {"Authorization": f"Bearer {TEST_API_KEY}"},
                    }
                ]

                # Create the agent
                create_response = await client.post(
                    f"{base_urls[0]}/api/v2/agents/",
                    json={
                        "name": f"Cluster Test Agent {uuid4()}",
                        "version": "1.0.0",
                        "description": "Agent for cluster integration testing.",
                        "agent_architecture": {
                            "name": "agent_platform.architectures.default",
                            "version": "1.0.0",
                        },
                        "runbook": """
You are a worker that receives work as work items. Follow this process for each item you get:
1. Use the browsing actions from Sema4.ai to get content of any of the URLs you find in the payload
2. If you receive a valid page content, summarize what the company whose page it was does in
   one sentence.
3. If the tool succeeded to fetch the website, mark the work item as completed. Else, mark the work
   item as needs review.
""",
                        "platform_configs": [
                            {
                                "kind": "openai",
                                "name": "gpt-5-minimal",
                                "openai_api_key": openai_api_key,
                                "models": {"openai": ["gpt-5-minimal"]},
                            }
                        ],
                        "mcp_servers": mcp_servers,
                    },
                )
                create_response.raise_for_status()
                agent_data = create_response.json()
                agent_id = agent_data["agent_id"]

                # Create work items on all servers
                work_item_ids: list[str] = []
                query_targets: list[str] = []

                # Create the work items round-robin.
                for item_index in range(total_work_items):
                    creation_base_url = base_urls[item_index % server_count]
                    query_base_url = base_urls[(item_index + 1) % server_count]

                    create_response = await client.post(
                        f"{creation_base_url}/api/v2/work-items/",
                        json={
                            "agent_id": agent_id,
                            "messages": [
                                {
                                    "role": "user",
                                    "content": [
                                        {
                                            "kind": "text",
                                            "text": "fetch the website provided",
                                        }
                                    ],
                                }
                            ],
                            "payload": {"url": choose_url()},
                        },
                        headers={"Content-Type": "application/json"},
                    )
                    create_response.raise_for_status()
                    created = create_response.json()
                    work_item_ids.append(created["work_item_id"])
                    query_targets.append(query_base_url)

                assert len(work_item_ids) == total_work_items

                # Wait for all work items to reach a terminal status.
                terminal_statuses = await asyncio.gather(
                    *[
                        _wait_for_terminal_status(client, query_targets[i], work_item_id)
                        for i, work_item_id in enumerate(work_item_ids)
                    ]
                )

                # Check that all work items reached a terminal status.
                status_by_id = {
                    work_item_id: status for work_item_id, status in zip(work_item_ids, terminal_statuses, strict=False)
                }
                assert all(status in TERMINAL_STATUSES for status in status_by_id.values())

                not_completed_ids = [
                    work_item_id
                    for work_item_id, status in status_by_id.items()
                    if status not in (WorkItemStatus.COMPLETED, WorkItemStatus.NEEDS_REVIEW)
                ]

                # Print some stats
                state_counts = Counter(status_by_id.values())
                print(
                    "Work items not completed:",
                    sorted(not_completed_ids),
                )
                print(
                    "Work item counts by state:",
                    {status.value: count for status, count in state_counts.items()},
                )

                details = await _fetch_work_item_details(
                    client, work_item_ids, query_targets, status_by_id, not_completed_ids
                )

                assert not not_completed_ids, (
                    f"Expected all work items to complete, but some had other terminal statuses.{details}"
                )

                # Ensure list endpoint can retrieve the created work items from a random server.
                list_response = await client.get(
                    f"{base_urls[-1]}/api/v2/work-items/",
                    params={"limit": total_work_items, "agent_id": agent_id},
                )
                list_response.raise_for_status()
                listed_items = WorkItemsListResponse.model_validate(list_response.json())
                listed_ids = {item.work_item_id for item in listed_items.records}
                assert set(work_item_ids).issubset(listed_ids)
