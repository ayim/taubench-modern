import dataclasses
import uuid
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import httpx
import jsonschema
import psycopg
import pytest
import pytz
from agent_platform.orchestrator.agent_server_client import AgentServerClient
from psycopg import rows

from agent_platform.core.document_intelligence.data_models import (
    CreateDataModelRequest,
    DataModelPayload,
)


@pytest.mark.spar
class TestDataModels:
    """Live REST test against a running agent_server on localhost:8000."""

    def test_generate_then_create_data_model(
        self,
        spar_agent_server_base_url: str,
        agent_server_client_with_doc_int: AgentServerClient,
        agent_factory: Callable[[], str],
        spar_postgres_url: str,
        data_model_cleanup: Callable[[str, str], None],
    ):
        # Sanity check that the DocInt data source is set up
        resp = httpx.get(f"{spar_agent_server_base_url}/document-intelligence/ok")
        assert resp.status_code == 200, resp.text

        agent_id = agent_factory()
        thread_id = agent_server_client_with_doc_int.create_thread_and_return_thread_id(agent_id)

        # 1) Generate a data model schema from a sample PDF upload
        pdf_path = Path(__file__).parent / "resources" / "ski_rental.pdf"
        with open(pdf_path, "rb") as f:
            pdf_content = f.read()

        files = {
            "file": (
                "ski_rental.pdf",
                pdf_content,
                "application/pdf",
            )
        }
        params = {
            "thread_id": thread_id,
            "agent_id": agent_id,
        }
        data = {
            "instructions": "The results of each safety check should be included and be "
            "a pass/fail enumeration.",
        }
        gen_resp = httpx.post(
            f"{spar_agent_server_base_url}/document-intelligence/data-models/generate",
            params=params,
            files=files,
            data=data,
            timeout=120,
        )
        gen_resp.raise_for_status()

        # Verify that we got a valid jsonschema
        gen_body = gen_resp.json()
        assert "model_schema" in gen_body
        jsonschema.Draft7Validator.check_schema(gen_body["model_schema"])

        # 2) Create the data model using the generated schema
        model_name = f"test_ski_rental_{uuid.uuid4().hex[:8]}"
        create_payload = CreateDataModelRequest(
            data_model=DataModelPayload(
                name=model_name,
                description="An Example Ski Rental equipment safety report",
                model_schema=gen_body["model_schema"],
            )
        )
        create_resp = httpx.post(
            f"{spar_agent_server_base_url}/document-intelligence/data-models?agent_id={agent_id}",
            json=dataclasses.asdict(create_payload),
            timeout=60,
        )
        # Expect 201 Created
        assert create_resp.status_code == 201, create_resp.text
        created = create_resp.json()
        assert "data_model" in created
        assert created["data_model"]["name"]

        # Register for cleanup - this ensures deletion regardless of test outcome
        data_model_cleanup(model_name, agent_id)

        # Verify the response model is as we expect.
        assert isinstance(created["data_model"]["views"], list)
        assert len(created["data_model"]["views"]) == 1
        assert isinstance(created["data_model"]["quality_checks"], list)
        assert len(created["data_model"]["quality_checks"]) == 0
        assert created["data_model"]["prompt"] is None, (
            "Prompt was not provided and should not be set"
        )
        assert created["data_model"]["summary"], "Summary should be auto-generated"

        assert created["data_model"]["created_at"] is not None
        created_at = datetime.fromisoformat(created["data_model"]["created_at"]).replace(
            tzinfo=pytz.UTC
        )

        assert created["data_model"]["updated_at"] is not None
        updated_at = datetime.fromisoformat(created["data_model"]["updated_at"]).replace(
            tzinfo=pytz.UTC
        )

        # Verify the data model was created in the database
        with psycopg.connect(spar_postgres_url) as conn:
            with conn.cursor(row_factory=rows.dict_row) as cur:
                cur.execute("SELECT * FROM data_models WHERE name = %s", (model_name,))
                row = cur.fetchone()
                assert row is not None
                assert row["name"] == model_name
                assert row["description"] == "An Example Ski Rental equipment safety report"
                assert isinstance(row["model_schema"], dict), "Data model schema should be a dict"
                assert row["model_schema"] == gen_body["model_schema"]
                assert len(row["views"]) == 1
                assert len(row["quality_checks"]) == 0
                assert row["prompt"] is None
                assert row["summary"] == created["data_model"]["summary"]
                # Make sure to compare UTC timestamps
                assert row["created_at"].replace(tzinfo=pytz.UTC) == created_at
                assert row["updated_at"].replace(tzinfo=pytz.UTC) == updated_at

    def test_modify_incomplete_invoice_schema(
        self,
        spar_agent_server_base_url: str,
        agent_server_client_with_doc_int: AgentServerClient,
        agent_factory: Callable[[], str],
    ):
        agent_id = agent_factory()
        thread_id = agent_server_client_with_doc_int.create_thread_and_return_thread_id(agent_id)

        # Define an incomplete invoice schema that's missing several key fields
        incomplete_schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "Dental Supply Invoice",
            "description": (
                "Schema representing an invoice for dental supplies, "
                "including customer details, items, and totals."
            ),
            "type": "object",
            "properties": {
                "invoice_number": {
                    "type": "string",
                    "description": (
                        "Unique identifier for the invoice, typically found "
                        "near the top right (e.g., 'Invoice #5465')."
                    ),
                },
                "invoice_date": {
                    "type": "string",
                    "description": (
                        "The date the invoice was issued, located near the "
                        "invoice number (e.g., '8/28/2025')."
                    ),
                },
            },
            "required": [
                "invoice_number",
                "invoice_date",
            ],
        }

        # Upload the invoice PDF to provide context for the modification
        pdf_path = Path(__file__).parent / "resources" / "sample_invoice_2.pdf"
        with open(pdf_path, "rb") as f:
            pdf_content = f.read()

        files = {
            "files": (
                "sample_invoice_2.pdf",
                pdf_content,
                "application/pdf",
            )
        }

        # Upload file to thread
        upload_response = httpx.post(
            f"{spar_agent_server_base_url}/threads/{thread_id}/files",
            files=files,
        )
        upload_response.raise_for_status()

        # Modify the incomplete schema to add missing fields using the PDF context
        params = {
            "thread_id": thread_id,
            "agent_id": agent_id,
        }
        modify_resp = httpx.post(
            f"{spar_agent_server_base_url}/document-intelligence/data-models/modify",
            json={
                "schema": incomplete_schema,
                "instructions": "Add the missing items table to the schema.",
                "file_name": "sample_invoice_2.pdf",
            },
            params=params,
            timeout=120,
        )
        modify_resp.raise_for_status()

        # Verify that we got a valid jsonschema, all other fields are generative
        modify_body = modify_resp.json()
        jsonschema.Draft7Validator.check_schema(modify_body)
