from __future__ import annotations

import typing

import httpx
import pytest
from agent_platform.orchestrator.bootstrap_base import is_debugger_active

if typing.TYPE_CHECKING:
    from pytest_regressions.data_regression import DataRegressionFixture

    from agent_platform.core.oauth.oauth_models import AuthenticationMetadataClientCredentials

pytest_plugins = [
    "core.tests.mcp.fixtures",
]

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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_oauth2_client_credentials_integration_validate_mcp_server(
    base_url_agent_server_session: str,
    live_custom_mcp_server_with_auth: str,
    live_custom_oauth2_client_credentials_server: AuthenticationMetadataClientCredentials,
    data_regression: DataRegressionFixture,
):
    """Test OAuth2 client credentials integration with a real MCP server.

    This test should be used as a basis on how to actually validate an MCP server
    that uses OAuth2 client credentials authentication.
    """
    from agent_platform.core.mcp.mcp_server import MCPServer
    from agent_platform.core.oauth.oauth_models import AuthenticationType, OAuthConfig

    base_url_agent_server = base_url_agent_server_session
    client_credentials_endpoint = live_custom_oauth2_client_credentials_server.endpoint
    client_credentials_client_id = live_custom_oauth2_client_credentials_server.client_id.get_secret_value()
    client_credentials_client_secret = live_custom_oauth2_client_credentials_server.client_secret.get_secret_value()
    client_credentials_scope = live_custom_oauth2_client_credentials_server.scope

    mcp_server_url = live_custom_mcp_server_with_auth + "/mcp"

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # Create an MCP server via the API
        mcp_server = MCPServer(name="test-oauth-mcp-server", transport="streamable-http", url=mcp_server_url)
        mcp_server_payload = mcp_server.model_dump()

        def redact_urls(data: dict, url: str) -> dict:
            if isinstance(data, dict):
                return {k: redact_urls(v, url) for k, v in data.items()}
            elif isinstance(data, list):
                return [redact_urls(item, url) for item in data]
            elif isinstance(data, str) and url in data:
                return data.replace(url, "<REDACTED_URL>")
            return data

        async def check_no_oauth_use_case():
            # Check without the OAuth config (should give an issue)
            list_tools_response = await client.post(
                f"{base_url_agent_server}/api/v2/capabilities/mcp/tools",
                json={
                    "mcp_servers": [dict(**mcp_server_payload)],
                },
            )
            assert list_tools_response.status_code == 200, (
                f"Failed to list tools: {list_tools_response.status_code} {list_tools_response.text}"
            )
            list_tools_data = list_tools_response.json()
            # Redact any entry that contains the url (as it can change between runs)
            list_tools_data = redact_urls(list_tools_data, mcp_server_url)
            for result in list_tools_data["results"]:
                assert result.get("issues"), f"Expected issues when listing tools without OAuth config: {result}"
            data_regression.check(list_tools_data, basename="list_tools_data_without_oauth_config")

        await check_no_oauth_use_case()

        # Now, add the OAuth config (should work)
        oauth_config = OAuthConfig(
            authentication_type=AuthenticationType.OAUTH2_CLIENT_CREDENTIALS,
            authentication_metadata=dict(
                client_id=client_credentials_client_id,
                client_secret=client_credentials_client_secret,
                scope=client_credentials_scope,
                endpoint=client_credentials_endpoint,
            ),
        )

        # Step: List tools available from the provided MCP servers
        # (this validates that the MCP server is working and that the OAuth2 configuration is correct)

        list_tools_response = await client.post(
            f"{base_url_agent_server}/api/v2/capabilities/mcp/tools",
            json={
                "mcp_servers": [dict(**mcp_server_payload, oauth_config=oauth_config.model_dump_cleartext())],
            },
        )
        assert list_tools_response.status_code == 200, (
            f"Failed to list tools: {list_tools_response.status_code} {list_tools_response.text}"
        )
        list_tools_data = list_tools_response.json()
        # Redact the '/results/server/url` (as it can change between runs)
        list_tools_data = redact_urls(list_tools_data, mcp_server_url)
        data_regression.check(list_tools_data)

        await check_no_oauth_use_case()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_oauth2_client_credentials_integration_mcp_server_configuration(
    base_url_agent_server_session: str,
    live_custom_mcp_server_with_auth: str,
    live_custom_oauth2_client_credentials_server: AuthenticationMetadataClientCredentials,
    openai_api_key: str,
    data_regression: DataRegressionFixture,
):
    """Test OAuth2 client credentials integration with a real MCP server.

    This test should be used as a basis on how to actually configure an MCP server
    to use OAuth2 client credentials authentication.

    Steps:
    1. Create an MCP server with OAuth config via the API
    2. Create an agent with that MCP server ID attached
    3. Trigger a conversation to call the MCP tool
    4. Verify the tool was called successfully with OAuth authentication
    """
    from agent_platform.orchestrator.agent_server_client import AgentServerClient
    from pydantic.types import SecretStr

    from agent_platform.core.mcp.mcp_types import MCPVariableTypeSecret
    from agent_platform.core.oauth.oauth_models import AuthenticationType
    from agent_platform.core.payloads.mcp_server_payloads import (
        MCPServerCreate,
        MCPServerCreateAuthenticationMetadataClientCredentials,
        MCPServerCreateOAuthConfig,
    )

    client_credentials_endpoint = live_custom_oauth2_client_credentials_server.endpoint
    client_credentials_client_id = live_custom_oauth2_client_credentials_server.client_id.get_secret_value()
    client_credentials_client_secret = live_custom_oauth2_client_credentials_server.client_secret.get_secret_value()
    client_credentials_scope = live_custom_oauth2_client_credentials_server.scope

    mcp_server_url = live_custom_mcp_server_with_auth + "/mcp"

    print(f"AuthenticationType: {AuthenticationType.OAUTH2_CLIENT_CREDENTIALS}")
    print(f"client_id: {client_credentials_client_id}")
    print(f"client_secret: {client_credentials_client_secret}")
    print(f"scope: {client_credentials_scope}")
    print(f"endpoint: {client_credentials_endpoint}")
    print(f"mcp_server_url: {mcp_server_url}")
    # Note: running this test will actually create an MCP server that requires
    # OAuth2 client credentials authentication (i.e.: machine-to-machine authentication).
    # For manual tests it's possible to uncomment the line below and then run the test
    # manually (then when paused one can use the printed information to configure the
    # MCP server to test it manually)

    # input("Press Enter to continue...")

    # Step 1: Create an MCP server with OAuth config via the API
    # The MCP server will be automatically deleted when the context exits
    with AgentServerClient(base_url_agent_server_session) as agent_client:
        oauth_config = MCPServerCreateOAuthConfig(
            authentication_type=AuthenticationType.OAUTH2_CLIENT_CREDENTIALS,
            authentication_metadata=MCPServerCreateAuthenticationMetadataClientCredentials(
                client_id=SecretStr(client_credentials_client_id),
                client_secret=SecretStr(client_credentials_client_secret),
                scope=client_credentials_scope.strip(),
                endpoint=client_credentials_endpoint,
            ),
        )

        mcp_server_create = MCPServerCreate(
            name="test-oauth-mcp-server",
            transport="streamable-http",
            url=mcp_server_url,
            oauth_config=oauth_config,
            headers={
                "x-my-secret-header": MCPVariableTypeSecret(type="secret", value="my-secret-token"),
            },
        )
        mcp_server_id = agent_client.create_mcp_server_and_return_id(mcp_server_create)

        # Now, list the MCP servers (just check that the MCP server was created, we don't
        # retrieve oauth config information right now).

        mcp_servers = agent_client.list_mcp_servers()
        assert len(mcp_servers) == 1, f"Failed to list MCP servers: {mcp_servers}"
        mcp_server = next(iter(mcp_servers.values()))
        assert mcp_server["mcp_server_id"] == mcp_server_id, (
            f"id mismatch: {mcp_server['mcp_server_id']} != {mcp_server_id}"
        )

        # Ok, now check that the MCP server has the oauth config
        # we need to redact items that change between runs:
        # authentication_metadata.endpoint
        # mcp_server_id
        # url
        mcp_server_redacted = mcp_server.copy()
        mcp_server_redacted["authentication_metadata"]["endpoint"] = "REDACTED"
        mcp_server_redacted["mcp_server_id"] = "REDACTED"
        mcp_server_redacted["url"] = "REDACTED"
        data_regression.check(mcp_server_redacted)

        # Now, check the agen /mcp-servers/{mcp_server_id} endpoint (should have
        # the same content as the list endpoint)
        mcp_server = agent_client.get_mcp_server(mcp_server_id)
        mcp_server_redacted = mcp_server.copy()
        mcp_server_redacted["authentication_metadata"]["endpoint"] = "REDACTED"
        mcp_server_redacted["mcp_server_id"] = "REDACTED"
        mcp_server_redacted["url"] = "REDACTED"
        data_regression.check(mcp_server_redacted)

        agent_id = agent_client.create_agent_and_return_agent_id(
            runbook="""
            You are a test agent that must call the tool/action that the user asks for.
            Pay attention to the tool/action name and call it exactly as requested.
            If it fails just return the failure.
            """,
            action_packages=[],
            platform_configs=[
                {
                    "kind": "openai",
                    "openai_api_key": openai_api_key,
                    "models": {"openai": ["gpt-5-low"]},
                },
            ],
            mcp_server_ids=[mcp_server_id],
        )

        # Step 3: Trigger a conversation to call the MCP tool
        thread_id = agent_client.create_thread_and_return_thread_id(agent_id)

        # Send a message asking to call the dummy_tool
        final_message, tool_calls = agent_client.send_message_to_agent_thread(
            agent_id,
            thread_id,
            (
                "Please call the dummy_tool with message='Test OAuth2 client credentials integration'. "
                "Call it as fast as possible without doing or requesting anything else."
            ),
        )

        # Step 4: Verify the tool was called successfully
        assert tool_calls, f"No tool calls returned. Final message: {final_message}"
        tool_call = tool_calls[0]
        assert tool_call is not None, f"No tool calls returned. Final message: {final_message}"

        result = tool_call.result
        assert set(result.keys()) == {
            "result",
        }, f"""Structured content keys are not {{"result"}}: {result}.
            Final message: {final_message}"""
        assert result["result"] is not None, f"Result is None: {result}. Final message: {final_message}"

        # Verify the tool response contains the expected message
        # The dummy_tool returns: "Dummy tool response: {message}"
        assert "Dummy tool response" in str(result["result"]), (
            f"Tool response doesn't contain expected message: {result}. Final message: {final_message}"
        )
