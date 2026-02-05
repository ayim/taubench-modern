"""Tests for Schema operations via SemanticDataModel API endpoints.

Schemas are managed atomically through the parent SDM endpoints (POST, GET, PUT, DELETE).
This follows the existing pattern for SDM sub-resources like tables and relationships.

These tests do not duplicate foundational validation unit tests.
"""

from __future__ import annotations

from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_platform.core.payloads.semantic_data_model_payloads import (
    SetSemanticDataModelPayload,
)
from agent_platform.core.semantic_data_model import SemanticDataModel
from agent_platform.core.semantic_data_model.schemas import (
    DocumentExtraction,
    Schema,
    Transformation,
    Validation,
)
from agent_platform.core.semantic_data_model.types import LogicalTable
from agent_platform.core.user import User
from agent_platform.server.api.private_v2 import semantic_data_models_router
from agent_platform.server.auth.handlers import auth_user
from agent_platform.server.error_handlers import add_exception_handlers
from agent_platform.server.storage import PostgresStorage, SQLiteStorage
from agent_platform.server.storage.option import StorageService


@pytest.fixture
async def stub_user(storage: SQLiteStorage | PostgresStorage) -> User:
    """Create a stub user for authentication."""
    user, _ = await storage.get_or_create_user("tenant:test:user:sdm-schema-test")
    return user


@pytest.fixture
def fastapi_app_sdm(storage: SQLiteStorage | PostgresStorage, stub_user: User) -> FastAPI:
    """FastAPI app configured with semantic data model router."""
    StorageService.reset()
    StorageService.set_for_testing(storage)

    app = FastAPI()
    app.include_router(
        semantic_data_models_router,
        prefix="/api/v2/semantic-data-models",
        tags=["semantic-data-models"],
    )
    app.dependency_overrides[auth_user] = lambda: stub_user
    add_exception_handlers(app)
    return app


@pytest.fixture
def client(fastapi_app_sdm: FastAPI) -> TestClient:
    """Test client for the FastAPI app."""
    return TestClient(fastapi_app_sdm)


def _minimal_table() -> LogicalTable:
    """Create a minimal valid table for API payloads.

    The SDM API requires at least one table to be present.
    """
    return cast(
        LogicalTable,
        {
            "name": "test_table",
            "base_table": {"table": "test_physical_table"},
            "dimensions": [
                {
                    "name": "id",
                    "expr": "id",
                    "data_type": "string",
                }
            ],
        },
    )


def _make_schema(
    name: str = "TestSchema",
    description: str = "Test schema description",
    json_schema: dict[str, Any] | None = None,
    validations: list[Validation] | None = None,
    transformations: list[Transformation] | None = None,
    document_extraction: DocumentExtraction | None = None,
) -> Schema:
    """Helper to create a Schema instance."""
    return Schema(
        name=name,
        description=description,
        json_schema=json_schema or {"type": "object"},
        validations=validations or [],
        transformations=transformations or [],
        document_extraction=document_extraction,
    )


def _make_sdm_payload(
    name: str = "Test Model",
    schemas: list[Schema] | None = None,
    thread_id: str = "test-thread-id",
) -> dict[str, Any]:
    """Helper to create an SDM payload dict for API requests.

    Uses SetSemanticDataModelPayload internally.
    Includes a minimal valid table since the API requires tables to be non-empty.
    """
    sdm = SemanticDataModel(
        name=name,
        tables=[_minimal_table()],
        schemas=schemas,
    )
    return SetSemanticDataModelPayload(semantic_model=sdm, thread_id=thread_id).model_dump()


def _make_sdm_with_table_and_schemas(
    name: str,
    schemas: list[Schema] | None = None,
) -> SemanticDataModel:
    """Create a SemanticDataModel with one table and optional schemas for storage."""
    return SemanticDataModel(
        name=name,
        tables=[_minimal_table()],
        schemas=schemas,
    )


