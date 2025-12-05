import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
from reducto.types.shared import BoundingBox, ParseResponse, ParseUsage
from reducto.types.shared.parse_response import (
    ResultFullResult,
    ResultFullResultChunk,
    ResultFullResultChunkBlock,
)

from sema4ai_docint.extraction.reducto.sync import SyncExtractionClient
from sema4ai_docint.models.data_model import DataModel
from sema4ai_docint.models.extraction import ExtractionResult
from sema4ai_docint.services._context import _DIContext
from sema4ai_docint.services._data_model import _DataModelService
from sema4ai_docint.services._document import _DocumentService
from sema4ai_docint.services._knowledge_base_service import _KnowledgeBaseService
from sema4ai_docint.services._layout import _LayoutService
from tests.agent_dummy_server import AgentDummyServer
from tests.agent_server_client.conftest import MockTransport


@pytest.fixture
def data_model_data(mindsdb_db_name: str) -> dict[str, Any]:
    """Load test data model from JSON file and substitute the correct database name."""
    with open(Path(__file__).parent / "assets" / "data_model.json") as f:
        data = json.load(f)

    data_model = data[0]
    if data_model.get("views"):
        for view in data_model["views"]:
            if "sql" in view:
                import re

                view["sql"] = re.sub(r"`test_postgres_\d+`", f"`{mindsdb_db_name}`", view["sql"])

    return data_model


@pytest.fixture
def document_layout_data() -> dict[str, Any]:
    """Load test document layout from JSON file."""
    with open(Path(__file__).parent / "assets" / "document_layout.json") as f:
        data = json.load(f)
    return data[0]


@pytest.fixture
def document_data() -> dict[str, Any]:
    """Load test document from JSON file."""
    with open(Path(__file__).parent / "assets" / "document.json") as f:
        data = json.load(f)
    return data[0]


@pytest.fixture
def test_pdf_path() -> Path:
    """Return path to test PDF file for service tests."""
    return Path(__file__).parent / "assets" / "INV-00001.pdf"


@pytest.fixture
def extraction_service(agent_dummy_server):
    """Create a SYNC extraction service with test API key and mock its methods.

    Note: This creates SyncExtractionClient because the context expects that type.
    The sync client wraps an async client internally.
    """
    service = SyncExtractionClient(api_key="test_api_key")

    # Mock ExtractionService.upload
    service.upload = Mock(return_value="test-file-id-123")

    # Mock ExtractionService.parse
    def _mock_parse(*args, **kwargs) -> ParseResponse:
        # Create mock chunks that match ResultFullResultChunk structure
        chunk1 = ResultFullResultChunk(
            blocks=[
                ResultFullResultChunkBlock.model_construct(
                    bbox=BoundingBox.model_construct(
                        height=50.0,
                        left=50.0,
                        page=1,
                        top=700.0,
                        width=250.0,
                        original_page=1,
                    ),
                    content=(
                        "INVOICE\nInvoice Number: INV-00001\nDate: August 20, 2025\n"
                        "Bill To: Avenue University\n123 University Ave\nSuite 456\n"
                        "Dallas, TX 75201"
                    ),
                    type="Text",
                    confidence="high",
                    image_url=None,
                )
            ],
            content=(
                "INVOICE\nInvoice Number: INV-00001\nDate: August 20, 2025\n"
                "Bill To: Avenue University\n123 University Ave\nSuite 456\n"
                "Dallas, TX 75201"
            ),
            embed=(
                "INVOICE\nInvoice Number: INV-00001\nDate: August 20, 2025\n"
                "Bill To: Avenue University\n123 University Ave\nSuite 456\n"
                "Dallas, TX 75201"
            ),
        )

        return ParseResponse.model_construct(
            result=ResultFullResult(
                chunks=[chunk1],
                type="full",
            ),
            duration=2.5,
            job_id="test-job-123",
            usage=ParseUsage.model_construct(
                num_pages=1,
                credits=10.0,
            ),
        )

    service.parse = Mock(side_effect=_mock_parse)

    # Default extraction result for mocking - must be ExtractionResult object with results field
    default_result = ExtractionResult(
        results={
            "items": [
                {
                    "rate": "$55.00",
                    "amount": "$5,500.00",
                    "quantity": "100",
                    "description": "Services",
                },
                {
                    "rate": "$35.00",
                    "amount": "$1,750.00",
                    "quantity": "50",
                    "description": "Support",
                },
            ],
            "total": "$7,250.00",
            "due_date": "September 19, 2025",
            "billed_to": "Test Client",
            "amount_due": "$7,250.00",
            "balance_due": "$7,250.00",
            "date_issued": "August 20, 2025",
            "invoice_number": "INV-TEST-001",
        },
        citations=None,
    )

    # Mock all extraction methods as SYNC functions (SyncExtractionClient wraps async internally)
    service.extract = Mock(return_value=default_result)
    service.extract_with_data_model = Mock(return_value=default_result)
    service.extract_with_schema = Mock(return_value=default_result)

    return service


