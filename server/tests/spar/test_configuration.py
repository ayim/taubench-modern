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
                # Check for data server integration in the new unified integration table
                cur.execute("SELECT count(*) FROM v2.integration WHERE kind = 'data_server'")
                row = cur.fetchone()
                assert row is not None, "Data server integration should be set up"
                assert row["count"] == 1, "Data server integration should be set up"

                # Check for reducto integration in the new unified integration table
                cur.execute("SELECT * FROM v2.integration WHERE kind = 'reducto'")
                row = cur.fetchone()
                print(row)
                assert row is not None, "Document intelligence integrations should be set up"
                assert row["kind"] == "reducto", "Document intelligence integration kind should be reducto"

        import json

        decrypted_settings_json = secret_service.fetch(row["enc_settings"])
        enc_settings = json.loads(decrypted_settings_json)
        backend_url = enc_settings["endpoint"]
        api_key = enc_settings["api_key"]

        assert backend_url is not None
        assert api_key is not None

        request = requests.get(
            backend_url + "/version",
            headers={"X-API-Key": api_key},
        )
        assert request.status_code == 200
