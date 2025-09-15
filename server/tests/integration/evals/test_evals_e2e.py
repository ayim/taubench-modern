import pytest
from agent_platform.orchestrator.agent_server_client import AgentServerClient
from httpx import AsyncClient

from agent_platform.core.evals.types import TrialStatus
from server.tests.integration.work_items.helper_functions import _wait_until


@pytest.mark.integration
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
@pytest.mark.asyncio
async def test_evals_e2e(
    base_url_agent_server_evals_matrix: str,
    openai_api_key: str,
):
    """
    Comprehensive e2e test covering the complete lifecycle:
    - Create a scenario
    - List scenarios for an agent
    - Run a scenario
    - Check latest run status
    """
    with AgentServerClient(base_url_agent_server_evals_matrix) as agent_client:
        agent_id = agent_client.create_agent_and_return_agent_id(
            platform_configs=[
                {
                    "kind": "openai",
                    "openai_api_key": openai_api_key,
                    "models": {"openai": ["gpt-5-low"]},
                }
            ],
            runbook="""
            You are a helpful assistant. Always respond with exactly what the user asks for.
            """,
        )

        thread_id = agent_client.create_thread_and_return_thread_id(agent_id=agent_id)

        agent_client.send_message_to_agent_thread(agent_id, thread_id, "What is 2+2?")

        evals_url = f"{base_url_agent_server_evals_matrix}/api/v2/evals"

        async with AsyncClient(base_url=evals_url) as client:
            create_payload = {
                "name": "Test scenario",
                "description": "Test description",
                "thread_id": thread_id,
            }

            create_resp = await client.post("/scenarios", json=create_payload)
            assert create_resp.status_code == 200
            scenario = create_resp.json()

            assert scenario["name"] == create_payload["name"]
            assert scenario["description"] == create_payload["description"]
            assert scenario["thread_id"] == thread_id
            assert scenario["agent_id"] == agent_id

            scenario_id = scenario["scenario_id"]

            list_resp = await client.get(f"/scenarios?agent_id={agent_id}")
            assert list_resp.status_code == 200
            scenarios = list_resp.json()
            assert len(scenarios) == 1
            assert scenarios[0]["scenario_id"] == scenario_id

            run_payload = {"num_trials": 3}
            run_resp = await client.post(f"/scenarios/{scenario_id}/runs", json=run_payload)
            assert run_resp.status_code == 200
            run = run_resp.json()

            scenario_run_id = run["scenario_run_id"]

            assert run["scenario_id"] == scenario_id
            assert run["num_trials"] == run_payload["num_trials"]
            assert len(run["trials"]) == 3

            for idx, trial in enumerate(run["trials"]):
                assert trial["scenario_id"] == scenario_id
                assert trial["scenario_run_id"] == scenario_run_id
                assert trial["index_in_run"] == idx
                assert trial["status"] in [
                    TrialStatus.PENDING,
                    TrialStatus.EXECUTING,
                ]

            async def _is_final_status():
                get_run_resp = await client.get(f"/scenarios/{scenario_id}/runs/latest")
                assert get_run_resp.status_code == 200
                run = get_run_resp.json()

                all_completed = all(
                    trial["status"] == TrialStatus.COMPLETED for trial in run["trials"]
                )
                return all_completed

            await _wait_until(_is_final_status, interval=1.0, timeout=120)

            get_run_resp = await client.get(f"/scenarios/{scenario_id}/runs/latest")
            assert get_run_resp.status_code == 200
            get_run_resp = get_run_resp.json()

            for idx, trial in enumerate(get_run_resp["trials"]):
                assert trial["scenario_id"] == scenario_id
                assert trial["scenario_run_id"] == scenario_run_id
                assert trial["index_in_run"] == idx
                assert trial["status"] == TrialStatus.COMPLETED
