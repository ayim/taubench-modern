from urllib.parse import urljoin

import psycopg
import pytest
import requests
from agent_platform.orchestrator.agent_server_client import AgentServerClient
from psycopg.rows import dict_row

from agent_platform.server.secret_manager.base import BaseSecretManager
from agent_platform.server.secret_manager.option import SecretService

secret_service = SecretService.get_instance()


@pytest.mark.spar
class TestDocumentIntelligenceConfiguration:
    def test_document_intelligence_ok(
        self,
        agent_server_client_with_doc_int: AgentServerClient,
        spar_postgres_url: str,
        secret_service: BaseSecretManager,
    ):
        url = urljoin(agent_server_client_with_doc_int.base_url + "/", "document-intelligence/ok")
        response = requests.get(url)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(
                f"Error checking document intelligence: {response.status_code} {response.text}",
            ) from e
        assert response.status_code == requests.codes.ok

        with psycopg.connect(spar_postgres_url) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT count(*) FROM v2.dids_connection_details")
                row = cur.fetchone()
                assert row is not None, "DIDS connection details should be set up"
                assert row["count"] == 1, "DIDS connection details should be set up"

                cur.execute("SELECT * FROM v2.document_intelligence_integrations")
                row = cur.fetchone()
                print(row)
                assert row is not None, "Document intelligence integrations should be set up"
                assert row["kind"] == "reducto", (
                    "Document intelligence integration kind should be reducto"
                )

        backend_url = row["endpoint"]
        api_key = secret_service.fetch(row["enc_api_key"])
        print(f"Backend URL: {backend_url}")
        print(f"API Key: {api_key}")
        request = requests.get(
            backend_url + "/version",
            headers={"X-API-Key": api_key},
        )
        assert request.status_code == 200
