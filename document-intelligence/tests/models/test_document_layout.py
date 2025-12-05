from sema4ai.data import DataSource

from sema4ai_docint.models import DataModel, DocumentLayout


def test_crud(postgres_datasource: "DataSource"):
    """Test that we can interact with a DocumentLayout model."""

    # Create a data model first since document layout depends on it
    data_model = DataModel(
        name="test-data-model",
        description="A test data model",
        model_schema={},
    )
    data_model.insert(postgres_datasource)

    # Schema does not exist
    existing_schema = DocumentLayout.find_by_name(
        postgres_datasource, "test-data-model", "does-not-exist"
    )
    assert existing_schema is None

    extraction_schema = {"fields": ["field1", "field2"]}
    translation_schema = {"mappings": {"field1": "mapped1"}}

    document_layout = DocumentLayout(
        name="test-document-layout",
        data_model="test-data-model",
        extraction_schema=extraction_schema,
        translation_schema=translation_schema,
        summary="Test summary",
    )

    # Create the schema in the database
    document_layout.insert(postgres_datasource)

    # Read it back from the database
    actual = DocumentLayout.find_by_name(
        postgres_datasource, document_layout.data_model, document_layout.name
    )
    assert actual is not None
    assert actual.name == document_layout.name
    assert actual.data_model == document_layout.data_model
    assert actual.extraction_schema == extraction_schema
    assert actual.translation_schema == translation_schema
    assert actual.summary == document_layout.summary

    # Update the schema
    new_extraction_schema = {"fields": ["field3", "field4"]}
    new_translation_schema = {"mappings": {"field3": "mapped3"}}
    document_layout.extraction_schema = new_extraction_schema
    document_layout.translation_schema = new_translation_schema
    document_layout.summary = "Updated summary"
    document_layout.update(postgres_datasource)

    # Read it back from the database
    new_actual = DocumentLayout.find_by_name(
        postgres_datasource, document_layout.data_model, document_layout.name
    )
    assert new_actual is not None
    assert new_actual.extraction_schema == new_extraction_schema
    assert new_actual.translation_schema == new_translation_schema
    assert new_actual.summary == "Updated summary"

    # Delete the schema
    was_deleted = document_layout.delete(postgres_datasource)
    assert was_deleted is True

    # Try to read it back, verify it's deleted
    actual = DocumentLayout.find_by_name(
        postgres_datasource, document_layout.data_model, document_layout.name
    )
    assert actual is None


def test_find_all(postgres_datasource: "DataSource"):
    """Test that we can find all schemas."""
    document_layouts = DocumentLayout.find_all(postgres_datasource)
    assert len(document_layouts) == 0

    # Create a use case first
    data_model = DataModel(
        name="test-data-model",
        description="A test data model",
        model_schema={},
    )
    data_model.insert(postgres_datasource)

    # Create schemas
    document_layout1 = DocumentLayout(
        name="test-document-layout-1",
        data_model="test-data-model",
        extraction_schema={"fields": ["field1"]},
        translation_schema={"mappings": {"field1": "mapped1"}},
    )
    document_layout2 = DocumentLayout(
        name="test-document-layout-2",
        data_model="test-data-model",
        extraction_schema={"fields": ["field2"]},
        translation_schema={"mappings": {"field2": "mapped2"}},
    )

    document_layout1.insert(postgres_datasource)
    document_layout2.insert(postgres_datasource)

    # Find all schemas
    document_layouts = DocumentLayout.find_all(postgres_datasource)
    assert len(document_layouts) == 2
    assert any(s.name == document_layout1.name for s in document_layouts), (
        "did not find document layout 1"
    )
    assert any(s.name == document_layout2.name for s in document_layouts), (
        "did not find document layout 2"
    )