@pytest.fixture
def agent_server_transport():
    """Create a mock agent server transport for testing.

    NOTE: This should only be used by tests that explicitly configure mock responses.
    Tests using agent_dummy_server should NOT use this fixture - they should pass
    agent_server_transport=None to let HTTPTransport be created automatically.

    TODO: We should likely refactor tests generally to use one or the other, perhaps when
    we remove deprecated SyncExtractionClient.
    """
    return MockTransport(agent_id="test_agent")


@pytest.fixture
def context(postgres_datasource, extraction_service):
    """Create a context with actual datasource and extraction service.

    NOTE: agent_server_transport is NOT provided here, so AgentServerClient will create
    an HTTPTransport by default. This allows tests using agent_dummy_server to work properly.
    Tests that need MockTransport should explicitly inject it.

    TODO: We should likely refactor tests generally to use one or the other, perhaps when
    we remove deprecated SyncExtractionClient.
    """
    return _DIContext(
        datasource=postgres_datasource,
        extraction_service=extraction_service,
        agent_server_transport=None,  # Let HTTPTransport be created from env vars
    )


@pytest.fixture
def context_with_transport(postgres_datasource, extraction_service, agent_server_transport):
    """Create a context with mock transport for tests that need get_file().

    Use this for tests that call get_file() and need to configure file responses.
    """
    return _DIContext(
        datasource=postgres_datasource,
        extraction_service=extraction_service,
        agent_server_transport=agent_server_transport,
    )


@pytest.fixture
def document_service(context_with_transport):
    """Create a DocumentService instance for testing.

    Uses context_with_transport so tests can configure file responses via agent_server_transport.
    """
    return _DocumentService(context_with_transport)


@pytest.fixture
def layout_service(context):
    """Create a LayoutService instance for testing."""
    return _LayoutService(context)


@pytest.fixture
def data_model_service(context):
    """Create a DataModelService instance for testing."""
    return _DataModelService(context)


@pytest.fixture
def knowledge_base_service(context):
    """Create a KnowledgeBaseService instance for testing."""
    return _KnowledgeBaseService(context)


@pytest.fixture
def drop_mindsdb_views():
    """Ensure MindsDB views are dropped before and after each test to avoid stale integrations."""
    from sema4ai.data import get_connection

    from sema4ai_docint.models.constants import PROJECT_NAME

    conn = get_connection()
    try:
        # We should avoid using the "real" PROJECT_NAME in tests.
        conn.execute_sql(f"CREATE PROJECT IF NOT EXISTS {PROJECT_NAME}")
        conn.execute_sql(f"DROP VIEW IF EXISTS {PROJECT_NAME}.TEST_ITEMS")

        yield
    finally:
        conn.execute_sql(f"DROP VIEW IF EXISTS {PROJECT_NAME}.TEST_ITEMS")


@pytest.fixture
def setup_data_model(postgres_datasource, data_model_data):
    """Set up a test data model by inserting into the PostgreSQL database."""
    data_model = DataModel(**data_model_data)
    data_model.insert(postgres_datasource)
    return data_model


@pytest.fixture
def agent_dummy_server(request):
    """Start AgentDummyServer for testing with configurable responses."""
    from pathlib import Path

    # Get responses from test parameter if provided
    responses = getattr(request, "param", None)

    # Start the dummy server
    server = AgentDummyServer(responses)
    server.start()

    # Set environment variables to point to the dummy server
    original_agents_url = os.environ.get("SEMA4AI_AGENTS_SERVICE_URL")
    original_file_url = os.environ.get("SEMA4AI_FILE_MANAGEMENT_URL")

    os.environ["SEMA4AI_AGENTS_SERVICE_URL"] = f"http://localhost:{server.get_port()}"

    # Set up file management URL for test data
    test_data_dir = Path(__file__).parent / "assets"
    os.environ["SEMA4AI_FILE_MANAGEMENT_URL"] = f"file://{test_data_dir.absolute()}"

    try:
        yield server
    finally:
        # Cleanup
        server.stop()

        # Restore original environment variables
        if original_agents_url is not None:
            os.environ["SEMA4AI_AGENTS_SERVICE_URL"] = original_agents_url
        else:
            os.environ.pop("SEMA4AI_AGENTS_SERVICE_URL", None)

        if original_file_url is not None:
            os.environ["SEMA4AI_FILE_MANAGEMENT_URL"] = original_file_url
        else:
            os.environ.pop("SEMA4AI_FILE_MANAGEMENT_URL", None)
