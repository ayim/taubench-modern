import base64
import json
import uuid
from typing import Any

from pydantic import BaseModel, Json, field_validator
from sema4ai.data import DataSource


class Document(BaseModel):
    id: str
    document_name: str
    document_layout: str | None = None
    data_model: str
    extracted_content: Json[dict[str, Any]] | None = None
    translated_content: Json[dict[str, Any]] | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @field_validator("extracted_content", "translated_content", mode="before")
    @classmethod
    def validate_content(cls, value: str | dict[str, Any] | None) -> str | None:
        # Accept a dict or a string which contains a json object
        if value is None:
            return None
        if isinstance(value, dict):
            return json.dumps(value)
        # TODO validate that `value` is valid json
        return value

    def insert(self, ds: DataSource) -> None:
        """Insert the document into the database."""
        # Encode JSONB fields as base64 for maximum SQL safety
        extracted_content_val = (
            json.dumps(self.extracted_content) if self.extracted_content else "{}"
        )
        b64_extracted_content = base64.b64encode(extracted_content_val.encode("utf-8")).decode(
            "utf-8"
        )

        translated_content_val = (
            json.dumps(self.translated_content) if self.translated_content else "{}"
        )
        b64_translated_content = base64.b64encode(translated_content_val.encode("utf-8")).decode(
            "utf-8"
        )

        query = """
            INSERT INTO documents
                (id, document_name, document_layout, data_model, extracted_content,
                 translated_content)
            VALUES
                ($id,
                 $document_name,
                 $document_layout,
                 $data_model,
                 convert_from(decode($b64_extracted_content, 'base64'), 'UTF8')::JSONB,
                 convert_from(decode($b64_translated_content, 'base64'), 'UTF8')::JSONB
            )
        """

        ds.native_query(
            query,
            params={
                "id": self.id,
                "document_name": self.document_name,
                "document_layout": self.document_layout
                if self.document_layout is not None
                else "NULL",
                "data_model": self.data_model if self.data_model is not None else "NULL",
                "b64_extracted_content": b64_extracted_content,
                "b64_translated_content": b64_translated_content,
            },
        )

    def update(self, ds: DataSource) -> None:
        """Update the document in the database."""
        # Encode JSONB fields as base64 for maximum SQL safety
        extracted_content_val = (
            json.dumps(self.extracted_content) if self.extracted_content else "{}"
        )
        b64_extracted_content = base64.b64encode(extracted_content_val.encode("utf-8")).decode(
            "utf-8"
        )

        translated_content_val = (
            json.dumps(self.translated_content) if self.translated_content else "{}"
        )
        b64_translated_content = base64.b64encode(translated_content_val.encode("utf-8")).decode(
            "utf-8"
        )

        query = """
            update documents
            set
                document_name = $document_name,
                document_layout = $document_layout,
                data_model = $data_model,
                extracted_content = convert_from(decode($b64_extracted_content, 'base64'),
                    'UTF8')::JSONB,
                translated_content = convert_from(decode($b64_translated_content, 'base64'),
                    'UTF8')::JSONB,
                updated_at = now()
            where id = $id
        """

        ds.native_query(
            query,
            params={
                "id": self.id,
                "document_name": self.document_name,
                "document_layout": self.document_layout
                if self.document_layout is not None
                else "NULL",
                "data_model": self.data_model if self.data_model is not None else "NULL",
                "b64_extracted_content": b64_extracted_content,
                "b64_translated_content": b64_translated_content,
            },
        )

    def delete(self, ds: DataSource) -> bool:
        """Delete the document from the database."""
        query = """
            delete from documents
            where id = $id
            returning 1;
        """

        result = ds.native_query(
            query,
            params={
                "id": self.id,
            },
        )
        rows = [t for t in result.iter_as_tuples()]
        # expect one row which has one column
        if not rows or len(rows[0]) != 1:
            return False

        return rows[0][0] == 1

    @classmethod
    def find_all(cls, ds: DataSource) -> list["Document"]:
        """Find all documents metadata."""
        # Only return metadata about the document, not the content
        query = """
            select id, document_name, document_layout, data_model, created_at, updated_at
            from documents
        """
        return ds.native_query(query).build_list(Document)

    @classmethod
    def find_by_id(cls, ds: DataSource, doc_id: str) -> "Document | None":
        """Find a document metadata by id."""
        # Return the full document object
        query = """
            select id, document_name, document_layout, data_model, extracted_content,
                   translated_content, created_at, updated_at from documents
            where id = $id
        """

        result = ds.native_query(
            query,
            params={
                "id": doc_id,
            },
        )
        dict_results = result.to_dict_list()
        if not dict_results:
            return None

        return Document(**dict_results[0])  # type: ignore

    @classmethod
    def find_by_name(cls, ds: DataSource, document_name: str) -> list["Document"]:
        """Find all documents with a given name."""
        query = """
            select id, document_name, document_layout, data_model, extracted_content,
                   translated_content, created_at, updated_at
            from documents
            where document_name = $document_name
        """

        result = ds.native_query(
            query,
            params={
                "document_name": document_name,
            },
        )
        return result.build_list(Document)

    @classmethod
    def find_by_document_layout(
        cls, ds: DataSource, data_model: str, document_layout: str
    ) -> list["Document"]:
        """Find all documents metadata for a given document layout."""
        query = """
            select id, document_name, document_layout, data_model, extracted_content,
                   translated_content, created_at, updated_at from documents
            where data_model = $data_model and document_layout = $document_layout
        """

        result = ds.native_query(
            query,
            params={
                "data_model": data_model,
                "document_layout": document_layout,
            },
        )
        return result.build_list(Document)

    @classmethod
    def find_by_data_model(cls, ds: DataSource, data_model: str) -> list["Document"]:
        """Find all documents for a given data model."""
        query = """
            select id, document_name, document_layout, data_model, created_at, updated_at
            from documents
            where data_model = $data_model
        """

        result = ds.native_query(
            query,
            params={
                "data_model": data_model,
            },
        )
        return result.build_list(Document)

    @classmethod
    def delete_by_data_model(cls, ds: DataSource, data_model: str) -> int:
        """Bulk delete all documents for a given data model.

        Args:
            ds: The data source connection
            data_model: The name of the data model

        Returns:
            int: Number of documents deleted
        """
        query = """
            DELETE FROM documents
            WHERE data_model = $data_model
            RETURNING id;
        """

        result = ds.native_query(
            query,
            params={
                "data_model": data_model,
            },
        )

        # Count the number of deleted documents
        deleted_count = len([row for row in result.iter_as_tuples()])
        return deleted_count

    @classmethod
    def create(
        cls,
        ds: DataSource,
        document_layout: str,
        data_model: str,
        document_name: str | None = None,
        extracted_content: dict[str, Any] | None = None,
        translated_content: dict[str, Any] | None = None,
    ) -> "Document":
        """Create a new document with a random UUID and insert it into the database."""
        doc = cls(
            id=str(uuid.uuid4()),
            document_name=document_name,
            document_layout=document_layout,
            data_model=data_model,
            extracted_content=extracted_content,
            translated_content=translated_content,
        )
        doc.insert(ds)
        return doc

    def to_json(self) -> dict[str, Any]:
        """Return a JSON representation of the document without internal fields."""
        return self.model_dump(
            exclude={
                "extracted_content": True,
                "translated_content": True,
                "created_at": True,
                "updated_at": True,
            }
        )