async def _get_sdm_from_storage(storage: SQLiteStorage | PostgresStorage, sdm_id: str) -> SemanticDataModel:
    """Retrieve SDM from storage and reconstruct as SemanticDataModel instance."""
    stored_dict = await storage.get_semantic_data_model(sdm_id)
    return SemanticDataModel.model_validate(stored_dict)


class TestCreateSdmWithSchemas:
    """Tests for creating SDMs with schemas via POST /api/v2/semantic-data-models/"""

    @pytest.mark.asyncio
    async def test_create_sdm_with_single_schema(self, storage: SQLiteStorage | PostgresStorage, client: TestClient):
        """Can create an SDM containing a single schema."""
        payload = _make_sdm_payload(
            name="Invoice Model",
            schemas=[
                _make_schema(
                    name="Invoice",
                    description="Invoice document schema",
                    json_schema={
                        "type": "object",
                        "properties": {
                            "invoice_number": {"type": "string"},
                            "amount": {"type": "number"},
                        },
                    },
                )
            ],
        )

        response = client.post("/api/v2/semantic-data-models/", json=payload)
        assert response.status_code == 200, f"Failed: {response.text}"

        sdm_id = response.json()["semantic_data_model_id"]
        sdm = await _get_sdm_from_storage(storage, sdm_id)
        assert sdm.schemas is not None
        assert len(sdm.schemas) == 1
        assert sdm.schemas[0].name == "Invoice"

    @pytest.mark.asyncio
    async def test_create_sdm_with_multiple_schemas(self, storage: SQLiteStorage | PostgresStorage, client: TestClient):
        """Can create an SDM with multiple schemas."""
        payload = _make_sdm_payload(
            name="Order Model",
            schemas=[
                _make_schema(name="Order", description="Order schema"),
                _make_schema(name="LineItem", description="Line item schema"),
                _make_schema(name="Customer", description="Customer schema"),
            ],
        )

        response = client.post("/api/v2/semantic-data-models/", json=payload)
        assert response.status_code == 200, f"Failed: {response.text}"

        sdm_id = response.json()["semantic_data_model_id"]
        sdm = await _get_sdm_from_storage(storage, sdm_id)
        assert sdm.schemas is not None
        assert len(sdm.schemas) == 3
        schema_names = {s.name for s in sdm.schemas}
        assert schema_names == {"Order", "LineItem", "Customer"}

    @pytest.mark.asyncio
    async def test_create_sdm_with_no_schemas(self, storage: SQLiteStorage | PostgresStorage, client: TestClient):
        """Can create an SDM without any schemas (schemas omitted)."""
        payload = _make_sdm_payload(name="Empty Model")

        response = client.post("/api/v2/semantic-data-models/", json=payload)
        assert response.status_code == 200, f"Failed: {response.text}"

        sdm_id = response.json()["semantic_data_model_id"]
        sdm = await _get_sdm_from_storage(storage, sdm_id)
        assert sdm.schemas is None or sdm.schemas == []


class TestGetSdmWithSchemas:
    """Tests for retrieving SDMs with schemas via GET /api/v2/semantic-data-models/{id}"""

    @pytest.mark.asyncio
    async def test_get_sdm_with_null_schemas(self, storage: SQLiteStorage | PostgresStorage, client: TestClient):
        """GET returns SDM correctly when schemas is null/omitted."""
        sdm = SemanticDataModel(name="Test Model", tables=[])
        sdm_id = await storage.set_semantic_data_model(
            semantic_data_model_id=None,
            semantic_model=sdm,
            data_connection_ids=[],
            file_references=[],
        )

        response = client.get(f"/api/v2/semantic-data-models/{sdm_id}")
        assert response.status_code == 200, f"Failed: {response.text}"

    @pytest.mark.asyncio
    async def test_get_sdm_schema_with_all_fields(self, storage: SQLiteStorage | PostgresStorage, client: TestClient):
        """GET returns schema with validations, transformations, and document_extraction."""
        sdm = SemanticDataModel(
            name="Full Model",
            tables=[],
            schemas=[
                Schema(
                    name="FullSchema",
                    description="Complete schema with all optional fields",
                    json_schema={
                        "type": "object",
                        "properties": {"total": {"type": "number"}},
                    },
                    validations=[
                        Validation(
                            name="positive",
                            description="Total must be positive",
                            jq_expression=".total > 0",
                        )
                    ],
                    transformations=[
                        Transformation(
                            target_schema_name="Summary",
                            jq_expression="{total: .total}",
                        )
                    ],
                    document_extraction=DocumentExtraction(
                        system_prompt="Extract invoice data",
                        configuration={"engine": "reducto"},
                    ),
                )
            ],
        )
        sdm_id = await storage.set_semantic_data_model(
            semantic_data_model_id=None,
            semantic_model=sdm,
            data_connection_ids=[],
            file_references=[],
        )

        response = client.get(f"/api/v2/semantic-data-models/{sdm_id}")
        assert response.status_code == 200, f"Failed: {response.text}"

        schema = response.json()["schemas"][0]
        assert len(schema["validations"]) == 1
        assert schema["validations"][0]["name"] == "positive"
        assert len(schema["transformations"]) == 1
        assert schema["transformations"][0]["target_schema_name"] == "Summary"
        assert schema["document_extraction"]["system_prompt"] == "Extract invoice data"


