import os
from unittest import mock
from unittest.mock import Mock, patch

import pytest
from reducto.types import ParseResponse
from sema4ai.data import DataSource, get_connection

from sema4ai_docint.models.constants import PROJECT_NAME
from sema4ai_docint.services._context import _DIContext
from sema4ai_docint.services._knowledge_base_service import _KnowledgeBaseService
from sema4ai_docint.services._setup_kb import _setup_kb
from sema4ai_docint.services.exceptions import KnowledgeBaseServiceError
from sema4ai_docint.utils import compute_document_id

# Test-specific constants to avoid interacting with production data
TEST_KNOWLEDGE_BASE_NAME = "test_documents"
TEST_PARSED_DOCUMENTS_TABLE_NAME = "test_parsed_documents"


@pytest.fixture
def patch_constants():
    """Fixture to patch constants with test values to avoid production data interaction."""
    patches = [
        # Patch in the constants module
        patch(
            "sema4ai_docint.models.constants.KNOWLEDGE_BASE_NAME",
            TEST_KNOWLEDGE_BASE_NAME,
        ),
        patch(
            "sema4ai_docint.models.constants.PARSED_DOCUMENTS_TABLE_NAME",
            TEST_PARSED_DOCUMENTS_TABLE_NAME,
        ),
        # Patch in the knowledge base service module
        patch(
            "sema4ai_docint.services._knowledge_base_service.KNOWLEDGE_BASE_NAME",
            TEST_KNOWLEDGE_BASE_NAME,
        ),
        patch(
            "sema4ai_docint.services._knowledge_base_service.PARSED_DOCUMENTS_TABLE_NAME",
            TEST_PARSED_DOCUMENTS_TABLE_NAME,
        ),
        # Patch in the setup kb module
        patch(
            "sema4ai_docint.services._setup_kb.KNOWLEDGE_BASE_NAME",
            TEST_KNOWLEDGE_BASE_NAME,
        ),
        patch(
            "sema4ai_docint.services._setup_kb.PARSED_DOCUMENTS_TABLE_NAME",
            TEST_PARSED_DOCUMENTS_TABLE_NAME,
        ),
    ]

    # Start all patches
    for p in patches:
        p.start()

    yield

    # Stop all patches
    for p in patches:
        p.stop()


@pytest.fixture
def cleanup_kb():
    """Fixture for cleaning up knowledge bases after tests."""
    try:
        yield
    finally:
        conn = get_connection()
        conn.execute_sql(f"DROP KNOWLEDGE_BASE IF EXISTS {PROJECT_NAME}.{TEST_KNOWLEDGE_BASE_NAME}")

        test_datasource_name = f"test_postgres_{os.getpid()}"
        try:
            conn.execute_sql(
                f"DROP TABLE IF EXISTS {test_datasource_name}.{TEST_PARSED_DOCUMENTS_TABLE_NAME}"
            )
        except Exception:
            pass


@pytest.fixture
def pgvector_datasource(postgres_datasource):
    """Create a PGVector datasource using postgres credentials."""
    pgvector_db_name = f"doc_int_pgvector_{os.getpid()!s}"

    conn = get_connection()
    connection_data = conn._get_datasource_info(postgres_datasource.datasource_name)[
        "connection_data"
    ]

    sql = f"""
    CREATE DATABASE IF NOT EXISTS {pgvector_db_name}
    WITH ENGINE = 'pgvector',
    PARAMETERS = {{
        "user": "{connection_data.get("user")}",
        "port": {connection_data.get("port", 5432)},
        "password": "{connection_data.get("password")}",
        "host": "{connection_data.get("host")}",
        "database": "{connection_data.get("database")}"
    }}
    """
    conn.execute_sql(sql)

    pgvector_datasource = DataSource.model_validate(datasource_name=pgvector_db_name)

    yield pgvector_datasource

    try:
        get_connection().execute_sql(f"DROP DATABASE IF EXISTS `{pgvector_db_name}`")
    except Exception:
        pass


@pytest.fixture
def kb_context(
    postgres_datasource, extraction_service, pgvector_datasource, agent_server_transport
):
    """
    Create a context with datasource, extraction service, and pgvector for knowledge base tests.

    Includes agent_server_transport so tests can configure file responses for ingest operations.
    """
    return _DIContext(
        datasource=postgres_datasource,
        extraction_service=extraction_service,
        pg_vector=pgvector_datasource,
        agent_server_transport=agent_server_transport,
    )