def test_find_by_name(postgres_datasource: "DataSource"):
    """Test that we can find a schema by name."""
    layout1 = DocumentLayout(
        name="default",
        data_model="model1",
        extraction_schema={"fields": ["field1"]},
        translation_schema={"mappings": {"field1": "mapped1"}},
    )
    layout2 = DocumentLayout(
        name="default",
        data_model="model2",
        extraction_schema={"fields": ["field2"]},
        translation_schema={"mappings": {"field2": "mapped2"}},
    )

    layout1.insert(postgres_datasource)
    layout2.insert(postgres_datasource)

    # Find by name
    actual = DocumentLayout.find_by_name(postgres_datasource, "model1", "default")
    assert actual is not None
    assert actual.name == layout1.name
    assert actual.data_model == layout1.data_model
    assert actual.extraction_schema == layout1.extraction_schema
    assert actual.translation_schema == layout1.translation_schema

    actual = DocumentLayout.find_by_name(postgres_datasource, "model2", "default")
    assert actual is not None
    assert actual.name == layout2.name
    assert actual.data_model == layout2.data_model
    assert actual.extraction_schema == layout2.extraction_schema
    assert actual.translation_schema == layout2.translation_schema

    assert DocumentLayout.find_by_name(postgres_datasource, "model1", "non-existent") is None
    assert DocumentLayout.find_by_name(postgres_datasource, "model3", "default") is None


def test_find_by_use_case(postgres_datasource: "DataSource"):
    """Test that we can find schemas by use case."""
    # Create two use cases
    data_model1 = DataModel(
        name="test-data-model-1",
        description="A test data model 1",
        model_schema={},
    )
    data_model2 = DataModel(
        name="test-data-model-2",
        description="A test data model 2",
        model_schema={},
    )
    data_model1.insert(postgres_datasource)
    data_model2.insert(postgres_datasource)

    # Create schemas for both use cases
    document_layout1 = DocumentLayout(
        name="test-document-layout-1",
        data_model="test-data-model-1",
        extraction_schema={"fields": ["field1"]},
        translation_schema={"mappings": {"field1": "mapped1"}},
    )
    document_layout2 = DocumentLayout(
        name="test-document-layout-2",
        data_model="test-data-model-1",
        extraction_schema={"fields": ["field2"]},
        translation_schema={"mappings": {"field2": "mapped2"}},
    )
    document_layout3 = DocumentLayout(
        name="test-document-layout-3",
        data_model="test-data-model-2",
        extraction_schema={"fields": ["field3"]},
        translation_schema={"mappings": {"field3": "mapped3"}},
    )

    document_layout1.insert(postgres_datasource)
    document_layout2.insert(postgres_datasource)
    document_layout3.insert(postgres_datasource)

    # Find schemas for use case 1
    document_layouts = DocumentLayout.find_by_data_model(postgres_datasource, "test-data-model-1")
    assert len(document_layouts) == 2
    assert any(s.name == document_layout1.name for s in document_layouts), (
        "did not find document layout 1"
    )
    assert any(s.name == document_layout2.name for s in document_layouts), (
        "did not find document layout 2"
    )

    # Find schemas for use case 2
    document_layouts = DocumentLayout.find_by_data_model(postgres_datasource, "test-data-model-2")
    assert len(document_layouts) == 1
    assert document_layouts[0].name == document_layout3.name, "did not find document layout 3"

    # Find schemas for non-existent use case
    document_layouts = DocumentLayout.find_by_data_model(
        postgres_datasource, "non-existent-data-model"
    )
    assert len(document_layouts) == 0


