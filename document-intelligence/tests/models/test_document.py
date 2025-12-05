import uuid

from sema4ai.data import DataSource

from sema4ai_docint.models import DataModel, Document, DocumentLayout


def test_crud(postgres_datasource: "DataSource"):
    """Test that we can interact with a Document model."""
    # Create a data model and document layout first since document depends on them
    data_model = DataModel(
        name="test-data-model",
        description="A test data model",
        model_schema={},
    )
    data_model.insert(postgres_datasource)

    document_layout = DocumentLayout(
        name="test-document-layout",
        data_model="test-data-model",
        extraction_schema={"fields": ["field1", "field2"]},
        translation_schema={"mappings": {"field1": "mapped1"}},
    )
    document_layout.insert(postgres_datasource)

    # Document does not exist
    non_existent_id = str(uuid.uuid4())  # Generate a valid UUID that doesn't exist in the database
    existing_doc = Document.find_by_id(postgres_datasource, non_existent_id)
    assert existing_doc is None

    extracted_content = {"field1": "value1", "field2": "value2"}
    translated_content = {"mapped1": "value1"}

    # Create a document using the create helper method
    doc = Document.create(
        postgres_datasource,
        document_layout="test-document-layout",
        data_model="test-data-model",
        document_name="doc1.pdf",
        extracted_content=extracted_content,
        translated_content=translated_content,
    )

    # Read it back from the database
    actual = Document.find_by_id(postgres_datasource, doc.id)
    assert actual is not None
    assert actual.id == doc.id
    assert actual.document_name == "doc1.pdf"
    assert actual.document_layout == doc.document_layout
    assert actual.data_model == doc.data_model
    assert actual.extracted_content == extracted_content
    assert actual.translated_content == translated_content

    # Update the document
    new_extracted_content = {"field1": "new_value1", "field2": "new_value2"}
    new_translated_content = {"mapped1": "new_value1"}
    doc.extracted_content = new_extracted_content
    doc.translated_content = new_translated_content
    doc.update(postgres_datasource)

    # Read it back from the database
    new_actual = Document.find_by_id(postgres_datasource, doc.id)
    assert new_actual is not None
    assert new_actual.extracted_content == new_extracted_content
    assert new_actual.translated_content == new_translated_content
    assert new_actual.updated_at is not None
    assert new_actual.updated_at > actual.updated_at
    assert new_actual.created_at is not None
    assert new_actual.created_at < new_actual.updated_at

    # Delete the document
    was_deleted = doc.delete(postgres_datasource)
    assert was_deleted is True

    # Try to read it back, verify it's deleted
    actual = Document.find_by_id(postgres_datasource, doc.id)
    assert actual is None


def test_find_all(postgres_datasource: "DataSource"):
    """Test that we can find all documents."""
    # Create a data model and document layout first
    data_model = DataModel(
        name="test-data-model",
        description="A test data model",
        model_schema={},
    )
    data_model.insert(postgres_datasource)

    document_layout = DocumentLayout(
        name="test-document-layout",
        data_model="test-data-model",
        extraction_schema={"fields": ["field1"]},
        translation_schema={"mappings": {"field1": "mapped1"}},
    )
    document_layout.insert(postgres_datasource)

    # Create documents
    doc1 = Document.create(
        postgres_datasource,
        document_layout="test-document-layout",
        data_model="test-data-model",
        document_name="doc1.pdf",
        extracted_content={"field1": "value1"},
        translated_content={"mapped1": "value1"},
    )
    doc2 = Document.create(
        postgres_datasource,
        document_layout="test-document-layout",
        data_model="test-data-model",
        document_name="doc2.pdf",
        extracted_content={"field1": "value2"},
        translated_content={"mapped1": "value2"},
    )

    # Find all documents
    docs = Document.find_all(postgres_datasource)
    assert len(docs) == 2
    doc_ids = [d.id for d in docs]
    assert doc1.id in doc_ids, "did not find document 1"
    assert doc2.id in doc_ids, "did not find document 2"
    # Verify that content fields are not returned
    for doc in docs:
        assert doc.extracted_content is None
        assert doc.translated_content is None


