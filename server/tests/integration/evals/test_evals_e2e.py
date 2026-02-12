import pytest
from agent_platform.orchestrator.agent_server_client import AgentServerClient
from httpx import AsyncClient

from agent_platform.core.evals.types import TrialStatus
from server.tests.auth_helpers import TEST_AUTH_HEADERS
from server.tests.integration.work_items.helper_functions import _wait_until

TERMINAL_STATUSES = [TrialStatus.CANCELED, TrialStatus.COMPLETED, TrialStatus.ERROR]


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
    import json

    timeout = 60 * 7  # 7 minutes

    with AgentServerClient(base_url_agent_server_evals_matrix) as agent_client:
        agent_id = agent_client.create_agent_and_return_agent_id(
            platform_configs=[
                {
                    "kind": "openai",
                    "openai_api_key": openai_api_key,
                    "models": {"openai": ["gpt-5-minimal"]},
                }
            ],
            runbook="""
            You are a helpful assistant. Always respond with exactly what the user asks for.
            """,
        )

        evals_url = f"{base_url_agent_server_evals_matrix}/api/v2/evals"

        async with AsyncClient(base_url=evals_url, headers=TEST_AUTH_HEADERS) as client:
            create_payload = {
                "name": "Test scenario",
                "description": "Test description",
                "agent_id": agent_id,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "kind": "text",
                                "text": "What is 2+2?",
                            }
                        ],
                        "complete": True,
                    },
                    {
                        "role": "agent",
                        "content": [
                            {
                                "kind": "text",
                                "text": "4",
                            }
                        ],
                        "complete": True,
                    },
                ],
                # in this way we run only one LM judge that always returns a success
                # we are not interested in measuring the quality of evals
                # but to test the flow end to end
                "evaluation_criteria": [
                    {
                        "type": "response_accuracy",
                        "expectation": "everything is fine",
                    }
                ],
            }

            print("Creating a new scenario")
            create_resp = await client.post("/scenarios", json=create_payload)
            assert create_resp.status_code == 200
            scenario = create_resp.json()

            assert scenario["name"] == create_payload["name"]
            assert scenario["description"] == create_payload["description"]
            assert scenario["agent_id"] == agent_id
            assert scenario["thread_id"] is None

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

            await _wait_until(_is_final_status, interval=1.0, timeout=timeout)

            get_run_resp = await client.get(f"/scenarios/{scenario_id}/runs/{scenario_run_id}")
            assert get_run_resp.status_code == 200, get_run_resp.text
            get_run_resp = get_run_resp.json()

            for idx, trial in enumerate(get_run_resp["trials"]):
                print(json.dumps(trial, indent=4))
                assert trial["scenario_id"] == scenario_id
                assert trial["scenario_run_id"] == scenario_run_id
                assert trial["index_in_run"] == idx
                assert trial["status"] == TrialStatus.COMPLETED
