from datetime import UTC, datetime

from sema4ai.data import DataSource

from sema4ai_docint.models import DataModel


def test_crud(postgres_datasource: "DataSource"):
    """Test that we can interact with a DataModel model."""

    # DataModel does not exist
    existing_data_model = DataModel.find_by_name(postgres_datasource, "does-not-exist")
    assert existing_data_model is None

    data_model = DataModel(
        name="test-data-model",
        description="A test data model with apostrophe's in it",
        model_schema={},
        quality_checks=[
            {
                "rule_name": "test-rule",
                "rule_description": "A test validation rule",
                "sql_query": "SELECT 1",
            }
        ],
        prompt="Test prompt with apostrophe's in it",
        summary="Test summary with apostrophe's in it",
        base_config={
            "experimental_options": {
                "enrich": {
                    "enabled": True,
                    "mode": "table",
                    "prompt": (
                        "CRITICAL: PARSE the entire document\n"
                        "Important: For data in tables, do not skip any rows"
                    ),
                },
                "layout_model": "beta",
            }
        },
    )

    # Create the data model in the database
    data_model.insert(postgres_datasource)

    # Read it back from the database
    actual = DataModel.find_by_name(postgres_datasource, data_model.name)
    assert actual is not None
    assert actual.name == data_model.name
    assert actual.description == data_model.description
    assert actual.model_schema == data_model.model_schema
    assert actual.prompt == data_model.prompt
    assert actual.summary == data_model.summary
    assert actual.quality_checks is not None
    assert len(actual.quality_checks) == 1
    assert actual.quality_checks[0]["rule_name"] == "test-rule"
    assert actual.quality_checks[0]["rule_description"] == "A test validation rule"
    assert actual.quality_checks[0]["sql_query"] == "SELECT 1"
    assert actual.base_config == {
        "experimental_options": {
            "enrich": {
                "enabled": True,
                "mode": "table",
                "prompt": (
                    "CRITICAL: PARSE the entire document\n"
                    "Important: For data in tables, do not skip any rows"
                ),
            },
            "layout_model": "beta",
        }
    }

    # Check that created_at and updated_at timestamps are set and recent
    now = datetime.now(UTC)
    assert actual.created_at is not None
    assert actual.updated_at is not None
    created_dt = datetime.fromisoformat(actual.created_at).replace(tzinfo=UTC)
    updated_dt = datetime.fromisoformat(actual.updated_at).replace(tzinfo=UTC)
    # Allow for a 10 second difference to account for timezone and processing time
    assert abs((now - created_dt).total_seconds()) < 10
    assert abs((now - updated_dt).total_seconds()) < 10

    # Update the data model
    data_model.description = "A new description, but one ' that still has an apostrophe"
    data_model.model_schema = {"new": "model_schema"}
    data_model.quality_checks = [
        {
            "rule_name": "updated-rule",
            "rule_description": "An updated validation rule",
            "sql_query": "SELECT 2",
        }
    ]
    data_model.summary = "Updated summary with apostrophe's in it"
    data_model.prompt = "Updated prompt with apostrophe's in it"
    data_model.base_config = {
        "experimental_options": {
            "enrich": {
                "enabled": False,
                "mode": "document",
                "prompt": "UPDATED: Parse the document with enhanced accuracy",
            },
            "layout_model": "stable",
        }
    }
    data_model.update(postgres_datasource)

    # Read it back from the database
    new_actual = DataModel.find_by_name(postgres_datasource, data_model.name)
    assert new_actual is not None
    assert new_actual.description == data_model.description
    assert new_actual.model_schema == data_model.model_schema
    assert new_actual.prompt == "Updated prompt with apostrophe's in it"
    assert new_actual.summary == "Updated summary with apostrophe's in it"
    assert new_actual.quality_checks is not None
    assert len(new_actual.quality_checks) == 1
    assert new_actual.quality_checks[0]["rule_name"] == "updated-rule"
    assert new_actual.quality_checks[0]["rule_description"] == "An updated validation rule"
    assert new_actual.quality_checks[0]["sql_query"] == "SELECT 2"
    assert new_actual.base_config == {
        "experimental_options": {
            "enrich": {
                "enabled": False,
                "mode": "document",
                "prompt": "UPDATED: Parse the document with enhanced accuracy",
            },
            "layout_model": "stable",
        }
    }

    # Delete the data model
    was_deleted = data_model.delete(postgres_datasource)
    assert was_deleted is True

    # Try to read it back, verify it's deleted.
    actual = DataModel.find_by_name(postgres_datasource, data_model.name)
    assert actual is None


