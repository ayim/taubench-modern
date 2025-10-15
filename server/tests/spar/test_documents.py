from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

import pytest
import requests
from agent_platform.orchestrator.agent_server_client import AgentServerClient
from sema4ai_docint import normalize_name

from agent_platform.core.document_intelligence.data_models import (
    CreateDataModelRequest,
    DataModelPayload,
)

from .helpers import upload_file_to_thread


@pytest.mark.spar
class TestDocuments:
    def test_ingest_document(
        self,
        spar_agent_server_base_url: str,
        agent_server_client_with_doc_int: AgentServerClient,
        agent_factory: Callable[[], str],
        spar_resources_path: Path,
        data_model_cleanup: Callable[[str, str], None],
    ):
        """Test document ingestion workflow:

        1. Generate a data model from sample_invoice_1.pdf
        2. Ingest the document using the data model and default layout
        3. Verify the response contains expected data
        """
        file_name = "sample_invoice_1.pdf"
        file_path = spar_resources_path / file_name

        data_model_name = normalize_name(file_name.split(".")[0])

        agent_id = agent_factory()
        thread_id = agent_server_client_with_doc_int.create_thread_and_return_thread_id(agent_id)

        file_upload_result = upload_file_to_thread(
            agent_server_client_with_doc_int, thread_id, file_path
        )

        # Step 1: Generate a data model from the file
        response = requests.post(
            f"{spar_agent_server_base_url}/document-intelligence/data-models/generate",
            data={"file": file_upload_result.file_ref},
            params={"agent_id": agent_id, "thread_id": thread_id},
        )
        response.raise_for_status()
        data_model_response = response.json()
        data_model_schema = data_model_response["model_schema"]

        # Upsert the data model so it can be used
        create_payload = CreateDataModelRequest(
            data_model=DataModelPayload(
                name=data_model_name,
                description=f"An example {data_model_name} document",
                model_schema=data_model_schema,
            )
        )
        response = requests.post(
            f"{spar_agent_server_base_url}/document-intelligence/data-models",
            json=asdict(create_payload),
            params={"agent_id": agent_id},
        )
        response.raise_for_status()
        assert response.json()["data_model"]["name"] == data_model_name
        data_model_cleanup(data_model_name, agent_id)

        # Step 2: Ingest the document using the default layout
        response = requests.post(
            f"{spar_agent_server_base_url}/document-intelligence/documents/ingest",
            data={
                "file": file_upload_result.file_ref,
            },
            params={
                "agent_id": agent_id,
                "thread_id": thread_id,
                "data_model_name": data_model_name,
                "layout_name": "default",
            },
        )
        response.raise_for_status()
        ingest_response = response.json()

        # Step 3: Verify the response
        assert "document" in ingest_response
        assert ingest_response["document"] is not None
        # The document should contain extracted data based on the schema
        document_data = ingest_response["document"]
        assert isinstance(document_data, dict)
        # Basic sanity check that we got some data back
        assert len(document_data) > 0