class TestUpdateSdmSchemas:
    """Tests for updating SDM schemas via PUT /api/v2/semantic-data-models/{id}"""

    @pytest.mark.asyncio
    async def test_add_schema_to_existing_sdm(self, storage: SQLiteStorage | PostgresStorage, client: TestClient):
        """Can add a new schema to an existing SDM."""
        sdm = _make_sdm_with_table_and_schemas(
            name="Test Model",
            schemas=[
                _make_schema(
                    name="Existing",
                    description="Existing schema",
                )
            ],
        )
        sdm_id = await storage.set_semantic_data_model(
            semantic_data_model_id=None,
            semantic_model=sdm,
            data_connection_ids=[],
            file_references=[],
        )

        payload = _make_sdm_payload(
            name="Test Model",
            schemas=[
                _make_schema(name="Existing", description="Existing schema"),
                _make_schema(name="NewSchema", description="Newly added schema"),
            ],
        )
        response = client.put(f"/api/v2/semantic-data-models/{sdm_id}", json=payload)
        assert response.status_code == 200, f"Failed: {response.text}"

        sdm = await _get_sdm_from_storage(storage, sdm_id)
        assert sdm.schemas is not None
        assert len(sdm.schemas) == 2
        schema_names = {s.name for s in sdm.schemas}
        assert schema_names == {"Existing", "NewSchema"}

    @pytest.mark.asyncio
    async def test_remove_schema_from_sdm(self, storage: SQLiteStorage | PostgresStorage, client: TestClient):
        """Can remove a schema by omitting it from the update payload."""
        sdm = _make_sdm_with_table_and_schemas(
            name="Test Model",
            schemas=[
                _make_schema(name="Keep", description="To keep"),
                _make_schema(name="Remove", description="To remove"),
            ],
        )
        sdm_id = await storage.set_semantic_data_model(
            semantic_data_model_id=None,
            semantic_model=sdm,
            data_connection_ids=[],
            file_references=[],
        )

        payload = _make_sdm_payload(
            name="Test Model",
            schemas=[
                _make_schema(name="Keep", description="To keep"),
            ],
        )
        response = client.put(f"/api/v2/semantic-data-models/{sdm_id}", json=payload)
        assert response.status_code == 200, f"Failed: {response.text}"

        sdm = await _get_sdm_from_storage(storage, sdm_id)
        assert sdm.schemas is not None
        assert len(sdm.schemas) == 1
        assert sdm.schemas[0].name == "Keep"

    @pytest.mark.asyncio
    async def test_update_schema_content(self, storage: SQLiteStorage | PostgresStorage, client: TestClient):
        """Can update a schema's description, json_schema, validations, etc."""
        sdm = _make_sdm_with_table_and_schemas(
            name="Test Model",
            schemas=[
                _make_schema(
                    name="Invoice",
                    description="Old description",
                )
            ],
        )
        sdm_id = await storage.set_semantic_data_model(
            semantic_data_model_id=None,
            semantic_model=sdm,
            data_connection_ids=[],
            file_references=[],
        )

        payload = _make_sdm_payload(
            name="Test Model",
            schemas=[
                _make_schema(
                    name="Invoice",
                    description="Updated description",
                    json_schema={
                        "type": "object",
                        "properties": {"id": {"type": "string"}},
                    },
                    validations=[
                        Validation(
                            name="has_id",
                            description="Must have id",
                            jq_expression=".id != null",
                        )
                    ],
                )
            ],
        )
        response = client.put(f"/api/v2/semantic-data-models/{sdm_id}", json=payload)
        assert response.status_code == 200, f"Failed: {response.text}"

        sdm = await _get_sdm_from_storage(storage, sdm_id)
        assert sdm.schemas is not None
        assert sdm.schemas[0].description == "Updated description"
        assert len(sdm.schemas[0].validations) == 1

    @pytest.mark.asyncio
    async def test_rename_schema(self, storage: SQLiteStorage | PostgresStorage, client: TestClient):
        """Can rename a schema by providing new name in update."""
        sdm = _make_sdm_with_table_and_schemas(
            name="Test Model",
            schemas=[
                _make_schema(
                    name="OldName",
                    description="Schema description",
                )
            ],
        )
        sdm_id = await storage.set_semantic_data_model(
            semantic_data_model_id=None,
            semantic_model=sdm,
            data_connection_ids=[],
            file_references=[],
        )

        payload = _make_sdm_payload(
            name="Test Model",
            schemas=[
                _make_schema(name="NewName", description="Schema description"),
            ],
        )
        response = client.put(f"/api/v2/semantic-data-models/{sdm_id}", json=payload)
        assert response.status_code == 200, f"Failed: {response.text}"

        sdm = await _get_sdm_from_storage(storage, sdm_id)
        assert sdm.schemas is not None
        assert sdm.schemas[0].name == "NewName"

    @pytest.mark.asyncio
    async def test_clear_all_schemas(self, storage: SQLiteStorage | PostgresStorage, client: TestClient):
        """Can remove all schemas by setting empty array."""
        sdm = _make_sdm_with_table_and_schemas(
            name="Test Model",
            schemas=[
                _make_schema(name="A", description="Schema A"),
                _make_schema(name="B", description="Schema B"),
            ],
        )
        sdm_id = await storage.set_semantic_data_model(
            semantic_data_model_id=None,
            semantic_model=sdm,
            data_connection_ids=[],
            file_references=[],
        )

        payload = _make_sdm_payload(
            name="Test Model",
            schemas=[],
        )
        response = client.put(f"/api/v2/semantic-data-models/{sdm_id}", json=payload)
        assert response.status_code == 200, f"Failed: {response.text}"

        sdm = await _get_sdm_from_storage(storage, sdm_id)
        assert sdm.schemas == []


class TestDeleteSdmWithSchemas:
    """Tests for deleting SDMs via DELETE /api/v2/semantic-data-models/{id}"""

    @pytest.mark.asyncio
    async def test_delete_sdm_removes_schemas(self, storage: SQLiteStorage | PostgresStorage, client: TestClient):
        """Deleting SDM removes the SDM and all associated schemas."""
        sdm = _make_sdm_with_table_and_schemas(
            name="Test Model",
            schemas=[
                _make_schema(name="Schema1", description="Schema 1"),
                _make_schema(name="Schema2", description="Schema 2"),
            ],
        )
        sdm_id = await storage.set_semantic_data_model(
            semantic_data_model_id=None,
            semantic_model=sdm,
            data_connection_ids=[],
            file_references=[],
        )

        response = client.delete(f"/api/v2/semantic-data-models/{sdm_id}")
        assert response.status_code == 200, f"Failed: {response.text}"

        from agent_platform.core.errors import PlatformHTTPError

        with pytest.raises(PlatformHTTPError):
            await storage.get_semantic_data_model(sdm_id)
