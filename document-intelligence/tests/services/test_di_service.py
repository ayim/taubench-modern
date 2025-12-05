"""
Tests for the DIService factory method and service initialization.
"""

from unittest.mock import Mock

import pytest
from sema4ai.data import DataSource

from sema4ai_docint.extraction.reducto import AsyncExtractionClient, SyncExtractionClient
from sema4ai_docint.services import DIService, build_di_service
from sema4ai_docint.services._data_model import _DataModelService
from sema4ai_docint.services._document import _DocumentService
from sema4ai_docint.services._knowledge_base_service import _KnowledgeBaseService
from sema4ai_docint.services._layout import _LayoutService


class TestBuildDIService:
    @pytest.fixture
    def mock_datasource(self):
        return Mock(spec=DataSource)

    def test_build_di_service_minimal_parameters(self, mock_datasource):
        """Test building DIService with minimal parameters (no API key)."""
        di_service = build_di_service(datasource=mock_datasource)

        assert isinstance(di_service, DIService)
        assert di_service.document is not None
        assert isinstance(di_service.document, _DocumentService)
        assert di_service.layout is not None
        assert isinstance(di_service.layout, _LayoutService)
        assert di_service.data_model is not None
        assert isinstance(di_service.data_model, _DataModelService)

        # Without API key, extraction service should be None
        assert di_service.extraction is None

    def test_build_di_service_with_api_key(self, mock_datasource):
        """Test building DIService with sema4_api_key (extraction service available)."""
        api_key = "test-api-key"

        di_service = build_di_service(
            datasource=mock_datasource,
            sema4_api_key=api_key,
            disable_ssl_verification=False,
        )

        assert isinstance(di_service, DIService)
        assert di_service.extraction is not None
        assert isinstance(di_service.extraction, SyncExtractionClient)
        assert isinstance(di_service.extraction_async, AsyncExtractionClient)

    def test_build_di_service_context_shared_across_services(self, mock_datasource):
        """Test that the same context is shared across all services."""
        # Act
        di_service = build_di_service(datasource=mock_datasource)

        # Assert - Access the private context from each service
        document_context = di_service.document._context
        layout_context = di_service.layout._context
        data_model_context = di_service.data_model._context

        # All services should share the same context instance
        assert document_context is layout_context
        assert layout_context is data_model_context
        assert document_context.datasource is mock_datasource

    def test_build_di_service_with_pgvector(self, mock_datasource):
        """Test building DIService with pgvector datasource (knowledge base service available)."""
        mock_pgvector = Mock(spec=DataSource)

        di_service = build_di_service(
            datasource=mock_datasource,
            pg_vector=mock_pgvector,
        )

        assert isinstance(di_service, DIService)
        assert di_service.knowledge_base is not None
        assert isinstance(di_service.knowledge_base, _KnowledgeBaseService)

        # Verify that the context has the pgvector datasource
        assert di_service._context.pg_vector is mock_pgvector

    def test_build_di_service_without_pgvector(self, mock_datasource):
        """
        Test building DIService without pgvector datasource (knowledge base service unavailable).
        """
        di_service = build_di_service(datasource=mock_datasource)

        assert isinstance(di_service, DIService)
        assert di_service.knowledge_base is None

        # Verify that the context has no pgvector datasource
        assert di_service._context.pg_vector is None