def test_find_all(postgres_datasource: "DataSource"):
    """Test that we can find all data models."""
    data_models = DataModel.find_all(postgres_datasource)
    assert len(data_models) == 0

    # Create a data model
    data_model1 = DataModel(
        name="test-data-model",
        description="A test data model",
        model_schema={},
        prompt="Test prompt 1",
        summary="Test summary 1",
        quality_checks=[
            {
                "rule_name": "test-rule-1",
                "rule_description": "A test validation rule 1",
                "sql_query": "SELECT 1",
            }
        ],
    )
    data_model2 = DataModel(
        name="test-data-model-2",
        description="A test data model 2",
        model_schema={},
        prompt=None,  # Test with null prompt
        summary=None,  # Test with null summary
        quality_checks=[
            {
                "rule_name": "test-rule-2",
                "rule_description": "A test validation rule 2",
                "sql_query": "SELECT 2",
            }
        ],
    )

    data_model1.insert(postgres_datasource)
    data_model2.insert(postgres_datasource)

    # Find all data models
    data_models = DataModel.find_all(postgres_datasource)
    assert len(data_models) == 2
    assert any(
        data_model.name == data_model1.name
        and data_model.prompt == "Test prompt 1"
        and data_model.summary == "Test summary 1"
        for data_model in data_models
    ), "did not find data model 1 with correct prompt and summary"
    assert any(
        data_model.name == data_model2.name
        and data_model.prompt is None
        and data_model.summary is None
        for data_model in data_models
    ), "did not find data model 2 with null prompt and summary"


def test_to_json():
    # Create a data model with all fields populated
    model = DataModel(
        name="test_model",
        description="Test model description",
        model_schema={"type": "object", "properties": {"test": {"type": "string"}}},
        views=[
            {
                "name": "test_view",
                "sql": "SELECT * FROM test",
                "columns": [{"name": "test_col", "type": "string"}],
            }
        ],
        quality_checks=[{"type": "required", "field": "test"}],
        prompt="test prompt",
        base_config={
            "experimental_options": {
                "enrich": {
                    "enabled": True,
                    "mode": "table",
                    "prompt": (
                        "CRITICAL: PARSE the entire document\n"
                        "Important: For data in tables, do not skip any rows"
                    ),
                },
                "layout_model": "beta",
            }
        },
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z",
    )

    # Convert to JSON
    json_data = model.to_json()

    # Verify required fields are present
    assert json_data["name"] == "test_model"
    assert json_data["description"] == "Test model description"
    assert json_data["model_schema"] == {
        "type": "object",
        "properties": {"test": {"type": "string"}},
    }
    assert json_data["quality_checks"] == [{"type": "required", "field": "test"}]
    assert json_data["base_config"] == {
        "experimental_options": {
            "enrich": {
                "enabled": True,
                "mode": "table",
                "prompt": (
                    "CRITICAL: PARSE the entire document\n"
                    "Important: For data in tables, do not skip any rows"
                ),
            },
            "layout_model": "beta",
        }
    }

    # Verify excluded fields are not present
    assert "created_at" not in json_data
    assert "updated_at" not in json_data

    # Verify views are present but sql field is excluded
    assert len(json_data["views"]) == 1
    view = json_data["views"][0]
    assert view["name"] == "test_view"
    assert "sql" not in view
    assert view["columns"] == [{"name": "test_col", "type": "string"}]


def test_update_prompt(postgres_datasource: "DataSource"):
    """Test that we can interact with a DataModel model."""

    data_model = DataModel(
        name="test-data-model",
        description="A test data model",
        model_schema={},
        quality_checks=[
            {
                "rule_name": "test-rule",
                "rule_description": "A test validation rule",
                "sql_query": "SELECT 1",
            }
        ],
    )

    # Create the data model in the database
    data_model.insert(postgres_datasource)

    actual = DataModel.find_by_name(postgres_datasource, data_model.name)
    assert actual is not None
    assert actual.name == data_model.name
    assert actual.prompt is None

    new_prompt = "Updated prompt with apostrophe's in it"
    data_model.set_prompt(postgres_datasource, new_prompt)

    actual = DataModel.find_by_name(postgres_datasource, data_model.name)
    assert actual is not None
    assert actual.prompt == new_prompt


def test_update_base_config(postgres_datasource: "DataSource"):
    """Test that we can update the base_config field of a DataModel."""

    data_model = DataModel(
        name="test-data-model-extraction",
        description="A test data model for extraction config",
        model_schema={},
        quality_checks=[
            {
                "rule_name": "test-rule",
                "rule_description": "A test validation rule",
                "sql_query": "SELECT 1",
            }
        ],
    )

    # Create the data model in the database
    data_model.insert(postgres_datasource)

    actual = DataModel.find_by_name(postgres_datasource, data_model.name)
    assert actual is not None
    assert actual.name == data_model.name
    assert actual.base_config is None

    # Test setting an base_config
    new_base_config = {
        "experimental_options": {
            "enrich": {
                "enabled": True,
                "mode": "table",
                "prompt": (
                    "CRITICAL: PARSE the entire document\n"
                    "Important: For data in tables, do not skip any rows"
                ),
            },
            "layout_model": "beta",
        }
    }
    data_model.set_base_config(postgres_datasource, new_base_config)

    actual = DataModel.find_by_name(postgres_datasource, data_model.name)
    assert actual is not None
    assert actual.base_config == new_base_config

    # Test setting base_config to None
    data_model.set_base_config(postgres_datasource, None)

    actual = DataModel.find_by_name(postgres_datasource, data_model.name)
    assert actual is not None
    assert actual.base_config is None

    # Clean up
    data_model.delete(postgres_datasource)
