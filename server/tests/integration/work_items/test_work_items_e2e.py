import dataclasses
import json
from io import BytesIO

import pytest
from agent_platform.orchestrator.agent_server_client import AgentServerClient
from httpx import AsyncClient

from agent_platform.core.payloads.update_work_item import UpdateWorkItemPayload
from agent_platform.core.thread.thread import Thread
from agent_platform.core.work_items.work_item import WorkItemStatus
from agent_platform.server.work_items.callbacks import _compute_signature
from agent_platform.server.work_items.rest import WorkItemsListResponse
from server.tests.integration.work_items.helper_functions import (
    _wait_until,
    assert_work_item_url,
    make_text_message,
)


async def _verify_payload_in_thread_messages(
    base_url: str, agent_id: str, thread_id: str, expected_payload_data: dict, work_item_id: str
) -> None:
    """Verify that the expected payload data appears in the thread messages."""
    async with AsyncClient(base_url=f"{base_url}/api/v2") as messages_client:
        resp = await messages_client.get(f"/threads/{thread_id}/state")
        assert resp.status_code == 200
        thread = Thread.model_validate(resp.json())

        # Verify that the thread has the correct work_item_id
        assert thread.work_item_id == work_item_id, (
            f"Expected thread work_item_id to be {work_item_id}, but got {thread.work_item_id}"
        )

        # Filter to only ThreadTextContext, and get the actual text
        text_contents = [
            content.as_text_content()
            for message in thread.messages
            for content in message.content
            if content.kind == "text"
        ]

        # Look for a text content with the payload
        expected_text = json.dumps(expected_payload_data)
        found = any(expected_text in text_content for text_content in text_contents)

        assert found, (
            f"Expected to find payload {expected_payload_data} in thread messages, "
            f"but it was not found. Messages: {thread.messages}"
        )


