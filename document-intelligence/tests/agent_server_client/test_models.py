import pytest
from pydantic import ValidationError

from sema4ai_docint.agent_server_client.models import View


def test_valid_view():
    """Test creating a valid view."""
    view_data = {
        "name": "test_view",
        "sql": "SELECT * FROM test_table",
        "columns": [
            {"name": "id", "type": "integer"},
            {"name": "name", "type": "text"},
            {"name": "value", "type": "numeric"},
        ],
    }
    view = View(**view_data)
    assert view.name == "test_view"
    assert view.sql == "SELECT * FROM test_table"
    assert len(view.columns) == 3
    assert view.columns[0].name == "id"
    assert view.columns[0].type == "integer"
    assert view.get_column_names() == ["id", "name", "value"]


def test_view_with_whitespace():
    """Test that whitespace is properly stripped from fields."""
    view_data = {
        "name": "  test_view  ",
        "sql": "  SELECT * FROM test_table  ",
        "columns": [
            {"name": "  id  ", "type": "  integer  "},
            {"name": "  name  ", "type": "  text  "},
            {"name": "  value  ", "type": "  numeric  "},
        ],
    }
    view = View(**view_data)
    assert view.name == "test_view"
    assert view.sql == "SELECT * FROM test_table"
    assert view.columns[0].name == "id"
    assert view.columns[0].type == "integer"
    assert view.get_column_names() == ["id", "name", "value"]


def test_empty_name():
    """Test that empty name raises validation error."""
    view_data = {
        "name": "",
        "sql": "SELECT * FROM test_table",
        "columns": [
            {"name": "id", "type": "integer"},
            {"name": "name", "type": "text"},
        ],
    }
    with pytest.raises(ValidationError) as exc_info:
        View(**view_data)
    assert "name" in str(exc_info.value)


def test_empty_sql():
    """Test that empty SQL raises validation error."""
    view_data = {
        "name": "test_view",
        "sql": "",
        "columns": [
            {"name": "id", "type": "integer"},
            {"name": "name", "type": "text"},
        ],
    }
    with pytest.raises(ValidationError) as exc_info:
        View(**view_data)
    assert "sql" in str(exc_info.value)


def test_empty_columns():
    """Test that empty columns list raises validation error."""
    view_data = {"name": "test_view", "sql": "SELECT * FROM test_table", "columns": []}
    with pytest.raises(ValidationError) as exc_info:
        View(**view_data)
    assert "columns" in str(exc_info.value)


def test_empty_column_name():
    """Test that empty column name raises validation error."""
    view_data = {
        "name": "test_view",
        "sql": "SELECT * FROM test_table",
        "columns": [
            {"name": "id", "type": "integer"},
            {"name": "", "type": "text"},
            {"name": "value", "type": "numeric"},
        ],
    }
    with pytest.raises(ValidationError) as exc_info:
        View(**view_data)
    assert "name" in str(exc_info.value)


def test_empty_column_type():
    """Test that empty column type raises validation error."""
    view_data = {
        "name": "test_view",
        "sql": "SELECT * FROM test_table",
        "columns": [
            {"name": "id", "type": "integer"},
            {"name": "name", "type": ""},
            {"name": "value", "type": "numeric"},
        ],
    }
    with pytest.raises(ValidationError) as exc_info:
        View(**view_data)
    assert "type" in str(exc_info.value)


def test_missing_required_fields():
    """Test that missing required fields raise validation error."""
    # Test missing name
    with pytest.raises(ValidationError) as exc_info:
        View(sql="SELECT * FROM test_table", columns=[{"name": "id", "type": "integer"}])
    assert "name" in str(exc_info.value)

    # Test missing sql
    with pytest.raises(ValidationError) as exc_info:
        View(name="test_view", columns=[{"name": "id", "type": "integer"}])
    assert "sql" in str(exc_info.value)


def test_model_serialization():
    """Test that the model can be serialized to and from JSON."""
    view_data = {
        "name": "test_view",
        "sql": "SELECT * FROM test_table",
        "columns": [
            {"name": "id", "type": "integer"},
            {"name": "name", "type": "text"},
            {"name": "value", "type": "numeric"},
        ],
    }
    view = View(**view_data)

    # Test serialization to dict
    view_dict = view.model_dump()
    assert view_dict == view_data

    # Test serialization to JSON
    view_json = view.model_dump_json()
    assert isinstance(view_json, str)

    # Test deserialization from JSON
    new_view = View.model_validate_json(view_json)
    assert new_view == view
