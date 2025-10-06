import pytest
from agent_platform.orchestrator.agent_server_client import AgentServerClient
from httpx import AsyncClient

from agent_platform.core.evals.types import TrialStatus
from server.tests.integration.work_items.helper_functions import _wait_until

TERMINAL_STATUSES = [TrialStatus.CANCELED, TrialStatus.COMPLETED, TrialStatus.ERROR]


@pytest.mark.integration
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
@pytest.mark.asyncio
async def test_evals_e2e(  # noqa: PLR0915
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
    import json

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

        agent_client.send_message_to_agent_thread(
            agent_id,
            thread_id,
            "What is 2+2?",
        )

        threads_url = f"{base_url_agent_server_evals_matrix}/api/v2"

        async with AsyncClient(base_url=threads_url) as threads_client:

            async def _latest_message_from_agent() -> bool:
                response = await threads_client.get(f"/threads/{thread_id}/state")
                assert response.status_code == 200, response.text
                thread = response.json()
                messages = thread.get("messages", [])
                if not messages:
                    return False
                latest_message = messages[-1]
                return latest_message.get("role") == "agent"

            await _wait_until(_latest_message_from_agent, interval=0.5, timeout=60)

        evals_url = f"{base_url_agent_server_evals_matrix}/api/v2/evals"

        async with AsyncClient(base_url=evals_url) as client:
            create_payload = {
                "name": "Test scenario",
                "description": "Test description",
                "thread_id": thread_id,
            }

            print("Creating a new scenario")
            create_resp = await client.post("/scenarios", json=create_payload)
            assert create_resp.status_code == 200
            scenario = create_resp.json()

            assert scenario["name"] == create_payload["name"]
            assert scenario["description"] == create_payload["description"]
            assert scenario["thread_id"] == thread_id
            assert scenario["agent_id"] == agent_id

            scenario_id = scenario["scenario_id"]

            print("List scenarios")
            list_resp = await client.get(f"/scenarios?agent_id={agent_id}")
            assert list_resp.status_code == 200
            scenarios = list_resp.json()
            assert len(scenarios) == 1
            assert scenarios[0]["scenario_id"] == scenario_id

            print("Start a run with 1 trial")
            run_payload = {"num_trials": 1}
            run_resp = await client.post(f"/scenarios/{scenario_id}/runs", json=run_payload)
            assert run_resp.status_code == 200
            run = run_resp.json()

            scenario_run_id = run["scenario_run_id"]

            assert run["scenario_id"] == scenario_id
            assert run["num_trials"] == run_payload["num_trials"]
            assert len(run["trials"]) == 1

            for idx, trial in enumerate(run["trials"]):
                assert trial["scenario_id"] == scenario_id
                assert trial["scenario_run_id"] == scenario_run_id
                assert trial["index_in_run"] == idx
                assert trial["status"] not in TERMINAL_STATUSES

            async def _is_final_status():
                print("Checking run status")
                get_run_resp = await client.get(f"/scenarios/{scenario_id}/runs/{scenario_run_id}")
                assert get_run_resp.status_code == 200, get_run_resp.text
                run = get_run_resp.json()

                trials = run.get("trials", [])
                assert len(trials) == 1

                for _, trial in enumerate(trials):
                    print(json.dumps(trial, indent=4))

                all_terminated = all(trial["status"] in TERMINAL_STATUSES for trial in trials)

                return all_terminated

            five_minutes = 5 * 60
            await _wait_until(_is_final_status, interval=1.0, timeout=five_minutes)

            get_run_resp = await client.get(f"/scenarios/{scenario_id}/runs/{scenario_run_id}")
            assert get_run_resp.status_code == 200, get_run_resp.text
            get_run_resp = get_run_resp.json()

            for idx, trial in enumerate(get_run_resp["trials"]):
                print(json.dumps(trial, indent=4))
                assert trial["scenario_id"] == scenario_id
                assert trial["scenario_run_id"] == scenario_run_id
                assert trial["index_in_run"] == idx
                assert trial["status"] == TrialStatus.COMPLETED
