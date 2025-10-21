from pathlib import Path


def test_csv_data_reader():
    from agent_platform.server.data_frames.data_reader import CsvDataReader

    file_bytes = b"name,age\nJohn,25\nJane,30"
    reader = CsvDataReader(file_bytes)
    assert reader.has_multiple_sheets() is False
    sheet = next(reader.iter_sheets())
    assert sheet.name is None
    assert sheet.num_rows == 2
    assert sheet.num_columns == 2
    assert sheet.column_headers == ["name", "age"]
    assert sheet.list_sample_rows(1) == [["John", 25]]
    assert sheet.list_sample_rows(2) == [["John", 25], ["Jane", 30]]
    assert sheet.list_sample_rows(5) == [["John", 25], ["Jane", 30]]
    assert sheet.to_ibis().to_pylist() == [
        {"name": "John", "age": 25},
        {"name": "Jane", "age": 30},
    ]


def test_excel_to_csv_fallback():
    from agent_platform.server.data_frames.data_reader import ExcelDataReader

    file_bytes = b"name,age\nJohn,25\nJane,30"
    reader = ExcelDataReader(file_bytes)
    assert reader.has_multiple_sheets() is False
    sheet = next(reader.iter_sheets())
    assert sheet.name is None
    assert sheet.num_rows == 2
    assert sheet.num_columns == 2
    assert sheet.column_headers == ["name", "age"]
    assert sheet.list_sample_rows(1) == [["John", 25]]
    assert sheet.list_sample_rows(2) == [["John", 25], ["Jane", 30]]
    assert sheet.list_sample_rows(5) == [["John", 25], ["Jane", 30]]
    assert sheet.to_ibis().to_pylist() == [
        {"name": "John", "age": 25},
        {"name": "Jane", "age": 30},
    ]


def test_excel_data_reader(datadir: Path):
    from agent_platform.server.data_frames.data_reader import ExcelDataReader

    file_bytes = (datadir / "sample.xlsx").read_bytes()
    reader = ExcelDataReader(file_bytes)
    assert reader.has_multiple_sheets() is True
    sheets = list(reader.iter_sheets())
    assert len(sheets) == 2
    sheet = sheets[0]
    assert sheet.name == "Sheet1"
    assert sheet.num_columns == 2
    assert sheet.column_headers == ["name", "age"]
    assert sheet.list_sample_rows(1) == [["John", 25]]
    assert sheet.list_sample_rows(2) == [["John", 25], ["Jane", 30]]

    # These always load the full content.
    assert sheet.num_rows == 2
    assert sheet.to_ibis().to_pylist() == [
        {"name": "John", "age": 25},
        {"name": "Jane", "age": 30},
    ]

    # Try after the full content is loaded.
    assert sheet.num_columns == 2
    assert sheet.column_headers == ["name", "age"]
    assert sheet.list_sample_rows(1) == [["John", 25]]
    assert sheet.list_sample_rows(5) == [["John", 25], ["Jane", 30]]


def test_excel_data_reader_single_sheet(datadir: Path):
    from agent_platform.server.data_frames.data_reader import ExcelDataReader

    file_bytes = (datadir / "sample.xlsx").read_bytes()
    reader = ExcelDataReader(file_bytes, sheet_name="Sheet1")
    assert reader.has_multiple_sheets() is False
    sheet = next(reader.iter_sheets())
    assert sheet.name == "Sheet1"
    assert sheet.num_columns == 2
    assert sheet.column_headers == ["name", "age"]
    assert sheet.list_sample_rows(1) == [["John", 25]]
    assert sheet.list_sample_rows(2) == [["John", 25], ["Jane", 30]]

    # These always load the full content.
    assert sheet.num_rows == 2
    assert sheet.to_ibis().to_pylist() == [
        {"name": "John", "age": 25},
        {"name": "Jane", "age": 30},
    ]

    # Try after the full content is loaded.
    assert sheet.num_columns == 2
    assert sheet.column_headers == ["name", "age"]
    assert sheet.list_sample_rows(1) == [["John", 25]]
    assert sheet.list_sample_rows(5) == [["John", 25], ["Jane", 30]]


def test_ods_data_reader_single_sheet(datadir: Path, data_regression):
    from agent_platform.server.data_frames.data_reader import ExcelDataReader

    file_bytes = (datadir / "example.ods").read_bytes()
    reader = ExcelDataReader(file_bytes, sheet_name="Sheet1")
    assert reader.has_multiple_sheets() is False
    sheet = next(reader.iter_sheets())
    assert sheet.name == "Sheet1"
    assert sheet.num_columns == 16

    as_ibis = sheet.to_ibis()
    data_regression.check(as_ibis.to_pylist())