def test_update_translation_schema(postgres_datasource: "DataSource"):
    """Test that we can update the translation schema."""
    # Create a data model first
    data_model = DataModel(
        name="test-data-model",
        description="A test data model",
        model_schema={},
    )
    data_model.insert(postgres_datasource)

    # Create initial document layout with all fields set
    initial_translation_schema = {"mappings": {"field1": "mapped1"}}
    initial_extraction_schema = {"fields": ["field1"]}
    document_layout = DocumentLayout(
        name="test-document-layout",
        data_model="test-data-model",
        extraction_schema=initial_extraction_schema,
        translation_schema=initial_translation_schema,
    )
    document_layout.insert(postgres_datasource)

    # Store initial state for comparison
    initial_layout = DocumentLayout.find_by_name(
        postgres_datasource, data_model.name, document_layout.name
    )
    assert initial_layout is not None
    initial_created_at = initial_layout.created_at
    initial_updated_at = initial_layout.updated_at

    # Update translation schema
    new_translation_schema = {"mappings": {"field1": "new_mapped1", "field2": "mapped2"}}
    document_layout.update_translation_schema(postgres_datasource, new_translation_schema)

    # Read it back and verify
    updated_layout = DocumentLayout.find_by_name(
        postgres_datasource, data_model.name, document_layout.name
    )
    assert updated_layout is not None

    # Verify translation schema was updated
    assert updated_layout.translation_schema == new_translation_schema

    # Verify other fields remain unchanged
    assert updated_layout.name == document_layout.name
    assert updated_layout.data_model == document_layout.data_model
    assert updated_layout.extraction_schema == initial_extraction_schema
    assert updated_layout.created_at == initial_created_at
    assert updated_layout.updated_at != initial_updated_at  # This should be updated

    # Try updating with wrong data model
    wrong_data_model_layout = DocumentLayout(
        name="test-document-layout",
        data_model="wrong-data-model",
        extraction_schema={"fields": ["field1"]},
        translation_schema=initial_translation_schema,
    )
    wrong_data_model_layout.update_translation_schema(postgres_datasource, new_translation_schema)

    # Verify the schema wasn't updated and all fields remain the same
    unchanged_layout = DocumentLayout.find_by_name(
        postgres_datasource, data_model.name, document_layout.name
    )
    assert unchanged_layout is not None
    assert (
        unchanged_layout.translation_schema == new_translation_schema
    )  # Should still have the previous update
    assert unchanged_layout.name == document_layout.name
    assert unchanged_layout.data_model == document_layout.data_model
    assert unchanged_layout.extraction_schema == initial_extraction_schema
    assert unchanged_layout.created_at == initial_created_at
    assert (
        unchanged_layout.updated_at == updated_layout.updated_at
    )  # Should not have changed from last update


def test_default_layouts_different_data_models(postgres_datasource: "DataSource"):
    """Test creating two document layouts with the same name 'default' but different data
    models and updating one."""

    # Create two data models
    data_model1 = DataModel(
        name="energy-trading",
        description="Energy trading data model",
        model_schema={},
    )
    data_model2 = DataModel(
        name="commodity-trading",
        description="Commodity trading data model",
        model_schema={},
    )
    data_model1.insert(postgres_datasource)
    data_model2.insert(postgres_datasource)

    # Create two document layouts both named 'default' but with different data models
    default_layout1 = DocumentLayout(
        name="default",
        data_model="energy-trading",
        extraction_schema={"fields": ["energy_type", "quantity", "price"]},
        translation_schema={"mappings": {"energy_type": "type", "quantity": "qty"}},
    )

    default_layout2 = DocumentLayout(
        name="default",
        data_model="commodity-trading",
        extraction_schema={"fields": ["commodity", "volume", "unit_price"]},
        translation_schema={"mappings": {"commodity": "product", "volume": "amount"}},
    )

    # Insert both layouts
    default_layout1.insert(postgres_datasource)
    default_layout2.insert(postgres_datasource)

    # Verify both layouts exist and are distinct
    retrieved_layout1 = DocumentLayout.find_by_name(
        postgres_datasource, "energy-trading", "default"
    )
    retrieved_layout2 = DocumentLayout.find_by_name(
        postgres_datasource, "commodity-trading", "default"
    )

    assert retrieved_layout1 is not None
    assert retrieved_layout2 is not None
    assert retrieved_layout1.data_model == "energy-trading"
    assert retrieved_layout2.data_model == "commodity-trading"
    assert retrieved_layout1.extraction_schema == {"fields": ["energy_type", "quantity", "price"]}
    assert retrieved_layout2.extraction_schema == {"fields": ["commodity", "volume", "unit_price"]}

    # Store original updated_at timestamps
    original_updated_at1 = retrieved_layout1.updated_at
    original_updated_at2 = retrieved_layout2.updated_at

    # Update the document layout1
    default_layout1.translation_schema = {
        "mappings": {
            "energy_type": "energy_category",
            "quantity": "amount",
            "price": "unit_cost",
        }
    }
    default_layout1.update(postgres_datasource)

    # Verify the first layout was updated
    updated_layout1 = DocumentLayout.find_by_name(postgres_datasource, "energy-trading", "default")
    unchanged_layout2 = DocumentLayout.find_by_name(
        postgres_datasource, "commodity-trading", "default"
    )

    assert updated_layout1 is not None
    assert unchanged_layout2 is not None

    # Verify the first layout's translation schema was updated
    assert updated_layout1.translation_schema == default_layout1.translation_schema
    assert updated_layout1.updated_at != original_updated_at1

    # Verify the second layout remained unchanged
    assert unchanged_layout2.translation_schema == {
        "mappings": {"commodity": "product", "volume": "amount"}
    }
    assert unchanged_layout2.updated_at == original_updated_at2

    # Verify other fields of the first layout remain unchanged
    assert updated_layout1.name == "default"
    assert updated_layout1.data_model == "energy-trading"
    assert updated_layout1.extraction_schema == {"fields": ["energy_type", "quantity", "price"]}
    assert updated_layout1.created_at == retrieved_layout1.created_at


