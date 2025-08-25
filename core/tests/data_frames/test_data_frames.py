import datetime

import pytest

from agent_platform.core.data_frames.data_frames import DataFrameSource, PlatformDataFrame


# Convert bytes to base64 for JSON serialization (the parquet_contents is a bytes object)
def convert_bytes_to_base64(obj):
    import base64

    if isinstance(obj, bytes):
        return base64.b64encode(obj).decode("utf-8")
    elif isinstance(obj, dict):
        return {k: convert_bytes_to_base64(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_bytes_to_base64(item) for item in obj]
    else:
        return obj


def test_data_frame_source_basic_model_dump_and_validate():
    """Test 1: Basic test for DataFrameSource model_dump and model_validate."""
    # Create a DataFrameSource instance
    source = DataFrameSource(source_type="data_frame", source_id="test-source-123")

    # Test model_dump
    dumped = source.model_dump()
    expected = {"source_type": "data_frame", "source_id": "test-source-123"}
    assert dumped == expected

    # Test model_validate
    validated = DataFrameSource.model_validate(dumped)
    assert validated.source_type == "data_frame"
    assert validated.source_id == "test-source-123"

    # Test round-trip
    assert validated.model_dump() == dumped


def test_data_frame_basic_model_dump_and_validate(file_regression):
    """Test 1: Basic test for PlatformDataFrame model_dump and model_validate."""
    import json

    # Create a PlatformDataFrame instance with minimal required fields
    created_at = datetime.datetime(2023, 1, 1, 12, 0, 0)
    source = DataFrameSource(source_type="data_frame", source_id="source-456")

    data_frame = PlatformDataFrame(
        data_frame_id="df-123",
        user_id="user-456",
        agent_id="agent-789",
        thread_id="thread-101",
        num_rows=100,
        num_columns=5,
        column_headers=["col1", "col2", "col3", "col4", "col5"],
        name="Test_PlatformDataFrame",
        input_id_type="sql_computation",
        created_at=created_at,
        computation_input_sources={"source1": source},
        computation="SELECT * FROM source1",
    )

    # Test model_dump
    dumped = data_frame.model_dump()
    file_regression.check(json.dumps(convert_bytes_to_base64(dumped), indent=2))

    # Test model_validate
    validated = PlatformDataFrame.model_validate(dumped)
    assert validated.data_frame_id == "df-123"
    assert validated.user_id == "user-456"
    assert validated.num_rows == 100
    assert validated.num_columns == 5
    assert validated.column_headers == ["col1", "col2", "col3", "col4", "col5"]
    assert validated.name == "Test_PlatformDataFrame"
    assert validated.input_id_type == "sql_computation"
    assert validated.created_at == created_at
    assert len(validated.computation_input_sources) == 1
    assert validated.computation_input_sources["source1"].source_id == "source-456"

    # Test round-trip
    file_regression.check(json.dumps(convert_bytes_to_base64(dumped), indent=2))


def test_data_frame_complex_model_dump_and_validate(file_regression):
    """Test 2: Complex test for PlatformDataFrame with all optional fields."""
    import json

    # Create a complex PlatformDataFrame instance with all fields
    created_at = datetime.datetime(2023, 6, 15, 14, 30, 45, 123456)
    source1 = DataFrameSource(source_type="data_frame", source_id="frame-001")
    source2 = DataFrameSource(source_type="data_frame", source_id="source-002")

    data_frame = PlatformDataFrame(
        data_frame_id="complex-df-789",
        user_id="complex-user-123",
        agent_id="complex-agent-456",
        thread_id="complex-thread-789",
        num_rows=1000,
        num_columns=25,
        column_headers=["col1", "col2", "col3", "col4", "col5"],
        name="Complex_Test_PlatformDataFrame",
        input_id_type="file",
        created_at=created_at,
        computation_input_sources={"source1": source1, "source2": source2},
        file_id="file-123",
        description="A comprehensive test data frame with all fields populated",
        computation="SELECT * FROM complex_table WHERE active = true",
        parquet_contents=b"fake_parquet_data_here",
        sheet_name="Sheet1",
    )

    # Test model_dump
    dumped = data_frame.model_dump()

    dumped_for_json = convert_bytes_to_base64(dumped)
    file_regression.check(json.dumps(dumped_for_json, indent=2))

    # Test model_validate
    validated = PlatformDataFrame.model_validate(dumped)
    assert validated.data_frame_id == "complex-df-789"
    assert validated.user_id == "complex-user-123"
    assert validated.num_rows == 1000
    assert validated.num_columns == 25
    assert validated.name == "Complex_Test_PlatformDataFrame"
    assert validated.input_id_type == "file"
    assert validated.created_at == created_at
    assert validated.file_id == "file-123"
    assert validated.description == "A comprehensive test data frame with all fields populated"
    assert validated.computation == "SELECT * FROM complex_table WHERE active = true"
    assert validated.parquet_contents == b"fake_parquet_data_here"
    assert validated.sheet_name == "Sheet1"
    assert len(validated.computation_input_sources) == 2
    assert validated.computation_input_sources["source1"].source_type == "data_frame"
    assert validated.computation_input_sources["source2"].source_type == "data_frame"

    # Test round-trip
    validated_dumped = validated.model_dump()
    validated_dumped_for_json = convert_bytes_to_base64(validated_dumped)
    file_regression.check(json.dumps(validated_dumped_for_json, indent=2))


def test_data_frame_error_handling():
    """Test 3: Test error handling and edge cases."""
    # Test missing required fields in DataFrameSource
    with pytest.raises(KeyError):
        DataFrameSource.model_validate({})

    with pytest.raises(KeyError):
        DataFrameSource.model_validate({"source_type": "data_frame"})  # missing source_id

    with pytest.raises(KeyError):
        DataFrameSource.model_validate({"source_id": "test"})  # missing source_type

    # Test missing required fields in PlatformDataFrame
    with pytest.raises(KeyError):
        PlatformDataFrame.model_validate({})

    with pytest.raises(KeyError):
        PlatformDataFrame.model_validate({"data_frame_id": "test"})  # missing other required fields

    # Test invalid datetime format
    invalid_data = {
        "data_frame_id": "df-123",
        "user_id": "user-456",
        "agent_id": "agent-789",
        "thread_id": "thread-101",
        "num_rows": 100,
        "num_columns": 5,
        "column_headers": ["col1", "col2", "col3", "col4", "col5"],
        "name": "Test_PlatformDataFrame",
        "input_id_type": "sql_computation",
        "created_at": "invalid-datetime-format",
        "computation_input_sources": {},
    }

    with pytest.raises(ValueError, match="Unable to parse created_at: 'invalid-datetime-format'"):
        PlatformDataFrame.model_validate(invalid_data)

    # Test invalid source_type in DataFrameSource
    with pytest.raises(ValueError, match="Invalid value for 'source_type': 'invalid_type'"):
        DataFrameSource.model_validate({"source_type": "invalid_type", "source_id": "test"})

    # Test invalid input_id_type in PlatformDataFrame
    invalid_data["created_at"] = "2023-01-01T12:00:00"
    invalid_data["input_id_type"] = "invalid_type"

    with pytest.raises(ValueError, match="Invalid value for 'input_id_type': 'invalid_type'"):
        PlatformDataFrame.model_validate(invalid_data)

    # Test that optional fields are properly handled when None
    minimal_data = {
        "data_frame_id": "df-123",
        "user_id": "user-456",
        "agent_id": "agent-789",
        "thread_id": "thread-101",
        "num_rows": 100,
        "num_columns": 5,
        "column_headers": ["col1", "col2", "col3", "col4", "col5"],
        "name": "Test_PlatformDataFrame",
        "input_id_type": "sql_computation",
        "created_at": "2023-01-01T12:00:00",
        "computation_input_sources": {},
        "extra_data": {"key": "value"},
        "computation": "SELECT * FROM source1",
    }

    validated = PlatformDataFrame.model_validate(minimal_data)
    assert validated.file_id is None
    assert validated.description is None
    assert validated.computation == "SELECT * FROM source1"
    assert validated.parquet_contents is None
    assert validated.extra_data == {"key": "value"}

    # Test that dumped data doesn't include None values
    dumped = validated.model_dump()
    assert dumped["file_id"] is None
    assert dumped["description"] is None
    assert dumped["parquet_contents"] is None
    assert dumped["extra_data"] == {"key": "value"}
