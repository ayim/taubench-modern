from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

import psycopg
import pytest
import requests
from agent_platform.orchestrator.agent_server_client import AgentServerClient
from psycopg import rows
from sema4ai_docint import normalize_name

from agent_platform.core.document_intelligence.data_models import (
    CreateDataModelRequest,
    DataModelPayload,
)
from agent_platform.core.payloads.document_intelligence import DocumentLayoutPayload

from .helpers import upload_file_to_thread


@pytest.mark.spar
class TestDocumentLayouts:
    def _generate_document_layout(
        self,
        data_model_name: str,
        file: str,
        agent_id: str,
        thread_id: str,
        base_url: str,
    ) -> DocumentLayoutPayload:
        response = requests.post(
            f"{base_url}/document-intelligence/layouts/generate",
            files={"file": (None, file)},  # multipart keeps FastAPI's UploadFile|str happy
            params={
                "data_model_name": data_model_name,
                "agent_id": agent_id,
                "thread_id": thread_id,
            },
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as e:  # enrich CI failures with body
            raise AssertionError(
                "Failed to generate layout.\n"
                f"status={response.status_code}\n"
                f"url={response.request.url if response.request else 'unknown'}\n"
                f"body={response.text}"
            ) from e
        layout_response = response.json()["layout"]
        return DocumentLayoutPayload.model_validate(layout_response)

    def _upsert_document_layout(
        self,
        layout: DocumentLayoutPayload,
        base_url: str,
        layout_cleanup: Callable[[str, str], None],
    ):
        payload = asdict(layout)
        payload["extraction_schema"] = payload["extraction_schema"].model_dump(mode="json", exclude_none=True)
        response = requests.post(
            f"{base_url}/document-intelligence/layouts",
            json=payload,
        )
        response.raise_for_status()
        assert layout.name is not None
        assert layout.data_model_name is not None
        layout_cleanup(layout.name, layout.data_model_name)
        assert response.json()["ok"]

    def _get_document_layout(
        self,
        layout_name: str,
        data_model_name: str,
        base_url: str,
    ) -> DocumentLayoutPayload:
        response = requests.get(
            f"{base_url}/document-intelligence/layouts/{layout_name}",
            params={"data_model_name": data_model_name},
        )
        response.raise_for_status()
        return DocumentLayoutPayload.model_validate(response.json())

    def _update_document_layout(
        self,
        layout: DocumentLayoutPayload,
        layout_name: str,
        data_model_name: str,
        base_url: str,
    ):
        payload = {k: v for k, v in asdict(layout).items() if v is not None}
        response = requests.put(
            f"{base_url}/document-intelligence/layouts/{layout_name}",
            json=payload,
            params={"data_model_name": data_model_name},
        )
        response.raise_for_status()
        assert response.json()["ok"]

    def _assert_layout_is_in_db(
        self,
        layout: DocumentLayoutPayload,
        spar_postgres_url: str,
    ):
        with psycopg.connect(spar_postgres_url) as conn:
            with conn.cursor(row_factory=rows.dict_row) as cur:
                cur.execute(
                    "SELECT * FROM document_layouts WHERE name = %s AND data_model = %s",
                    (layout.name, layout.data_model_name),
                )
                row = cur.fetchone()
                assert row is not None, f"Layout {layout.name} not found in database"

                # Basic fields
                assert row["name"] == layout.name
                assert row["data_model"] == layout.data_model_name  # DB column is 'data_model'

    @pytest.mark.parametrize(
        ("first_file_name", "second_file_name"), [("sample_invoice_1.pdf", "sample_invoice_2.pdf")]
    )
    def test_generate_layout(
        self,
        spar_agent_server_base_url: str,
        agent_server_client_with_doc_int: AgentServerClient,
        agent_factory: Callable[[], str],
        first_file_name: str,
        second_file_name: str,
        spar_resources_path: Path,
        layout_cleanup: Callable[[str, str], None],
        data_model_cleanup: Callable[[str, str], None],
        spar_postgres_url: str,
    ):
        """Test will use two specific resource files and do the following:

        1. Generate a data model from the first file
        2. Generate a layout from the second file, using the data model from the first file
        3. Assert that the layout is generated correctly
        """
        first_file = spar_resources_path / first_file_name
        second_file = spar_resources_path / second_file_name

        data_model_name = normalize_name(first_file_name.split(".")[0])

        agent_id = agent_factory()
        thread_id = agent_server_client_with_doc_int.create_thread_and_return_thread_id(agent_id)

        first_file_upload_result = upload_file_to_thread(agent_server_client_with_doc_int, thread_id, first_file)

        # Generate a data model from the first file
        response = requests.post(
            f"{spar_agent_server_base_url}/document-intelligence/data-models/generate",
            data={"file": first_file_upload_result.file_ref},
            params={"agent_id": agent_id, "thread_id": thread_id},
        )
        response.raise_for_status()
        data_model_response = response.json()
        data_model_schema = data_model_response["model_schema"]

        # Upsert the data model so it can be used to generate a layout
        create_payload = CreateDataModelRequest(
            data_model=DataModelPayload(
                name=data_model_name,
                description=f"An Example {data_model_name} document",
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

        # Generate a layout for the second file
        second_file_upload_result = upload_file_to_thread(agent_server_client_with_doc_int, thread_id, second_file)
        layout = self._generate_document_layout(
            data_model_name,
            second_file_upload_result.file_ref,
            agent_id,
            thread_id,
            spar_agent_server_base_url,
        )
        assert layout.name is not None
        assert layout.data_model_name is not None

        # Upsert the new layout
        self._upsert_document_layout(layout, spar_agent_server_base_url, layout_cleanup)

        self._assert_layout_is_in_db(layout, spar_postgres_url)

        # Now get it so we can make a small change, like add a prompt
        layout = self._get_document_layout(layout.name, data_model_name, spar_agent_server_base_url)
        assert layout.name is not None
        self._update_document_layout(
            DocumentLayoutPayload.model_validate({"prompt": "This is a test prompt"}),
            layout.name,
            data_model_name,
            spar_agent_server_base_url,
        )
        updated_layout = self._get_document_layout(layout.name, data_model_name, spar_agent_server_base_url)
        assert updated_layout.prompt is not None
        assert updated_layout.prompt == "This is a test prompt"

        self._assert_layout_is_in_db(
            DocumentLayoutPayload.model_validate({**asdict(layout), "prompt": "This is a test prompt"}),
            spar_postgres_url,
        )