@pytest.mark.integration
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
@pytest.mark.asyncio
async def test_work_items_with_file_e2e(
    base_url_agent_server_workitems_matrix: str,
    openai_api_key: str,
    callback_server,
):
    """
    Comprehensive e2e test covering the complete work item lifecycle:
    - File upload (single direct upload) with upload message verification
    - Multiple callbacks with signature verification (only one should fire)
    - All endpoint testing (list, describe, cancel)
    - Judge validation (handles both COMPLETED and NEEDS_REVIEW as valid outcomes)
    - Complete status transitions and verification
    """

    # Create agent for this test run
    with AgentServerClient(base_url_agent_server_workitems_matrix) as agent_client:
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

        work_items_url = f"{base_url_agent_server_workitems_matrix}/api/public/v1/work-items"

        async with AsyncClient(base_url=work_items_url) as client:
            # 1. Upload file
            file_content = b"Important document content for agent analysis"
            filename = "document.txt"
            file_tuple = (filename, BytesIO(file_content), "text/plain")

            upload_resp = await client.post("/upload-file", files={"file": file_tuple})
            assert upload_resp.status_code == 200
            work_item_id = upload_resp.json()["work_item_id"]

            # Verify work item is in DRAFT state
            get_resp = await client.get(f"/{work_item_id}")
            assert get_resp.status_code == 200
            work_item = get_resp.json()
            assert work_item["status"] == WorkItemStatus.DRAFT.value
            assert work_item["agent_id"] is None

            # 2. Setup multiple callback servers with signature verification
            signature_secret_completed = "test_secret_completed_123"
            signature_secret_needs_review = "test_secret_needs_review_456"

            completed_callback_srv = callback_server(["COMPLETED"])
            needs_review_callback_srv = callback_server(["NEEDS_REVIEW"])

            # 3. Convert work item to PENDING by adding agent and messages with multiple callbacks
            create_payload = {
                "agent_id": agent_id,
                "messages": make_text_message("What is 2+2?"),
                "payload": {"task": "simple_math", "test_type": "e2e_comprehensive"},
                "work_item_name": "  E2E Test Work Item  ",
                "callbacks": [
                    {
                        "url": completed_callback_srv.url,
                        "on_status": "COMPLETED",
                        "signature_secret": signature_secret_completed,
                    },
                    {
                        "url": needs_review_callback_srv.url,
                        "on_status": "NEEDS_REVIEW",
                        "signature_secret": signature_secret_needs_review,
                    },
                ],
                "work_item_id": work_item_id,
            }

            create_resp = await client.post("/", json=create_payload)
            assert create_resp.status_code == 200
            work_item = create_resp.json()

            # Verify work item is now PENDING with agent
            assert work_item["status"] in [
                WorkItemStatus.PENDING.value,
                WorkItemStatus.EXECUTING.value,
            ]
            assert work_item["agent_id"] == agent_id
            assert work_item["work_item_id"] == work_item_id
            assert work_item["work_item_name"] == "E2E Test Work Item"

            # 4. Wait for main work item to reach final status
            # Note: The judge can return either COMPLETED or NEEDS_REVIEW
            async def _is_final_status():
                r = await client.get(f"/{work_item_id}")
                assert r.status_code == 200
                status = WorkItemStatus(r.json()["status"])
                return status in [WorkItemStatus.COMPLETED, WorkItemStatus.NEEDS_REVIEW]

            # Increased timeout for CI environments (especially with cloud file management)
            await _wait_until(_is_final_status, interval=1.0, timeout=240)

            # 5. Get final work item state
            final_resp = await client.get(f"/{work_item_id}?results=true")
            assert final_resp.status_code == 200
            final_work_item = final_resp.json()

            final_status = WorkItemStatus(final_work_item["status"])
            assert final_status in [WorkItemStatus.COMPLETED, WorkItemStatus.NEEDS_REVIEW], (
                f"Expected COMPLETED or NEEDS_REVIEW status, got {final_status}. "
                f"The judge can return either status for simple questions."
            )
            assert final_work_item["thread_id"] is not None

            # Verify thread name uses the custom work item name
            thread_id = final_work_item["thread_id"]
            async with AsyncClient(base_url=f"{base_url_agent_server_workitems_matrix}/api/v2") as thread_client:
                thread_resp = await thread_client.get(f"/threads/{thread_id}/state")
                assert thread_resp.status_code == 200
                thread_data = thread_resp.json()
                assert thread_data["name"] == "E2E Test Work Item"

            # 6. Verify appropriate callback was triggered based on final status
            if final_status == WorkItemStatus.COMPLETED:
                # COMPLETED callback should have fired
                callback_received = completed_callback_srv.wait_for("COMPLETED")
                assert callback_received, "COMPLETED callback was not received within timeout"
                assert len(completed_callback_srv.requests) == 1, (
                    f"Expected exactly 1 COMPLETED callback, got {len(completed_callback_srv.requests)}"
                )
                assert len(needs_review_callback_srv.requests) == 0, (
                    "Expected 0 NEEDS_REVIEW callbacks, "
                    f"got {len(needs_review_callback_srv.requests)}. "
                    "Only the COMPLETED callback should have fired."
                )

                # Verify callback details
                request = completed_callback_srv.single_request()
                body = request["body"]
                expected_signature = _compute_signature(signature_secret_completed, body)

            elif final_status == WorkItemStatus.NEEDS_REVIEW:
                # NEEDS_REVIEW callback should have fired
                callback_received = needs_review_callback_srv.wait_for("NEEDS_REVIEW")
                assert callback_received, "NEEDS_REVIEW callback was not received within timeout"
                assert len(needs_review_callback_srv.requests) == 1, (
                    f"Expected exactly 1 NEEDS_REVIEW callback, got {len(needs_review_callback_srv.requests)}"
                )
                assert len(completed_callback_srv.requests) == 0, (
                    f"Expected 0 COMPLETED callbacks, got {len(completed_callback_srv.requests)}. "
                    f"Only the NEEDS_REVIEW callback should have fired."
                )

                # Verify callback details
                request = needs_review_callback_srv.single_request()
                body = request["body"]
                expected_signature = _compute_signature(signature_secret_needs_review, body)

            # Common callback verification
            assert request["path"] == "/webhook"
            assert request["headers"]["Content-Type"] == "application/json"
            assert body["work_item_id"] == work_item_id
            assert body["agent_id"] == agent_id
            assert body["status"] == final_status.value
            assert body["thread_id"] is not None

            # Verify signature
            assert "X-SEMA4AI-SIGNATURE" in request["headers"]
            actual_signature = request["headers"]["X-SEMA4AI-SIGNATURE"]
            assert actual_signature == expected_signature

            # Verify work item URL
            assert_work_item_url(body, agent_id, body["work_item_id"], body["thread_id"])

            # 7. Final endpoint verification - ensure we can still query the completed work item
            final_list_resp = await client.get("/")
            assert final_list_resp.status_code == 200
            final_listed_items = WorkItemsListResponse.model_validate(final_list_resp.json())
            final_work_item_ids = [wi.work_item_id for wi in final_listed_items.records]
            assert work_item_id in final_work_item_ids

            # 8. Verify final describe still works
            final_desc_resp = await client.get(f"/{work_item_id}")
            assert final_desc_resp.status_code == 200
            assert final_desc_resp.json()["work_item_id"] == work_item_id
            assert final_desc_resp.json()["status"] == final_status.value

            # 9. Verify payload made it into thread messages after completion
            thread_id = final_work_item["thread_id"]
            assert thread_id is not None, "Thread ID should not be None after completion"

        # Verify that the payload made it into the thread messages
        expected_payload_data = {"task": "simple_math", "test_type": "e2e_comprehensive"}
        await _verify_payload_in_thread_messages(
            base_url_agent_server_workitems_matrix,
            agent_id,
            thread_id,
            expected_payload_data,
            work_item_id,
        )

        # Make sure the private v2 work-items endpoint is working:
        async with AsyncClient(base_url=f"{base_url_agent_server_workitems_matrix}/api/v2") as client:
            v2_list_resp = await client.get("/work-items/")
            assert v2_list_resp.status_code == 200
            v2_listed_items = v2_list_resp.json()["records"]
            v2_work_item_ids = [wi["work_item_id"] for wi in v2_listed_items]
            assert work_item_id in v2_work_item_ids

        # Verify that the thread retrieved from the API has the correct work_item_id
        async with AsyncClient(base_url=f"{base_url_agent_server_workitems_matrix}/api/v2") as client:
            thread_resp = await client.get(f"/threads/{thread_id}/state")
            assert thread_resp.status_code == 200
            thread_data = thread_resp.json()
            assert thread_data["work_item_id"] == work_item_id, (
                f"Expected thread {work_item_id=}, but got {thread_data.get('work_item_id')}"
            )