def test_find_by_schema(postgres_datasource: "DataSource"):
    """Test that we can find documents by schema."""
    # Create a data model and two document layouts
    data_model = DataModel(
        name="test-data-model",
        description="A test data model",
        model_schema={},
    )
    data_model.insert(postgres_datasource)

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

    # Create documents for both schemas
    doc1 = Document.create(
        postgres_datasource,
        document_layout="test-document-layout-1",
        data_model="test-data-model",
        document_name="doc1.pdf",
        extracted_content={"field1": "value1"},
        translated_content={"mapped1": "value1"},
    )
    doc2 = Document.create(
        postgres_datasource,
        document_layout="test-document-layout-1",
        data_model="test-data-model",
        document_name="doc2.pdf",
        extracted_content={"field1": "value2"},
        translated_content={"mapped1": "value2"},
    )
    doc3 = Document.create(
        postgres_datasource,
        document_layout="test-document-layout-2",
        data_model="test-data-model",
        document_name="doc3.pdf",
        extracted_content={"field2": "value3"},
        translated_content={"mapped2": "value3"},
    )

    # Find documents for schema 1
    docs = Document.find_by_document_layout(
        postgres_datasource, "test-data-model", "test-document-layout-1"
    )
    assert len(docs) == 2
    doc_ids = [d.id for d in docs]
    assert doc1.id in doc_ids, "did not find document 1"
    assert doc2.id in doc_ids, "did not find document 2"

    # Find documents for schema 2
    docs = Document.find_by_document_layout(
        postgres_datasource, "test-data-model", "test-document-layout-2"
    )
    assert len(docs) == 1
    assert docs[0].id == doc3.id, "did not find document 3"
    assert docs[0].extracted_content is not None
    assert docs[0].translated_content is not None

    # Find documents for non-existent schema
    docs = Document.find_by_document_layout(
        postgres_datasource, "test-data-model", "non-existent-document-layout"
    )
    assert len(docs) == 0


def test_find_by_use_case(postgres_datasource: "DataSource"):
    """Test that we can find documents by use case."""
    # Create a data model and document layout first
    data_model = DataModel(
        name="test-data-model",
        description="A test data model",
        model_schema={},
    )
    data_model.insert(postgres_datasource)

    document_layout = DocumentLayout(
        name="test-document-layout",
        data_model="test-data-model",
        extraction_schema={"fields": ["field1"]},
        translation_schema={"mappings": {"field1": "mapped1"}},
    )
    document_layout.insert(postgres_datasource)

    # Create documents for the use case
    doc1 = Document.create(
        postgres_datasource,
        document_layout="test-document-layout",
        data_model="test-data-model",
        document_name="doc1.pdf",
        extracted_content={"field1": "value1"},
        translated_content={"mapped1": "value1"},
    )
    doc2 = Document.create(
        postgres_datasource,
        document_layout="test-document-layout",
        data_model="test-data-model",
        document_name="doc2.pdf",
        extracted_content={"field1": "value2"},
        translated_content={"mapped1": "value2"},
    )

    # Find documents for the use case
    docs = Document.find_by_data_model(postgres_datasource, "test-data-model")
    assert len(docs) == 2
    doc_ids = [d.id for d in docs]
    assert doc1.id in doc_ids, "did not find document 1"
    assert doc2.id in doc_ids, "did not find document 2"

    # Verify that content fields are not returned
    for doc in docs:
        assert doc.extracted_content is None
        assert doc.translated_content is None

    # Find documents for non-existent use case
    docs = Document.find_by_data_model(postgres_datasource, "non-existent-data-model")
    assert len(docs) == 0


def test_bulk_delete_by_data_model(postgres_datasource: "DataSource"):
    """Test bulk deletion of documents by data model."""
    # Create a data model and document layout first
    data_model = DataModel(
        name="test-data-model",
        description="A test data model",
        model_schema={},
    )
    data_model.insert(postgres_datasource)

    document_layout = DocumentLayout(
        name="test-document-layout",
        data_model="test-data-model",
        extraction_schema={"fields": ["field1"]},
        translation_schema={"mappings": {"field1": "mapped1"}},
    )
    document_layout.insert(postgres_datasource)

    # Create multiple documents for the same data model
    doc1 = Document.create(
        postgres_datasource,
        document_layout="test-document-layout",
        data_model="test-data-model",
        document_name="doc1.pdf",
        extracted_content={"field1": "value1"},
        translated_content={"mapped1": "value1"},
    )
    doc2 = Document.create(
        postgres_datasource,
        document_layout="test-document-layout",
        data_model="test-data-model",
        document_name="doc2.pdf",
        extracted_content={"field1": "value2"},
        translated_content={"mapped1": "value2"},
    )
    doc3 = Document.create(
        postgres_datasource,
        document_layout="test-document-layout",
        data_model="test-data-model",
        document_name="doc3.pdf",
        extracted_content={"field1": "value3"},
        translated_content={"mapped1": "value3"},
    )

    # Verify documents exist before deletion
    docs = Document.find_by_data_model(postgres_datasource, "test-data-model")
    assert len(docs) == 3

    # Bulk delete all documents for the data model
    deleted_count = Document.delete_by_data_model(postgres_datasource, "test-data-model")
    assert deleted_count == 3

    # Verify all documents are deleted
    docs = Document.find_by_data_model(postgres_datasource, "test-data-model")
    assert len(docs) == 0

    # Verify individual documents are no longer accessible
    assert Document.find_by_id(postgres_datasource, doc1.id) is None
    assert Document.find_by_id(postgres_datasource, doc2.id) is None
    assert Document.find_by_id(postgres_datasource, doc3.id) is None


