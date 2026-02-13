"""Unit tests for _DocumentTools.extract_document method."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest


def _create_schema_registry(schemas=None):
    """Helper to create a SchemaRegistry with optional pre-populated schemas."""
    from agent_platform.server.kernel.documents import ResolvedSchema, SchemaRegistry

    class _TestSchemaRegistry(SchemaRegistry):
        def __init__(self):
            self._schemas: dict[str, ResolvedSchema] = {}

        def get(self, name: str) -> ResolvedSchema:
            return self._schemas[name.lower()]

        def list_names(self) -> list[str]:
            return [s.name for s in self._schemas.values()]

        def add(self, name: str, schema: ResolvedSchema) -> None:
            self._schemas[name.lower()] = schema

    registry = _TestSchemaRegistry()
    if schemas:
        for name, schema in schemas.items():
            registry.add(name, schema)
    return registry


def _create_document_tools(
    storage: Mock | None = None,
    kernel: Mock | None = None,
    user: Mock | None = None,
    tid: str = "test-thread-id",
    schema_registry=None,
):
    """Helper to create a _DocumentTools instance with mocked dependencies."""
    from agent_platform.server.kernel.documents import _DocumentTools

    if user is None:
        user = MagicMock()
        user.user_id = "test-user-id"

    if kernel is None:
        kernel = MagicMock()
        kernel.thread = MagicMock()
        kernel.thread.thread_id = tid
        kernel.agent = MagicMock()
        kernel.agent.agent_id = "test-agent-id"
        kernel.ctx = MagicMock()

    if storage is None:
        storage = AsyncMock()

    if schema_registry is None:
        schema_registry = _create_schema_registry()

    return _DocumentTools(
        user=user,
        tid=tid,
        storage=storage,
        kernel=kernel,
        schema_registry=schema_registry,
    )


@pytest.mark.asyncio
async def test_extract_document_empty_schema_raises():
    """Test that empty extraction_schema raises ValueError."""
    tools = _create_document_tools()

    with pytest.raises(ValueError, match="schema_name is required"):
        await tools.extract_document(
            schema_name="",
            file_name="test.pdf",
        )


@pytest.mark.asyncio
async def test_extract_document_invalid_reducto_settings_raises():
    """Test that invalid Reducto settings raises ValueError."""
    from agent_platform.server.kernel.documents import ResolvedSchema

    storage = AsyncMock()
    mock_integration = MagicMock()
    mock_integration.settings = "not_reducto_settings"  # Wrong type
    storage.get_integration_by_kind = AsyncMock(return_value=mock_integration)

    registry = _create_schema_registry(
        {
            "test_schema_20260211T120000": ResolvedSchema(
                name="test_schema_20260211T120000",
                json_schema={"type": "object", "properties": {"name": {"type": "string"}}},
                source="generated",
            ),
        }
    )

    tools = _create_document_tools(storage=storage, schema_registry=registry)

    with pytest.raises(ValueError, match="invalid settings"):
        await tools.extract_document(
            schema_name="test_schema_20260211T120000",
            file_name="test.pdf",
        )


@pytest.mark.parametrize("system_prompt", ["Extract invoice details", None])
@pytest.mark.asyncio
async def test_extract_document(system_prompt: str | None):
    """Test extraction with a dict schema passes through correctly."""
    from agent_platform.core.integrations.settings.reducto import ReductoSettings
    from agent_platform.core.utils import SecretString
    from agent_platform.server.kernel.documents import ResolvedSchema

    storage = AsyncMock()
    mock_integration = MagicMock()
    mock_integration.settings = ReductoSettings(endpoint="https://api.reducto.ai", api_key=SecretString("test-api-key"))
    storage.get_integration_by_kind = AsyncMock(return_value=mock_integration)

    registry = _create_schema_registry(
        {
            "test_schema_20260211T120000": ResolvedSchema(
                name="test_schema_20260211T120000",
                json_schema={"type": "object", "properties": {"data": {"type": "string"}}},
                source="generated",
            ),
        }
    )

    tools = _create_document_tools(storage=storage, schema_registry=registry)

    mock_doc = MagicMock()
    mock_extract_result = MagicMock()
    mock_extract_result.model_dump.return_value = {"data": "extracted"}

    with (
        patch("agent_platform.server.file_manager.FileManagerService") as mock_file_manager_class,
        patch("agent_platform.server.document_intelligence.DirectKernelTransport") as mock_transport_class,
        patch("sema4ai_docint.build_di_service") as mock_build_di,
    ):
        mock_file_manager_class.get_instance.return_value = MagicMock()
        mock_transport_class.return_value = MagicMock()

        mock_di_service = MagicMock()
        mock_di_service.document_v2 = MagicMock()
        mock_di_service.document_v2.new_document = AsyncMock(return_value=mock_doc)
        mock_di_service.document_v2.extract_document = AsyncMock(return_value=mock_extract_result)
        mock_di_service.__aenter__ = AsyncMock(return_value=mock_di_service)
        mock_di_service.__aexit__ = AsyncMock(return_value=None)
        mock_build_di.return_value = mock_di_service

        result = await tools.extract_document(
            schema_name="test_schema_20260211T120000",
            file_name="document.pdf",
            start_page=1,
            end_page=5,
            system_prompt=system_prompt,
        )

        assert result == {"data": "extracted"}
        call_kwargs = mock_di_service.document_v2.extract_document.call_args[1]
        assert call_kwargs["start_page"] == 1
        assert call_kwargs["end_page"] == 5
        assert call_kwargs["prompt"] == system_prompt
        assert call_kwargs["extraction_config"] is None


def _make_sdm_info(sdm):
    """Helper to create a SemanticDataModelInfo-like dict."""
    return {
        "semantic_data_model": sdm,
        "semantic_data_model_id": "sdm-1",
        "agent_ids": {"test-agent-id"},
        "thread_ids": {"test-thread-id"},
        "updated_at": "2025-01-01T00:00:00Z",
    }


def _make_schema(name, *, document_extraction=None, json_schema=None):
    """Helper to create a Schema object for testing."""
    from agent_platform.core.semantic_data_model.schemas import Schema

    return Schema(
        name=name,
        description=f"Test schema {name}",
        json_schema=json_schema or {"type": "object", "properties": {"field": {"type": "string"}}},
        validations=[],
        transformations=[],
        document_extraction=document_extraction,
    )


def _make_sdm_with_schemas(schemas):
    """Helper to create a mock SDM with schemas."""
    sdm = MagicMock()
    sdm.schemas = schemas
    return sdm


@pytest.mark.asyncio
async def test_extract_document_str_schema_found():
    """Test extraction with a string schema name that is found via registry."""
    from agent_platform.core.integrations.settings.reducto import ReductoSettings
    from agent_platform.core.utils import SecretString
    from agent_platform.server.kernel.documents import ResolvedSchema

    storage = AsyncMock()
    mock_integration = MagicMock()
    mock_integration.settings = ReductoSettings(endpoint="https://api.reducto.ai", api_key=SecretString("test-api-key"))
    storage.get_integration_by_kind = AsyncMock(return_value=mock_integration)

    test_json_schema = {"type": "object", "properties": {"field": {"type": "string"}}}
    registry = _create_schema_registry(
        {
            "invoice_schema": ResolvedSchema(
                name="invoice_schema",
                json_schema=test_json_schema,
                system_prompt="Use this prompt for extraction",
                extraction_config={"advanced_options": {"some_setting": True}},
                source="sdm",
                extraction_enabled=True,
            ),
        }
    )

    tools = _create_document_tools(storage=storage, schema_registry=registry)

    mock_doc = MagicMock()
    mock_extract_result = MagicMock()
    mock_extract_result.model_dump.return_value = {"data": "extracted"}

    with (
        patch("agent_platform.server.file_manager.FileManagerService") as mock_file_manager_class,
        patch("agent_platform.server.document_intelligence.DirectKernelTransport") as mock_transport_class,
        patch("sema4ai_docint.build_di_service") as mock_build_di,
    ):
        mock_file_manager_class.get_instance.return_value = MagicMock()
        mock_transport_class.return_value = MagicMock()

        mock_di_service = MagicMock()
        mock_di_service.document_v2 = MagicMock()
        mock_di_service.document_v2.new_document = AsyncMock(return_value=mock_doc)
        mock_di_service.document_v2.extract_document = AsyncMock(return_value=mock_extract_result)
        mock_di_service.__aenter__ = AsyncMock(return_value=mock_di_service)
        mock_di_service.__aexit__ = AsyncMock(return_value=None)
        mock_build_di.return_value = mock_di_service

        result = await tools.extract_document(
            schema_name="invoice_schema",
            file_name="document.pdf",
            system_prompt="this should be overridden",
        )

        assert result == {"data": "extracted"}
        call_kwargs = mock_di_service.document_v2.extract_document.call_args[1]
        # system_prompt from Schema should override the function argument
        assert call_kwargs["prompt"] == "Use this prompt for extraction"
        # extraction_config from Schema should be passed through
        assert call_kwargs["extraction_config"] == {"advanced_options": {"some_setting": True}}
        # json_schema from Schema should be used
        call_args = mock_di_service.document_v2.extract_document.call_args[0]
        assert call_args[1] == test_json_schema


@pytest.mark.asyncio
async def test_extract_document_str_schema_not_found():
    """Test that a missing schema name raises ValueError with available names."""
    from agent_platform.server.kernel.documents import ResolvedSchema

    registry = _create_schema_registry(
        {
            "existing_schema": ResolvedSchema(
                name="existing_schema",
                json_schema={"type": "object", "properties": {"field": {"type": "string"}}},
                source="sdm",
                extraction_enabled=True,
            ),
        }
    )

    tools = _create_document_tools(schema_registry=registry)

    with pytest.raises(ValueError, match="nonexistent_schema") as exc_info:
        await tools.extract_document(
            schema_name="nonexistent_schema",
            file_name="test.pdf",
        )

    assert "existing_schema" in str(exc_info.value)
    assert "generate_schema" in str(exc_info.value)


@pytest.mark.asyncio
async def test_extract_document_str_schema_no_document_extraction():
    """Test that a schema without document_extraction raises ValueError."""
    from agent_platform.server.kernel.documents import ResolvedSchema

    registry = _create_schema_registry(
        {
            "invoice_schema": ResolvedSchema(
                name="invoice_schema",
                json_schema={"type": "object", "properties": {"field": {"type": "string"}}},
                source="sdm",
                extraction_enabled=False,
            ),
        }
    )

    tools = _create_document_tools(schema_registry=registry)

    with pytest.raises(ValueError, match="not enabled") as exc_info:
        await tools.extract_document(
            schema_name="invoice_schema",
            file_name="test.pdf",
        )

    assert "invoice_schema" in str(exc_info.value)


@pytest.mark.asyncio
async def test_extract_document_str_schema_empty_system_prompt_not_overridden():
    """Test that an empty system_prompt on the schema does not override the function argument."""
    from agent_platform.core.integrations.settings.reducto import ReductoSettings
    from agent_platform.core.utils import SecretString
    from agent_platform.server.kernel.documents import ResolvedSchema

    storage = AsyncMock()
    mock_integration = MagicMock()
    mock_integration.settings = ReductoSettings(endpoint="https://api.reducto.ai", api_key=SecretString("test-api-key"))
    storage.get_integration_by_kind = AsyncMock(return_value=mock_integration)

    registry = _create_schema_registry(
        {
            "invoice_schema": ResolvedSchema(
                name="invoice_schema",
                json_schema={"type": "object", "properties": {"field": {"type": "string"}}},
                system_prompt="",
                extraction_config={},
                source="sdm",
                extraction_enabled=True,
            ),
        }
    )

    tools = _create_document_tools(storage=storage, schema_registry=registry)

    mock_doc = MagicMock()
    mock_extract_result = MagicMock()
    mock_extract_result.model_dump.return_value = {"data": "extracted"}

    with (
        patch("agent_platform.server.file_manager.FileManagerService") as mock_file_manager_class,
        patch("agent_platform.server.document_intelligence.DirectKernelTransport") as mock_transport_class,
        patch("sema4ai_docint.build_di_service") as mock_build_di,
    ):
        mock_file_manager_class.get_instance.return_value = MagicMock()
        mock_transport_class.return_value = MagicMock()

        mock_di_service = MagicMock()
        mock_di_service.document_v2 = MagicMock()
        mock_di_service.document_v2.new_document = AsyncMock(return_value=mock_doc)
        mock_di_service.document_v2.extract_document = AsyncMock(return_value=mock_extract_result)
        mock_di_service.__aenter__ = AsyncMock(return_value=mock_di_service)
        mock_di_service.__aexit__ = AsyncMock(return_value=None)
        mock_build_di.return_value = mock_di_service

        result = await tools.extract_document(
            schema_name="invoice_schema",
            file_name="document.pdf",
            system_prompt="caller provided prompt",
        )

        assert result == {"data": "extracted"}
        call_kwargs = mock_di_service.document_v2.extract_document.call_args[1]
        # Empty schema system_prompt should NOT override the function argument
        assert call_kwargs["prompt"] == "caller provided prompt"
        # Empty configuration should result in None extraction_config
        assert call_kwargs["extraction_config"] is None


@pytest.mark.asyncio
async def test_generate_schema_returns_named_schema():
    """Test that generate_schema returns a dict with schema_name and json_schema."""
    from agent_platform.core.integrations.settings.reducto import ReductoSettings
    from agent_platform.core.utils import SecretString

    storage = AsyncMock()
    mock_integration = MagicMock()
    mock_integration.settings = ReductoSettings(endpoint="https://api.reducto.ai", api_key=SecretString("test-api-key"))
    storage.get_integration_by_kind = AsyncMock(return_value=mock_integration)

    registry = _create_schema_registry()
    tools = _create_document_tools(storage=storage, schema_registry=registry)

    raw_schema = {
        "title": "Invoice",
        "type": "object",
        "properties": {"amount": {"type": "number"}},
    }

    with (
        patch("agent_platform.server.file_manager.FileManagerService") as mock_file_manager_class,
        patch("agent_platform.server.document_intelligence.DirectKernelTransport") as mock_transport_class,
        patch("sema4ai_docint.build_di_service") as mock_build_di,
        patch.object(tools, "_generate_schema_name", new_callable=AsyncMock, return_value="invoice_20260211T120000"),
    ):
        mock_file_manager_class.get_instance.return_value = MagicMock()
        mock_transport_class.return_value = MagicMock()

        mock_doc = MagicMock()
        mock_di_service = MagicMock()
        mock_di_service.document_v2 = MagicMock()
        mock_di_service.document_v2.new_document = AsyncMock(return_value=mock_doc)
        mock_di_service.document_v2.generate_schema = AsyncMock(return_value=raw_schema)
        mock_di_service.__aenter__ = AsyncMock(return_value=mock_di_service)
        mock_di_service.__aexit__ = AsyncMock(return_value=None)
        mock_build_di.return_value = mock_di_service

        result = await tools.generate_schema(
            file_name="invoice.pdf",
            user_prompt="Extract invoice fields",
        )

        assert result["schema_name"] == "invoice_20260211T120000"
        # Schema should be cached in the registry for later use by extract_document
        resolved = registry.get("invoice_20260211T120000")
        assert resolved.json_schema == raw_schema
        assert resolved.source == "generated"


@pytest.mark.asyncio
async def test_generate_schema_name_fallback():
    """Test that generate_schema name falls back to filename stem when LLM fails."""
    tools = _create_document_tools()

    # _generate_schema_name should fall back gracefully when LLM is unavailable
    # (the kernel mock won't have a real platform)
    name = await tools._generate_schema_name("my_report.pdf")

    assert name.startswith("my_report_")
    assert len(name) > len("my_report_")


@pytest.mark.asyncio
async def test_collect_sdm_schemas_merges_with_generated():
    """Test that _collect_sdm_schemas merges SDM schemas with existing generated schemas."""
    from agent_platform.core.semantic_data_model.schemas import DocumentExtraction
    from agent_platform.server.kernel.documents import AgentServerDocumentsInterface, ResolvedSchema

    interface = AgentServerDocumentsInterface()

    # Mock kernel via attach_kernel (UsesKernelMixin)
    mock_kernel = MagicMock()
    mock_kernel.agent = MagicMock()
    mock_kernel.agent.agent_id = "test-agent-id"
    mock_kernel.thread_state = MagicMock()
    mock_kernel.thread_state.thread_id = "test-thread-id"
    interface.attach_kernel(mock_kernel)

    # Pre-populate a generated schema
    interface.add(
        "generated_one",
        ResolvedSchema(name="generated_one", json_schema={"type": "object"}, source="generated"),
    )

    # Create SDM schemas
    doc_extraction = DocumentExtraction(system_prompt="Extract it", configuration={"key": "val"})
    sdm_schema = _make_schema("sdm_schema", document_extraction=doc_extraction)
    no_extraction_schema = _make_schema("no_extract")
    sdm = _make_sdm_with_schemas([sdm_schema, no_extraction_schema])

    storage = AsyncMock()
    storage.list_semantic_data_models = AsyncMock(return_value=[_make_sdm_info(sdm)])

    await interface._collect_sdm_schemas(storage)

    # SDM schema with extraction
    resolved_sdm = interface.get("sdm_schema")
    assert resolved_sdm.source == "sdm"
    assert resolved_sdm.extraction_enabled is True
    assert resolved_sdm.system_prompt == "Extract it"
    assert resolved_sdm.extraction_config == {"key": "val"}

    # SDM schema without extraction
    resolved_no_ext = interface.get("no_extract")
    assert resolved_no_ext.source == "sdm"
    assert resolved_no_ext.extraction_enabled is False

    # Generated schema is preserved
    resolved_gen = interface.get("generated_one")
    assert resolved_gen.source == "generated"

    # All names listed
    names = interface.list_names()
    assert len(names) == 3


@pytest.mark.asyncio
async def test_collect_sdm_schemas_generated_takes_priority():
    """Test that generated schemas take priority over SDM schemas on name collision."""
    from agent_platform.core.semantic_data_model.schemas import DocumentExtraction
    from agent_platform.server.kernel.documents import AgentServerDocumentsInterface, ResolvedSchema

    interface = AgentServerDocumentsInterface()

    mock_kernel = MagicMock()
    mock_kernel.agent = MagicMock()
    mock_kernel.agent.agent_id = "test-agent-id"
    mock_kernel.thread_state = MagicMock()
    mock_kernel.thread_state.thread_id = "test-thread-id"
    interface.attach_kernel(mock_kernel)

    # Pre-populate a generated schema with the same name as an SDM schema
    generated_json = {"type": "object", "properties": {"gen": {"type": "string"}}}
    interface.add(
        "collision",
        ResolvedSchema(name="collision", json_schema=generated_json, source="generated"),
    )

    doc_extraction = DocumentExtraction(system_prompt="SDM prompt", configuration={})
    sdm_schema = _make_schema(
        "collision",
        document_extraction=doc_extraction,
        json_schema={"type": "object", "properties": {"sdm": {"type": "string"}}},
    )
    sdm = _make_sdm_with_schemas([sdm_schema])

    storage = AsyncMock()
    storage.list_semantic_data_models = AsyncMock(return_value=[_make_sdm_info(sdm)])

    await interface._collect_sdm_schemas(storage)

    # Generated schema should win
    resolved = interface.get("collision")
    assert resolved.source == "generated"
    assert resolved.json_schema == generated_json