def test_delete_by_data_model(postgres_datasource: "DataSource"):
    """Test bulk deletion of document layouts by data model."""
    # Create a data model first
    data_model = DataModel(
        name="test-data-model",
        description="A test data model",
        model_schema={},
    )
    data_model.insert(postgres_datasource)

    # Create multiple document layouts for the same data model
    layout1 = DocumentLayout(
        name="test-document-layout-1",
        data_model="test-data-model",
        extraction_schema={"fields": ["field1"]},
        translation_schema={"mappings": {"field1": "mapped1"}},
        summary="Layout 1",
    )
    layout2 = DocumentLayout(
        name="test-document-layout-2",
        data_model="test-data-model",
        extraction_schema={"fields": ["field2"]},
        translation_schema={"mappings": {"field2": "mapped2"}},
        summary="Layout 2",
    )
    layout3 = DocumentLayout(
        name="test-document-layout-3",
        data_model="test-data-model",
        extraction_schema={"fields": ["field3"]},
        translation_schema={"mappings": {"field3": "mapped3"}},
        summary="Layout 3",
    )

    layout1.insert(postgres_datasource)
    layout2.insert(postgres_datasource)
    layout3.insert(postgres_datasource)

    # Verify layouts exist before deletion
    layouts = DocumentLayout.find_by_data_model(postgres_datasource, "test-data-model")
    assert len(layouts) == 3

    # Bulk delete all layouts for the data model
    deleted_count = DocumentLayout.delete_by_data_model(postgres_datasource, "test-data-model")
    assert deleted_count == 3

    # Verify all layouts are deleted
    layouts = DocumentLayout.find_by_data_model(postgres_datasource, "test-data-model")
    assert len(layouts) == 0

    # Verify individual layouts are no longer accessible
    assert (
        DocumentLayout.find_by_name(
            postgres_datasource, "test-data-model", "test-document-layout-1"
        )
        is None
    )
    assert (
        DocumentLayout.find_by_name(
            postgres_datasource, "test-data-model", "test-document-layout-2"
        )
        is None
    )
    assert (
        DocumentLayout.find_by_name(
            postgres_datasource, "test-data-model", "test-document-layout-3"
        )
        is None
    )


def test_delete_by_data_model_empty(postgres_datasource: "DataSource"):
    """Test bulk deletion when no layouts exist for the data model."""
    # Create a data model first
    data_model = DataModel(
        name="test-data-model",
        description="A test data model",
        model_schema={},
    )
    data_model.insert(postgres_datasource)

    # Verify no layouts exist for the data model
    layouts = DocumentLayout.find_by_data_model(postgres_datasource, "test-data-model")
    assert len(layouts) == 0

    # Bulk delete - should return 0
    deleted_count = DocumentLayout.delete_by_data_model(postgres_datasource, "test-data-model")
    assert deleted_count == 0

    # Verify still no layouts exist
    layouts = DocumentLayout.find_by_data_model(postgres_datasource, "test-data-model")
    assert len(layouts) == 0


