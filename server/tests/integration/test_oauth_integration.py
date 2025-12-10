import httpx
import pytest
from agent_platform.orchestrator.bootstrap_base import is_debugger_active

TIMEOUT = 300

if is_debugger_active():
    TIMEOUT = 99999999  # No timeouts when debugging.


@pytest.mark.integration
@pytest.mark.asyncio
async def manual_test_oauth2_login_integration(base_url_agent_server_session):
    """Test OAuth2 login endpoint with a real MCP server."""
    import webbrowser
    from urllib.parse import urlencode

    from agent_platform.orchestrator.agent_server_client import AgentServerClient

    from sema4ai.common.wait_for import wait_for_non_error_condition

    base_url_agent_server = base_url_agent_server_session
    print(f"base_url_agent_server: {base_url_agent_server}")

    # MCP server URL (assumed to be running at localhost:8080)
    mcp_server_url = "http://localhost:8080/mcp"

    with AgentServerClient(base_url_agent_server_session) as agent_client:
        async with (
            httpx.AsyncClient(timeout=TIMEOUT) as client,
        ):
            # Create an MCP server via the API
            mcp_server_payload = {
                "name": "test-oauth-mcp-server",
                "transport": "streamable-http",
                "url": mcp_server_url,
            }

            # Create MCP server
            create_response = await client.post(
                f"{base_url_agent_server}/api/v2/mcp-servers/",
                json=mcp_server_payload,
            )
            assert create_response.status_code == 200, (
                f"Failed to create MCP server: {create_response.status_code} {create_response.text}"
            )

            mcp_server_data = create_response.json()
            mcp_server_url = mcp_server_data["url"]
            mcp_server_id = mcp_server_data["mcp_server_id"]
            print(f"mcp_server_id: {mcp_server_id}")
            print(f"mcp_server_url: {mcp_server_url}")

            _agent_id = agent_client.create_agent_and_return_agent_id(
                runbook="""
                You are a test agent that must call the tool/action that the user asks for.
                Pay attention to the tool/action name and call it exactly as requested.
                If it fails just return the failure.
                """,
                action_packages=[],
                platform_configs=[
                    {
                        "kind": "openai",
                        "openai_api_key": "unused",
                        "models": {"openai": ["gpt-5-low"]},
                    },
                ],
                mcp_server_ids=[mcp_server_id],
            )

            try:
                # Open the login page in the browser
                params = urlencode({"mcp_server_url": mcp_server_url})
                webbrowser.open(f"{base_url_agent_server}/api/v2/oauth2/login?{params}")

                # Wait for the OAuth2 flow to complete (i.e.: the /status must say the user
                # is authenticated)
                def raise_if_not_authenticated():
                    client = httpx.Client(timeout=TIMEOUT)
                    status_response = client.get(
                        f"{base_url_agent_server}/api/v2/oauth2/status?{params}",
                    )
                    try:
                        assert status_response.status_code == 200, status_response.text
                        for _mcp_server_id, status_data in status_response.json().items():
                            assert status_data["authenticated"] is True
                            assert status_data["token_expires_in"] is not None
                            assert status_data["token_expires_in"] > 0
                    except Exception as e:
                        raise RuntimeError(f"status_response: {status_response.text} - {e}") from e

                wait_for_non_error_condition(raise_if_not_authenticated, timeout=TIMEOUT, sleep=2)

            finally:
                # Clean up: delete the MCP server
                delete_response = await client.delete(
                    f"{base_url_agent_server}/api/v2/mcp-servers/{mcp_server_id}",
                )
                # Don't fail the test if cleanup fails
                if delete_response.status_code not in (200, 204, 404):
                    print(f"Warning: Failed to delete MCP server: {delete_response.status_code}")