@pytest.mark.integration
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
@pytest.mark.asyncio
async def test_work_items_e2e(
    base_url_agent_server_workitems_matrix: str,
    openai_api_key: str,
    callback_server,
):
    # Create agent for this test run
    with AgentServerClient(base_url_agent_server_workitems_matrix) as agent_client:
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

        work_items_url = f"{base_url_agent_server_workitems_matrix}/api/public/v1/work-items"

        async with AsyncClient(base_url=work_items_url) as client:
            # Create a work item
            create_payload = {
                "agent_id": agent_id,
                "messages": make_text_message("What is 2+2?"),
                "payload": {"task": "simple_math", "test_type": "e2e_comprehensive"},
            }

            create_resp = await client.post("/", json=create_payload)
            assert create_resp.status_code == 200
            work_item = create_resp.json()
            assert work_item["work_item_name"] == f"Work Item {work_item['work_item_id']}", (
                "expected work item to be set to reasonable default value"
            )

            # Verify work item is now PENDING with agent
            assert work_item["status"] in [
                WorkItemStatus.PENDING.value,
                WorkItemStatus.EXECUTING.value,
            ]
            assert work_item["agent_id"] == agent_id
            assert work_item["work_item_id"] is not None
            work_item_id = work_item["work_item_id"]

            # Wait for main work item to reach final status
            # Note: The judge can return either COMPLETED or NEEDS_REVIEW
            async def _is_final_status():
                r = await client.get(f"/{work_item_id}")
                assert r.status_code == 200
                status = WorkItemStatus(r.json()["status"])
                return status in [WorkItemStatus.COMPLETED, WorkItemStatus.NEEDS_REVIEW]

            # Increased timeout for CI environments (especially with cloud file management)
            await _wait_until(_is_final_status, interval=1.0, timeout=240)

            # Get final work item state
            final_resp = await client.get(f"/{work_item_id}?results=true")
            assert final_resp.status_code == 200
            final_work_item = final_resp.json()

            final_status = WorkItemStatus(final_work_item["status"])
            assert final_status in [WorkItemStatus.COMPLETED, WorkItemStatus.NEEDS_REVIEW], (
                f"Expected COMPLETED or NEEDS_REVIEW status, got {final_status}. "
                f"The judge can return either status for simple questions."
            )
            assert final_work_item["thread_id"] is not None

            # Final endpoint verification - ensure we can still query the completed work item
            final_list_resp = await client.get("/")
            assert final_list_resp.status_code == 200
            final_listed_items = WorkItemsListResponse.model_validate(final_list_resp.json())
            final_work_item_ids = [wi.work_item_id for wi in final_listed_items.records]
            assert work_item_id in final_work_item_ids

            # Verify final describe still works
            final_desc_resp = await client.get(f"/{work_item_id}")
            assert final_desc_resp.status_code == 200
            final_desc_data = final_desc_resp.json()
            assert final_desc_data["work_item_id"] == work_item_id
            assert final_desc_data["status"] == final_status.value

            # Verify payload made it into thread messages after completion
            thread_id = final_work_item["thread_id"]
            assert thread_id is not None, "Thread ID should not be None after completion"

        # Verify that the payload made it into the thread messages
        expected_payload_data = {"task": "simple_math", "test_type": "e2e_comprehensive"}
        await _verify_payload_in_thread_messages(
            base_url_agent_server_workitems_matrix,
            agent_id,
            thread_id,
            expected_payload_data,
            work_item_id,
        )

        # Make sure the private v2 work-items endpoint is working:
        async with AsyncClient(base_url=f"{base_url_agent_server_workitems_matrix}/api/v2/work-items") as client:
            v2_list_resp = await client.get("/")
            assert v2_list_resp.status_code == 200
            v2_listed_items = v2_list_resp.json()["records"]
            v2_work_item_ids = [wi["work_item_id"] for wi in v2_listed_items]
            assert work_item_id in v2_work_item_ids

            # Verify updating the name of a work item is successful
            new_name = "Updated Work Item Name"
            update_resp = await client.patch(
                f"/{work_item_id}",
                json=dataclasses.asdict(UpdateWorkItemPayload(work_item_name=new_name)),
            )
            assert update_resp.status_code == 200
            updated_work_item = update_resp.json()
            assert updated_work_item["work_item_name"] == new_name
