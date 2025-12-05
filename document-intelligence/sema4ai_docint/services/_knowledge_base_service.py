import base64
import json

from sema4ai.data import DataSource, get_connection

from sema4ai_docint.logging import logger
from sema4ai_docint.models.constants import (
    KNOWLEDGE_BASE_NAME,
    PARSED_DOCUMENTS_TABLE_NAME,
    PROJECT_NAME,
)
from sema4ai_docint.utils import compute_document_id

from ._context import _DIContext
from ._setup_kb import _setup_kb
from .dto import KnowledgeBaseQueryResult
from .exceptions import KnowledgeBaseServiceError


def _normalize_text_for_comparison(text: str) -> str:
    import re

    normalized = re.sub(r"\s+", " ", text.strip())
    return normalized


class _KnowledgeBaseService:
    def __init__(self, context: _DIContext) -> None:
        self._context = context

    @classmethod
    def _default_parse_opts(cls) -> dict:
        """
        Default parse options for the KB Service to use when calling Reducto.
        """
        return {
            "options": {
                "chunking": {"chunk_mode": "page"},
            },
        }

    def query(
        self,
        document_name: str | None,
        document_id: str | None,
        natural_language_query: str,
        relevance: float = 0.7,
    ) -> list[KnowledgeBaseQueryResult]:
        """
        Search the knowledge base for the query

        Args:
            document_name: The name of the file to search in (optional, can be used alone or with
                document_id)
            document_id: The document ID to search in (optional, can be used alone or with
                document_name)
            natural_language_query: The query to search for
            relevance: The relevance threshold for the search

        Returns:
            A list of KnowledgeBaseQueryResult objects.

        Note:
            - At least one of document_name or document_id must be provided
            - If both document_name and document_id are provided, a composite search is performed
        """
        if not document_name and not document_id:
            raise KnowledgeBaseServiceError("Either document_name or document_id must be provided")

        params = {
            "natural_language_query": natural_language_query,
            "relevance": relevance,
        }
        where_clause_params = {}

        where_clauses = []
        if document_name:
            where_clauses.append("document_name = $document_name")
            where_clause_params["document_name"] = document_name
        if document_id:
            where_clauses.append("id = $id")
            where_clause_params["id"] = document_id

        where_clause = " and ".join(where_clauses)
        params.update(where_clause_params)

        sql = f"""
        SELECT id, metadata, chunk_content, relevance, distance
            FROM {PROJECT_NAME}.{KNOWLEDGE_BASE_NAME}
        WHERE {where_clause}
        AND content = $natural_language_query AND relevance >= $relevance
        """

        raw_results = get_connection().execute_sql(sql, params=params).to_dict_list()

        # Enhance results with page and bbox information from parsed documents
        enhanced_results = []
        for result in raw_results:
            kb_result = KnowledgeBaseQueryResult(**result)
            enhanced_result = self._enhance_result_with_page_info(
                self._context.datasource, where_clause, where_clause_params, kb_result
            )
            enhanced_results.append(enhanced_result)

        return enhanced_results

    def _enhance_result_with_page_info(
        self,
        datasource: DataSource,
        where_clause: str,
        where_clause_params: dict,
        kb_result: KnowledgeBaseQueryResult,
    ) -> KnowledgeBaseQueryResult:
        """
        Enhance a KB result with page number and bounding box information.

        Args:
            kb_result: KnowledgeBaseQueryResult object

        Returns:
            Enhanced KnowledgeBaseQueryResult with page and bbox info
        """
        metadata = kb_result.metadata or {}
        kb_result.document_name = metadata.get("document_name")

        doc_sql = f"""
        SELECT extracted_chunks FROM {datasource.datasource_name}.{PARSED_DOCUMENTS_TABLE_NAME}
        WHERE {where_clause}
        """
        doc_result = datasource.execute_sql(doc_sql, params=where_clause_params).to_dict_list()

        doc_result = doc_result[0] if doc_result else None
        if not doc_result:
            return kb_result

        chunks = doc_result["extracted_chunks"]
        kb_chunk_content = kb_result.chunk_content

        first_page = None
        matching_chunk = None
        for chunk in chunks:
            chunk_embed = chunk.get("embed", "")
            # Normalize both texts to handle whitespace/newline differences
            normalized_chunk_embed = _normalize_text_for_comparison(chunk_embed)
            normalized_kb_content = _normalize_text_for_comparison(kb_chunk_content)

            if normalized_kb_content not in normalized_chunk_embed:
                continue

            blocks = chunk.get("blocks", [])
            if blocks:
                first_page = blocks[0]["bbox"].get("original_page")

            matching_chunk = chunk
            break

        kb_result.page_number = first_page
        kb_result.chunk = matching_chunk

        return kb_result

    def ingest(self, document_name: str, reducto_parse_config: dict | None = None) -> str:
        """
        Ingest a document into the knowledge base for semantic search and retrieval.

        Args:
            document_name: The name of the file to ingest
            reducto_parse_config: Optional configuration for the Reducto parse service

        Returns:
            Unique identifier for the document.
        """
        if self._context.extraction_service is None:
            raise KnowledgeBaseServiceError(
                "Extraction service is not available. Please set the sema4_api_key in the context."
            )
        assert self._context.agent_server_transport is not None, "AgentServer is not available"
        assert self._context.pg_vector is not None, "PGVector datasource was not provided"

        file_path = self._context.agent_server_transport.get_file(document_name)

        _setup_kb(self._context.datasource, self._context.pg_vector)

        if not reducto_parse_config:
            reducto_parse_config = _KnowledgeBaseService._default_parse_opts()

        document_id = compute_document_id(file_path)
        file_id = self._context.extraction_service.upload(file_path)
        document_data = self._context.extraction_service.parse(
            document_id=file_id,
            config=reducto_parse_config,
        )

        if not document_data.result:
            logger.info(f"No content found in the document {document_name}")
            raise ValueError(f"No content found in the document {document_name}")

        chunks = [chunk.model_dump() for chunk in document_data.result.chunks]

        self._insert_from_content(
            self._context.datasource,
            KNOWLEDGE_BASE_NAME,
            document_name,
            chunks,
            document_id,
        )

        return document_id

    def _insert_from_content(
        self,
        datasource: DataSource,
        kb_name: str,
        document_name: str,
        chunks: list[dict],
        document_id: str,
    ) -> None:
        chunks_string = json.dumps(chunks)
        b64_chunks = base64.b64encode(chunks_string.encode("utf-8")).decode("utf-8")

        datasource.native_query(
            f"""
            INSERT INTO {PARSED_DOCUMENTS_TABLE_NAME} (id, document_name, extracted_chunks)
            VALUES ($document_id, $document_name,
                convert_from(decode($b64_chunks, 'base64'), 'UTF8')::jsonb)
            ON CONFLICT (id) DO UPDATE SET
                document_name = EXCLUDED.document_name,
                extracted_chunks = EXCLUDED.extracted_chunks
            """,
            params={
                "document_id": document_id,
                "document_name": document_name,
                "b64_chunks": b64_chunks,
            },
        )

        # Delete any existing knowledge base entries for this document_id before inserting new ones
        delete_sql = f"""
        DELETE FROM {PROJECT_NAME}.{kb_name}
        WHERE document_id = $document_id
        """
        datasource.execute_sql(delete_sql, params={"document_id": document_id})

        sql = f"""
        INSERT INTO {PROJECT_NAME}.{kb_name} (
            document_id,
            document_name,
            chunk_content
        )
        SELECT
            id,
            document_name,
            jsonb_array_elements(extracted_chunks)->>'embed' as chunk_content
        FROM {datasource.datasource_name}.{PARSED_DOCUMENTS_TABLE_NAME}
        WHERE id = $document_id
        """

        datasource.execute_sql(sql, params={"document_id": document_id})