class TestKnowledgeBaseService:
    @pytest.fixture
    def kb_service(self, kb_context):
        """Create a KnowledgeBaseService instance for testing."""
        return _KnowledgeBaseService(kb_context)

    def test_ingest(
        self,
        setup_db,
        kb_service,
        postgres_datasource,
        test_pdf_path,
        cleanup_db,
        cleanup_kb,
        openai_api_key,
        patch_constants,
        agent_server_transport,
    ):
        """Test complete workflow: create KB, ingest INV-00001.pdf, and query for invoice total."""

        # Override the _insert_from_content function.
        kb_service._insert_from_content = Mock()

        mock_embedding_config = {
            "provider": "openai",
            "model_name": "text-embedding-3-large",
            "api_key": openai_api_key,
        }
        mock_reranking_config = {
            "provider": "openai",
            "model_name": "gpt-4o",
            "api_key": openai_api_key,
        }

        with (
            patch(
                "sema4ai_docint.services._setup_kb._get_model_configs_from_agent",
                return_value=(mock_embedding_config, mock_reranking_config),
            ),
            patch("sema4ai_docint.services._knowledge_base_service._setup_kb") as mock_setup_kb,
        ):
            # Override _setup_kb function.
            mock_setup_kb.return_value = "mocked setup"

            agent_server_transport.set_file_responses({"INV-00001.pdf": test_pdf_path})
            document_id = compute_document_id(test_pdf_path)

            ingest_result = kb_service.ingest("INV-00001.pdf")
            assert ingest_result == str(document_id)

            kb_service._context.extraction_service.upload.assert_called_once_with(test_pdf_path)
            # the ID from upload() should get passed into parse()
            kb_service._context.extraction_service.parse.assert_called_once_with(
                document_id="test-file-id-123",
                config=_KnowledgeBaseService._default_parse_opts(),
            )

            # Verify that we passed the output from Parse into the call to write to the KB.
            func_args = kb_service._insert_from_content.call_args_list
            assert len(func_args) == 1
            assert len(func_args[0].args) == 5, f"Captured arguments were: {func_args[0]}"
            actual_chunks = func_args[0].args[3]
            assert "Bill To: Avenue University" in str(actual_chunks), (
                "Did not find the expected chunks from Parse"
            )
            kb_service._insert_from_content.assert_called_once_with(
                postgres_datasource,
                TEST_KNOWLEDGE_BASE_NAME,
                "INV-00001.pdf",
                mock.ANY,
                document_id,
            )

    def test_query_missing_parameters(self, kb_service):
        """Test query when both document_name and document_id are missing."""
        with pytest.raises(
            KnowledgeBaseServiceError,
            match="Either document_name or document_id must be provided",
        ):
            kb_service.query(
                document_name=None,
                document_id=None,
                natural_language_query="test query",
            )

    def test_ingest_no_extraction_service(self, kb_service):
        """Test ingestion when extraction service is not available."""
        kb_service._context.extraction_service = None

        with pytest.raises(KnowledgeBaseServiceError, match="Extraction service is not available"):
            kb_service.ingest("test_document.pdf")

    def test_ingest_no_content_found(
        self,
        kb_service,
        test_pdf_path,
        agent_server_transport,
    ):
        """Test ingestion when no content is found in document."""
        # Mock the ExtractionService
        extraction_service = Mock()
        extraction_service.upload.return_value = "test-file-id-123"
        # Fake an empty parse response
        empty_parse_response = ParseResponse.model_construct(result=None)
        extraction_service.parse.return_value = empty_parse_response

        kb_service._context.extraction_service = extraction_service
        agent_server_transport.set_file_responses({"empty_document.pdf": test_pdf_path})

        # Mock the _setup_kb call to avoid database setup issues
        with (
            pytest.raises(ValueError, match="No content found in the document"),
            patch("sema4ai_docint.services._knowledge_base_service._setup_kb"),
        ):
            kb_service.ingest("empty_document.pdf")


class TestSetupKB:
    """Test the _setup_kb function with different datasource configurations."""

    def test_setup_kb_with_postgres_datasource(
        self,
        setup_db,
        postgres_datasource,
        pgvector_datasource,
        cleanup_db,
        cleanup_kb,
        openai_api_key,
        patch_constants,
    ):
        """Test _setup_kb with a postgres datasource and pgvector datasource."""

        # Mock the model configuration function using openai_api_key fixture
        mock_embedding_config = {
            "provider": "openai",
            "model_name": "text-embedding-3-large",
            "api_key": openai_api_key,
        }
        mock_reranking_config = {
            "provider": "openai",
            "model_name": "gpt-4o",
            "api_key": openai_api_key,
        }

        with patch(
            "sema4ai_docint.services._setup_kb._get_model_configs_from_agent",
            return_value=(mock_embedding_config, mock_reranking_config),
        ):
            # Call the real _setup_kb function with separate postgres and pgvector datasources
            result = _setup_kb(postgres_datasource, pgvector_datasource)

            # Verify the setup was successful
            assert f"Successfully set up knowledge base '{TEST_KNOWLEDGE_BASE_NAME}'" in result
            assert f"in project '{PROJECT_NAME}'" in result

            # Verify the knowledge base was actually created by checking it exists
            conn = get_connection()
            kb_list = conn.list_knowledge_bases()

            # Find our knowledge base in the list
            kb_found = False
            for kb in kb_list:
                if kb.name == TEST_KNOWLEDGE_BASE_NAME and kb.project == PROJECT_NAME:
                    kb_found = True
                    break

            assert kb_found, (
                f"Knowledge base '{TEST_KNOWLEDGE_BASE_NAME}' not found in "
                f"{[f'{kb.project}.{kb.name}' for kb in kb_list]}"
            )