def test_bulk_delete_by_data_model_empty(postgres_datasource: "DataSource"):
    """Test bulk deletion when no documents exist for the data model."""
    # Create a data model and document layout first
    data_model = DataModel(
        name="test-data-model",
        description="A test data model",
        model_schema={},
    )
    data_model.insert(postgres_datasource)

    document_layout = DocumentLayout(
        name="test-document-layout",
        data_model="test-data-model",
        extraction_schema={"fields": ["field1"]},
        translation_schema={"mappings": {"field1": "mapped1"}},
    )
    document_layout.insert(postgres_datasource)

    # Verify no documents exist for the data model
    docs = Document.find_by_data_model(postgres_datasource, "test-data-model")
    assert len(docs) == 0

    # Bulk delete - should return 0
    deleted_count = Document.delete_by_data_model(postgres_datasource, "test-data-model")
    assert deleted_count == 0

    # Verify still no documents exist
    docs = Document.find_by_data_model(postgres_datasource, "test-data-model")
    assert len(docs) == 0


def test_bulk_delete_by_data_model_multiple_data_models(
    postgres_datasource: "DataSource",
):
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

    # Create document layouts for both data models
    document_layout1 = DocumentLayout(
        name="test-document-layout-1",
        data_model="test-data-model-1",
        extraction_schema={"fields": ["field1"]},
        translation_schema={"mappings": {"field1": "mapped1"}},
    )
    document_layout2 = DocumentLayout(
        name="test-document-layout-2",
        data_model="test-data-model-2",
        extraction_schema={"fields": ["field2"]},
        translation_schema={"mappings": {"field2": "mapped2"}},
    )
    document_layout1.insert(postgres_datasource)
    document_layout2.insert(postgres_datasource)

    # Create documents for both data models
    doc1 = Document.create(
        postgres_datasource,
        document_layout="test-document-layout-1",
        data_model="test-data-model-1",
        document_name="doc1.pdf",
        extracted_content={"field1": "value1"},
        translated_content={"mapped1": "value1"},
    )
    doc2 = Document.create(
        postgres_datasource,
        document_layout="test-document-layout-1",
        data_model="test-data-model-1",
        document_name="doc2.pdf",
        extracted_content={"field1": "value2"},
        translated_content={"mapped1": "value2"},
    )
    doc3 = Document.create(
        postgres_datasource,
        document_layout="test-document-layout-2",
        data_model="test-data-model-2",
        document_name="doc3.pdf",
        extracted_content={"field2": "value3"},
        translated_content={"mapped2": "value3"},
    )

    # Verify documents exist for both data models
    docs1 = Document.find_by_data_model(postgres_datasource, "test-data-model-1")
    docs2 = Document.find_by_data_model(postgres_datasource, "test-data-model-2")
    assert len(docs1) == 2
    assert len(docs2) == 1

    # Delete documents for data model 1 only
    deleted_count = Document.delete_by_data_model(postgres_datasource, "test-data-model-1")
    assert deleted_count == 2

    # Verify only data model 1 documents are deleted
    docs1 = Document.find_by_data_model(postgres_datasource, "test-data-model-1")
    docs2 = Document.find_by_data_model(postgres_datasource, "test-data-model-2")
    assert len(docs1) == 0
    assert len(docs2) == 1

    # Verify individual documents
    assert Document.find_by_id(postgres_datasource, doc1.id) is None
    assert Document.find_by_id(postgres_datasource, doc2.id) is None
    assert Document.find_by_id(postgres_datasource, doc3.id) is not None


def test_bulk_delete_by_data_model_non_existent(postgres_datasource: "DataSource"):
    """Test bulk deletion for non-existent data model."""
    # Create a data model and document layout first
    data_model = DataModel(
        name="test-data-model",
        description="A test data model",
        model_schema={},
    )
    data_model.insert(postgres_datasource)

    document_layout = DocumentLayout(
        name="test-document-layout",
        data_model="test-data-model",
        extraction_schema={"fields": ["field1"]},
        translation_schema={"mappings": {"field1": "mapped1"}},
    )
    document_layout.insert(postgres_datasource)

    # Create a document
    doc = Document.create(
        postgres_datasource,
        document_layout="test-document-layout",
        data_model="test-data-model",
        document_name="doc1.pdf",
        extracted_content={"field1": "value1"},
        translated_content={"mapped1": "value1"},
    )

    # Verify document exists
    docs = Document.find_by_data_model(postgres_datasource, "test-data-model")
    assert len(docs) == 1

    # Try to delete documents for non-existent data model
    deleted_count = Document.delete_by_data_model(postgres_datasource, "non-existent-data-model")
    assert deleted_count == 0

    # Verify original document still exists
    docs = Document.find_by_data_model(postgres_datasource, "test-data-model")
    assert len(docs) == 1
    assert Document.find_by_id(postgres_datasource, doc.id) is not None