def test_delete_by_data_model_multiple_data_models(postgres_datasource: "DataSource"):
    """Test bulk deletion with multiple data models."""
    # Create two data models
    data_model1 = DataModel(
        name="test-data-model-1",
        description="A test data model 1",
        model_schema={},
    )
    data_model2 = DataModel(
        name="test-data-model-2",
        description="A test data model 2",
        model_schema={},
    )
    data_model1.insert(postgres_datasource)
    data_model2.insert(postgres_datasource)

    # Create layouts for both data models
    layout1 = DocumentLayout(
        name="test-document-layout-1",
        data_model="test-data-model-1",
        extraction_schema={"fields": ["field1"]},
        translation_schema={"mappings": {"field1": "mapped1"}},
        summary="Layout 1",
    )
    layout2 = DocumentLayout(
        name="test-document-layout-2",
        data_model="test-data-model-1",
        extraction_schema={"fields": ["field2"]},
        translation_schema={"mappings": {"field2": "mapped2"}},
        summary="Layout 2",
    )
    layout3 = DocumentLayout(
        name="test-document-layout-3",
        data_model="test-data-model-2",
        extraction_schema={"fields": ["field3"]},
        translation_schema={"mappings": {"field3": "mapped3"}},
        summary="Layout 3",
    )

    layout1.insert(postgres_datasource)
    layout2.insert(postgres_datasource)
    layout3.insert(postgres_datasource)

    # Verify layouts exist for both data models
    layouts1 = DocumentLayout.find_by_data_model(postgres_datasource, "test-data-model-1")
    layouts2 = DocumentLayout.find_by_data_model(postgres_datasource, "test-data-model-2")
    assert len(layouts1) == 2
    assert len(layouts2) == 1

    # Delete layouts for data model 1 only
    deleted_count = DocumentLayout.delete_by_data_model(postgres_datasource, "test-data-model-1")
    assert deleted_count == 2

    # Verify only data model 1 layouts are deleted
    layouts1 = DocumentLayout.find_by_data_model(postgres_datasource, "test-data-model-1")
    layouts2 = DocumentLayout.find_by_data_model(postgres_datasource, "test-data-model-2")
    assert len(layouts1) == 0
    assert len(layouts2) == 1

    # Verify individual layouts
    assert (
        DocumentLayout.find_by_name(
            postgres_datasource, "test-data-model-1", "test-document-layout-1"
        )
        is None
    )
    assert (
        DocumentLayout.find_by_name(
            postgres_datasource, "test-data-model-1", "test-document-layout-2"
        )
        is None
    )
    assert (
        DocumentLayout.find_by_name(
            postgres_datasource, "test-data-model-2", "test-document-layout-3"
        )
        is not None
    )


def test_delete_by_data_model_non_existent(postgres_datasource: "DataSource"):
    """Test bulk deletion for non-existent data model."""
    # Create a data model first
    data_model = DataModel(
        name="test-data-model",
        description="A test data model",
        model_schema={},
    )
    data_model.insert(postgres_datasource)

    # Create a layout
    layout = DocumentLayout(
        name="test-document-layout",
        data_model="test-data-model",
        extraction_schema={"fields": ["field1"]},
        translation_schema={"mappings": {"field1": "mapped1"}},
        summary="Layout 1",
    )
    layout.insert(postgres_datasource)

    # Verify layout exists
    layouts = DocumentLayout.find_by_data_model(postgres_datasource, "test-data-model")
    assert len(layouts) == 1

    # Try to delete layouts for non-existent data model
    deleted_count = DocumentLayout.delete_by_data_model(
        postgres_datasource, "non-existent-data-model"
    )
    assert deleted_count == 0

    # Verify original layout still exists
    layouts = DocumentLayout.find_by_data_model(postgres_datasource, "test-data-model")
    assert len(layouts) == 1
    assert (
        DocumentLayout.find_by_name(postgres_datasource, "test-data-model", "test-document-layout")
        is not None
    )
