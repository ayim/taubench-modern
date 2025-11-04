"""Tests for SemanticDataModelValidator using real storage and data connections."""

import sqlite3
import typing
from pathlib import Path

import pytest

if typing.TYPE_CHECKING:
    from agent_platform.core.data_connections.data_connections import DataConnection
    from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel
    from agent_platform.core.files.files import UploadedFile
    from agent_platform.server.auth.handlers import AuthedUser
    from agent_platform.server.data_frames.semantic_data_model_validator import (
        SemanticDataModelValidator,
    )
    from agent_platform.server.storage.sqlite import SQLiteStorage


class _SemanticDataModelValidatorChecker:
    """Helper class for testing SemanticDataModelValidator with real storage and data."""

    def __init__(self, sqlite_storage: "SQLiteStorage", tmpdir: Path):
        from tests.storage.sample_model_creator import SampleModelCreator

        self.sqlite_storage = sqlite_storage
        self.tmpdir = tmpdir
        self.model_creator = SampleModelCreator(sqlite_storage, tmpdir)
        self.user: AuthedUser | None = None
        self.thread = None

    async def setup(self):
        """Setup user, agent, and thread for testing."""
        from agent_platform.server.auth.handlers import AuthedUser, User

        await self.model_creator.setup()

        # Setup user and thread
        user_id = await self.model_creator.get_user_id()
        self.user = typing.cast(AuthedUser, User(user_id=user_id, sub=""))
        self.agent = await self.model_creator.obtain_sample_agent()
        self.thread = await self.model_creator.obtain_sample_thread()

    async def create_sqlite_connection_with_tables(
        self,
        tables_schema: dict[str, list[tuple[str, str]]],
        connection_name: str = "test_connection",
    ) -> "DataConnection":
        """
        Create a SQLite data connection with actual tables.

        Args:
            tables_schema: Dict mapping table_name to list of (column_name, column_type) tuples
            connection_name: Name for the data connection

        Returns:
            DataConnection with real tables
        """
        from uuid import uuid4

        # Create a unique SQLite database file
        db_file_path = Path(self.tmpdir) / f"test_db_{uuid4()}.db"

        # Create the tables in the SQLite database
        conn = sqlite3.connect(str(db_file_path))
        cursor = conn.cursor()

        for table_name, columns in tables_schema.items():
            columns_def = ", ".join([f"{col_name} {col_type}" for col_name, col_type in columns])
            cursor.execute(f"CREATE TABLE {table_name} ({columns_def})")

            # Insert a sample row for each table
            placeholders = ", ".join(["?" for _ in columns])
            sample_values = []
            for col_name, col_type in columns:
                if "INT" in col_type.upper():
                    sample_values.append(1)
                else:
                    sample_values.append(f"sample_{col_name}")
            cursor.execute(f"INSERT INTO {table_name} VALUES ({placeholders})", sample_values)

        conn.commit()
        conn.close()

        # Create the data connection
        data_connection = await self.model_creator.obtain_sample_data_connection(
            name=connection_name, db_file_path=db_file_path
        )

        return data_connection

    async def create_csv_file(
        self,
        filename: str,
        headers: list[str],
        rows: list[list[str]] | None = None,
    ) -> "UploadedFile":
        """
        Create a CSV file and upload it through storage.

        Args:
            filename: Name of the CSV file
            headers: List of column headers
            rows: Optional list of data rows

        Returns:
            UploadedFile object
        """
        import csv
        import io

        # Create CSV content
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)

        if rows:
            for row in rows:
                writer.writerow(row)
        else:
            # Add one sample row
            writer.writerow([f"sample_{h}" for h in headers])

        csv_content = output.getvalue().encode("utf-8")

        # Upload through storage
        uploaded_file = await self.model_creator.obtain_sample_file(
            file_content=csv_content,
            file_name=filename,
            mime_type="text/csv",
        )

        # Reset sample_file so we can create multiple files
        self.model_creator.sample_file = None

        return uploaded_file

    async def create_excel_file(
        self,
        filename: str,
        sheets: dict[str, list[str]],
    ) -> "UploadedFile":
        """
        Create an Excel file with multiple sheets and upload it through storage.

        Args:
            filename: Name of the Excel file
            sheets: Dict mapping sheet_name to list of column headers

        Returns:
            UploadedFile object
        """
        import io

        import pandas as pd

        # Create Excel file with multiple sheets
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:  # type: ignore[arg-type]
            for sheet_name, headers in sheets.items():
                # Create a dataframe with headers
                data = {h: [f"sample_{h}"] for h in headers}
                df = pd.DataFrame(data)
                df.to_excel(writer, sheet_name=sheet_name, index=False)

        excel_content = output.getvalue()

        # Upload through storage
        uploaded_file = await self.model_creator.obtain_sample_file(
            file_content=excel_content,
            file_name=filename,
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        # Reset sample_file so we can create multiple files
        self.model_creator.sample_file = None

        return uploaded_file

    def build_semantic_model(
        self,
        name: str,
        tables: list[dict],
        description: str = "Test semantic model",
    ) -> "SemanticDataModel":
        """Build a semantic data model payload."""
        return typing.cast(
            "SemanticDataModel",
            {
                "name": name,
                "description": description,
                "tables": tables,
            },
        )

    async def validate_model(
        self, semantic_model: "SemanticDataModel"
    ) -> "SemanticDataModelValidator":
        """Run validation and return validator."""
        from agent_platform.server.data_frames.semantic_data_model_validator import (
            SemanticDataModelValidator,
        )

        assert self.user is not None
        assert self.thread is not None

        validator = SemanticDataModelValidator(
            semantic_data_model=semantic_model,
            thread_id=self.thread.thread_id,
            storage=self.sqlite_storage,
            user=self.user,
        )
        await validator.validate()
        return validator


@pytest.fixture
async def validator_checker(sqlite_storage, tmpdir):
    """Fixture providing initialized validator checker."""
    checker = _SemanticDataModelValidatorChecker(sqlite_storage, tmpdir)
    await checker.setup()
    return checker


# ==================== Unit Tests for Helper Methods ====================


def test_add_validation_message_at_model_level(validator_checker):
    """Test adding a validation message at model level."""
    from agent_platform.server.data_frames.semantic_data_model_validator import (
        SemanticDataModelValidator,
    )

    sample_model = validator_checker.build_semantic_model(
        name="Test Model",
        tables=[
            {
                "name": "sales_data",
                "base_table": {
                    "table": "real_sales_table",
                    "data_connection_id": "conn-123",
                },
                "dimensions": [
                    {"name": "product", "expr": "product_col", "data_type": "TEXT"},
                ],
                "facts": [],
                "time_dimensions": [],
                "metrics": [],
            }
        ],
    )

    validator = SemanticDataModelValidator(
        semantic_data_model=sample_model,
        thread_id=validator_checker.thread.thread_id,
        storage=validator_checker.sqlite_storage,
        user=validator_checker.user,
    )

    validator._add_error("Model level error")

    assert len(validator._errors) == 1
    error = next(iter(validator._errors))
    assert error["message"] == "Model level error"
    assert error["level"] == "error"


def test_add_validation_message_at_table_level(validator_checker):
    """Test adding a validation message at table level."""
    from agent_platform.server.data_frames.semantic_data_model_validator import (
        SemanticDataModelValidator,
    )

    sample_model = validator_checker.build_semantic_model(
        name="Test Model",
        tables=[
            {
                "name": "sales_data",
                "base_table": {
                    "table": "real_sales_table",
                    "data_connection_id": "conn-123",
                },
                "dimensions": [
                    {"name": "product", "expr": "product_col", "data_type": "TEXT"},
                ],
                "facts": [],
                "time_dimensions": [],
                "metrics": [],
            }
        ],
    )

    validator = SemanticDataModelValidator(
        semantic_data_model=sample_model,
        thread_id=validator_checker.thread.thread_id,
        storage=validator_checker.sqlite_storage,
        user=validator_checker.user,
    )

    validator._add_error("Table level error", logical_table_name="sales_data")

    assert len(validator._errors) == 1
    validated_model = validator._validated_semantic_data_model
    assert validated_model is not None
    tables = validated_model.get("tables") or []
    sales_table = next(t for t in tables if t.get("name") == "sales_data")
    assert "errors" in sales_table
    errors = sales_table.get("errors") or []
    assert any(e["message"] == "Table level error" for e in errors)


def test_add_validation_message_at_column_level(validator_checker):
    """Test adding a validation message at column level."""
    from agent_platform.server.data_frames.semantic_data_model_validator import (
        SemanticDataModelValidator,
    )

    sample_model = validator_checker.build_semantic_model(
        name="Test Model",
        tables=[
            {
                "name": "sales_data",
                "base_table": {
                    "table": "real_sales_table",
                    "data_connection_id": "conn-123",
                },
                "dimensions": [
                    {"name": "product", "expr": "product_col", "data_type": "TEXT"},
                ],
                "facts": [],
                "time_dimensions": [],
                "metrics": [],
            }
        ],
    )

    validator = SemanticDataModelValidator(
        semantic_data_model=sample_model,
        thread_id=validator_checker.thread.thread_id,
        storage=validator_checker.sqlite_storage,
        user=validator_checker.user,
    )

    validator._add_error(
        "Column level error",
        logical_table_name="sales_data",
        logical_column_name="product",
    )

    assert len(validator._errors) == 1
    validated_model = validator._validated_semantic_data_model
    assert validated_model is not None
    tables = validated_model.get("tables") or []
    sales_table = next(t for t in tables if t.get("name") == "sales_data")
    dimensions = sales_table.get("dimensions") or []
    product_dim = next(d for d in dimensions if d.get("name") == "product")
    assert "errors" in product_dim
    errors = product_dim.get("errors") or []
    assert any(e["message"] == "Column level error" for e in errors)


def test_add_warning_vs_error(validator_checker):
    """Test adding warnings vs errors."""
    from agent_platform.server.data_frames.semantic_data_model_validator import (
        SemanticDataModelValidator,
    )

    sample_model = validator_checker.build_semantic_model(
        name="Test Model",
        tables=[],
    )

    validator = SemanticDataModelValidator(
        semantic_data_model=sample_model,
        thread_id=validator_checker.thread.thread_id,
        storage=validator_checker.sqlite_storage,
        user=validator_checker.user,
    )

    validator._add_error("This is an error")
    validator._add_warning("This is a warning")

    assert len(validator._errors) == 2
    errors_list = list(validator._errors)
    error_msg = next(e for e in errors_list if e["level"] == "error")
    warning_msg = next(e for e in errors_list if e["level"] == "warning")

    assert error_msg["message"] == "This is an error"
    assert warning_msg["message"] == "This is a warning"


def test_errors_and_warnings_properties(validator_checker):
    """Test the errors and warnings properties."""
    from agent_platform.server.data_frames.semantic_data_model_validator import (
        SemanticDataModelValidator,
    )

    sample_model = validator_checker.build_semantic_model(
        name="Test Model",
        tables=[],
    )

    validator = SemanticDataModelValidator(
        semantic_data_model=sample_model,
        thread_id=validator_checker.thread.thread_id,
        storage=validator_checker.sqlite_storage,
        user=validator_checker.user,
    )

    # Before validation, accessing properties should raise error
    with pytest.raises(ValueError, match="Validation has not been run"):
        _ = validator.errors

    with pytest.raises(ValueError, match="Validation has not been run"):
        _ = validator.warnings

    # Add mixed validation messages
    validator._add_error("Error 1")
    validator._add_error("Error 2")
    validator._add_warning("Warning 1")
    validator._add_warning("Warning 2")
    validator._add_warning("Warning 3")
    validator._validation_ran = True

    # Test errors property
    errors = validator.errors
    assert len(errors) == 2
    assert all(e["level"] == "error" for e in errors)
    assert {e["message"] for e in errors} == {"Error 1", "Error 2"}

    # Test warnings property
    warnings = validator.warnings
    assert len(warnings) == 3
    assert all(w["level"] == "warning" for w in warnings)
    assert {w["message"] for w in warnings} == {"Warning 1", "Warning 2", "Warning 3"}


def test_add_validation_message_column_without_table_raises_error(validator_checker):
    """Test that adding column error without table name raises ValueError."""
    from agent_platform.server.data_frames.semantic_data_model_validator import (
        SemanticDataModelValidator,
    )

    sample_model = validator_checker.build_semantic_model(
        name="Test Model",
        tables=[],
    )

    validator = SemanticDataModelValidator(
        semantic_data_model=sample_model,
        thread_id=validator_checker.thread.thread_id,
        storage=validator_checker.sqlite_storage,
        user=validator_checker.user,
    )

    with pytest.raises(ValueError, match="logical_table_name.*required"):
        validator._add_error("Error", logical_column_name="product")


def test_properties_before_validation_raise_error(validator_checker):
    """Test that properties raise ValueError before validation runs."""
    from agent_platform.server.data_frames.semantic_data_model_validator import (
        SemanticDataModelValidator,
    )

    sample_model = validator_checker.build_semantic_model(
        name="Test Model",
        tables=[],
    )

    validator = SemanticDataModelValidator(
        semantic_data_model=sample_model,
        thread_id=validator_checker.thread.thread_id,
        storage=validator_checker.sqlite_storage,
        user=validator_checker.user,
    )

    with pytest.raises(ValueError, match="Validation has not been run"):
        _ = validator.errors

    with pytest.raises(ValueError, match="Validation has not been run"):
        _ = validator.is_valid

    with pytest.raises(ValueError, match="Validation has not been run"):
        _ = validator.semantic_data_model_with_errors


# ==================== Data Connection Validation Tests ====================


@pytest.mark.asyncio
async def test_data_connection_validation_success(validator_checker):
    """Test successful validation with real data connection and tables."""
    # Create a real SQLite connection with tables
    data_connection = await validator_checker.create_sqlite_connection_with_tables(
        {
            "sales_table": [
                ("product_col", "TEXT"),
                ("region_col", "TEXT"),
                ("amount_col", "INTEGER"),
            ],
        }
    )

    # Build semantic model referencing real table
    semantic_model = validator_checker.build_semantic_model(
        name="Sales Model",
        tables=[
            {
                "name": "sales_data",
                "base_table": {
                    "table": "sales_table",
                    "data_connection_id": data_connection.id,
                },
                "dimensions": [
                    {"name": "product", "expr": "product_col", "data_type": "TEXT"},
                    {"name": "region", "expr": "region_col", "data_type": "TEXT"},
                ],
                "facts": [
                    {"name": "amount", "expr": "amount_col", "data_type": "INTEGER"},
                ],
                "time_dimensions": [],
                "metrics": [],
            }
        ],
    )

    validator = await validator_checker.validate_model(semantic_model)

    assert validator.is_valid
    assert len(validator.errors) == 0


@pytest.mark.asyncio
async def test_data_connection_not_found(validator_checker):
    """Test validation when data connection does not exist."""
    semantic_model = validator_checker.build_semantic_model(
        name="Test Model",
        tables=[
            {
                "name": "sales_data",
                "base_table": {
                    "table": "sales_table",
                    "data_connection_id": "non-existent-connection-id",
                },
                "dimensions": [
                    {"name": "product", "expr": "product_col", "data_type": "TEXT"},
                ],
                "facts": [],
                "time_dimensions": [],
                "metrics": [],
            }
        ],
    )

    validator = await validator_checker.validate_model(semantic_model)

    assert not validator.is_valid
    assert len(validator.errors) > 0
    error_messages = [e["message"] for e in validator.errors]
    assert any("non-existent-connection-id" in msg and "not found" in msg for msg in error_messages)


@pytest.mark.asyncio
async def test_data_connection_table_not_found(validator_checker):
    """Test validation when table does not exist in data connection."""
    # Create a real connection but reference a non-existent table
    data_connection = await validator_checker.create_sqlite_connection_with_tables(
        {
            "existing_table": [
                ("col1", "TEXT"),
            ],
        }
    )

    semantic_model = validator_checker.build_semantic_model(
        name="Test Model",
        tables=[
            {
                "name": "sales_data",
                "base_table": {
                    "table": "non_existent_table",
                    "data_connection_id": data_connection.id,
                },
                "dimensions": [
                    {"name": "product", "expr": "product_col", "data_type": "TEXT"},
                ],
                "facts": [],
                "time_dimensions": [],
                "metrics": [],
            }
        ],
    )

    validator = await validator_checker.validate_model(semantic_model)

    assert not validator.is_valid
    assert len(validator.errors) > 0
    error_messages = [e["message"] for e in validator.errors]
    assert any("non_existent_table" in msg.lower() for msg in error_messages)


@pytest.mark.asyncio
async def test_data_connection_column_not_found(validator_checker):
    """Test validation when column does not exist in table."""
    # Create a real connection with a table but without the referenced column
    data_connection = await validator_checker.create_sqlite_connection_with_tables(
        {
            "sales_table": [
                ("existing_col", "TEXT"),
            ],
        }
    )

    semantic_model = validator_checker.build_semantic_model(
        name="Test Model",
        tables=[
            {
                "name": "sales_data",
                "base_table": {
                    "table": "sales_table",
                    "data_connection_id": data_connection.id,
                },
                "dimensions": [
                    {"name": "product", "expr": "non_existent_col", "data_type": "TEXT"},
                ],
                "facts": [],
                "time_dimensions": [],
                "metrics": [],
            }
        ],
    )

    validator = await validator_checker.validate_model(semantic_model)

    assert not validator.is_valid
    assert len(validator.errors) > 0
    error_messages = [e["message"] for e in validator.errors]
    assert any("non_existent_col" in msg for msg in error_messages)


@pytest.mark.asyncio
async def test_data_connection_table_level_validation_error(validator_checker):
    """Test handling of table-level validation errors using TABLE_VALIDATION_ERROR_KEY."""

    # Create a connection with a table that has complex expressions that might fail
    data_connection = await validator_checker.create_sqlite_connection_with_tables(
        {
            "sales_table": [
                ("product_col", "TEXT"),
            ],
        }
    )

    # Create a semantic model with an invalid SQL expression at table level
    # This will cause a table-level error when DataConnectionInspector validates
    semantic_model = validator_checker.build_semantic_model(
        name="Test Model",
        tables=[
            {
                "name": "sales_data",
                "base_table": {
                    "table": "sales_table",
                    "data_connection_id": data_connection.id,
                },
                "dimensions": [
                    # Use an invalid expression that will cause SQL error
                    {"name": "product", "expr": "INVALID_SQL_FUNC()", "data_type": "TEXT"},
                ],
                "facts": [],
                "time_dimensions": [],
                "metrics": [],
            }
        ],
    )

    validator = await validator_checker.validate_model(semantic_model)

    # Should not crash and should report an error
    assert not validator.is_valid
    assert len(validator.errors) > 0


# ==================== File Reference Validation Tests ====================


@pytest.mark.asyncio
async def test_file_reference_validation_success(validator_checker):
    """Test successful validation with real CSV file."""
    # Create a real CSV file
    csv_file = await validator_checker.create_csv_file(
        filename="data.csv",
        headers=["Category", "Value"],
    )

    semantic_model = validator_checker.build_semantic_model(
        name="File Model",
        tables=[
            {
                "name": "file_data",
                "base_table": {
                    "table": "data_frame_file",
                    "file_reference": {
                        "thread_id": validator_checker.thread.thread_id,
                        "file_ref": csv_file.file_ref,
                        "sheet_name": None,
                    },
                },
                "dimensions": [
                    {"name": "category", "expr": "Category", "data_type": "TEXT"},
                ],
                "facts": [
                    {"name": "value", "expr": "Value", "data_type": "TEXT"},
                ],
                "time_dimensions": [],
                "metrics": [],
            }
        ],
    )

    validator = await validator_checker.validate_model(semantic_model)

    assert validator.is_valid
    assert len(validator.errors) == 0


@pytest.mark.asyncio
async def test_file_reference_not_found(validator_checker):
    """Test validation when file reference does not exist."""
    semantic_model = validator_checker.build_semantic_model(
        name="File Model",
        tables=[
            {
                "name": "file_data",
                "base_table": {
                    "table": "data_frame_file",
                    "file_reference": {
                        "thread_id": validator_checker.thread.thread_id,
                        "file_ref": "non_existent_file.csv",
                        "sheet_name": None,
                    },
                },
                "dimensions": [
                    {"name": "category", "expr": "Category", "data_type": "TEXT"},
                ],
                "facts": [],
                "time_dimensions": [],
                "metrics": [],
            }
        ],
    )

    validator = await validator_checker.validate_model(semantic_model)

    # Should be valid - file not found is just a warning
    assert validator.is_valid
    assert len(validator.errors) == 0

    # Should have warning for file not found
    warnings = validator.warnings
    assert len(warnings) > 0
    warning_messages = [w["message"] for w in warnings]
    assert any("non_existent_file.csv" in msg and "not found" in msg for msg in warning_messages)


@pytest.mark.asyncio
async def test_file_reference_column_not_found(validator_checker):
    """Test validation when column is not found in file."""
    # Create CSV file with specific columns
    csv_file = await validator_checker.create_csv_file(
        filename="data.csv",
        headers=["Name", "Value"],  # Note: "Category" is not here
    )

    semantic_model = validator_checker.build_semantic_model(
        name="File Model",
        tables=[
            {
                "name": "file_data",
                "base_table": {
                    "table": "data_frame_file",
                    "file_reference": {
                        "thread_id": validator_checker.thread.thread_id,
                        "file_ref": csv_file.file_ref,
                        "sheet_name": None,
                    },
                },
                "dimensions": [
                    {
                        "name": "category",
                        "expr": "Category",
                        "data_type": "TEXT",
                    },  # This doesn't exist
                ],
                "facts": [],
                "time_dimensions": [],
                "metrics": [],
            }
        ],
    )

    validator = await validator_checker.validate_model(semantic_model)

    assert not validator.is_valid
    assert len(validator.errors) > 0
    error_messages = [e["message"] for e in validator.errors]
    assert any("Category" in msg and "not found" in msg for msg in error_messages)


@pytest.mark.asyncio
async def test_file_reference_sheet_name_matching(validator_checker):
    """Test sheet name matching logic in file reference validation."""
    # Create Excel file with multiple sheets
    excel_file = await validator_checker.create_excel_file(
        filename="data.xlsx",
        sheets={
            "Sheet1": ["col1", "col2"],
            "Sheet2": ["other_col"],
        },
    )

    semantic_model = validator_checker.build_semantic_model(
        name="Excel Model",
        tables=[
            {
                "name": "sheet_table",
                "base_table": {
                    "table": "data_frame",
                    "file_reference": {
                        "thread_id": validator_checker.thread.thread_id,
                        "file_ref": excel_file.file_ref,
                        "sheet_name": "Sheet1",
                    },
                },
                "dimensions": [
                    {"name": "col1", "expr": "col1", "data_type": "TEXT"},
                ],
                "facts": [],
                "time_dimensions": [],
                "metrics": [],
            }
        ],
    )

    validator = await validator_checker.validate_model(semantic_model)

    # Should be valid - found the right sheet with the right column
    assert validator.is_valid
    assert len(validator.errors) == 0


# ==================== Edge Cases and Special Scenarios ====================


@pytest.mark.asyncio
async def test_unresolved_file_references_create_warnings(validator_checker):
    """Test that unresolved file references create warnings, not errors."""
    semantic_model = validator_checker.build_semantic_model(
        name="Model with unresolved file ref",
        tables=[
            {
                "name": "unresolved_table",
                "base_table": {
                    "table": "data_frame",
                    "file_reference": {
                        "thread_id": "",  # Empty = unresolved
                        "file_ref": "",
                        "sheet_name": None,
                    },
                },
                "dimensions": [],
                "facts": [],
                "time_dimensions": [],
                "metrics": [],
            }
        ],
    )

    validator = await validator_checker.validate_model(semantic_model)

    # Should still be valid since unresolved refs are warnings
    assert validator.is_valid
    assert len(validator.errors) == 0
    warnings = validator.warnings
    assert len(warnings) > 0
    assert any("unresolved file reference" in w["message"].lower() for w in warnings)


@pytest.mark.asyncio
async def test_validate_returns_semantic_model_with_errors(validator_checker):
    """Test that validate returns semantic model with errors attached."""
    # Create a scenario with errors (non-existent connection)
    semantic_model = validator_checker.build_semantic_model(
        name="Test Model",
        tables=[
            {
                "name": "sales_data",
                "base_table": {
                    "table": "sales_table",
                    "data_connection_id": "non-existent-id",
                },
                "dimensions": [],
                "facts": [],
                "time_dimensions": [],
                "metrics": [],
            }
        ],
    )

    validator = await validator_checker.validate_model(semantic_model)
    result = validator.semantic_data_model_with_errors

    assert "tables" in result
    assert not validator.is_valid


@pytest.mark.asyncio
async def test_multiple_validation_errors(validator_checker):
    """Test that multiple validation errors are collected properly."""
    # Create connection with one table but missing columns
    data_connection = await validator_checker.create_sqlite_connection_with_tables(
        {
            "products": [
                ("id", "INTEGER"),
            ],
        }
    )

    # Reference multiple non-existent columns
    semantic_model = validator_checker.build_semantic_model(
        name="Test Model",
        tables=[
            {
                "name": "product_data",
                "base_table": {
                    "table": "products",
                    "data_connection_id": data_connection.id,
                },
                "dimensions": [
                    {"name": "name", "expr": "product_name", "data_type": "TEXT"},
                    {"name": "category", "expr": "product_category", "data_type": "TEXT"},
                ],
                "facts": [
                    {"name": "price", "expr": "product_price", "data_type": "INTEGER"},
                ],
                "time_dimensions": [],
                "metrics": [],
            }
        ],
    )

    validator = await validator_checker.validate_model(semantic_model)

    assert not validator.is_valid
    # Should have multiple errors (one for each missing column)
    assert len(validator.errors) >= 3


@pytest.mark.asyncio
async def test_validation_with_multiple_tables(validator_checker):
    """Test validation with multiple tables in semantic model."""
    # Create connection with multiple tables
    data_connection = await validator_checker.create_sqlite_connection_with_tables(
        {
            "products": [
                ("id", "INTEGER"),
                ("name", "TEXT"),
            ],
            "orders": [
                ("id", "INTEGER"),
                ("product_id", "INTEGER"),
                ("quantity", "INTEGER"),
            ],
        }
    )

    semantic_model = validator_checker.build_semantic_model(
        name="Multi-table Model",
        tables=[
            {
                "name": "product_data",
                "base_table": {
                    "table": "products",
                    "data_connection_id": data_connection.id,
                },
                "dimensions": [
                    {"name": "product_id", "expr": "id", "data_type": "INTEGER"},
                    {"name": "product_name", "expr": "name", "data_type": "TEXT"},
                ],
                "facts": [],
                "time_dimensions": [],
                "metrics": [],
            },
            {
                "name": "order_data",
                "base_table": {
                    "table": "orders",
                    "data_connection_id": data_connection.id,
                },
                "dimensions": [
                    {"name": "order_id", "expr": "id", "data_type": "INTEGER"},
                ],
                "facts": [
                    {"name": "qty", "expr": "quantity", "data_type": "INTEGER"},
                ],
                "time_dimensions": [],
                "metrics": [],
            },
        ],
    )

    validator = await validator_checker.validate_model(semantic_model)

    assert validator.is_valid
    assert len(validator.errors) == 0


@pytest.mark.asyncio
async def test_mixed_data_connection_and_file_references(validator_checker):
    """Test validation with both data connection and file references."""
    # Create both a data connection and a CSV file
    data_connection = await validator_checker.create_sqlite_connection_with_tables(
        {
            "sales": [
                ("product", "TEXT"),
                ("amount", "INTEGER"),
            ],
        }
    )

    csv_file = await validator_checker.create_csv_file(
        filename="customers.csv",
        headers=["customer_id", "customer_name"],
    )

    semantic_model = validator_checker.build_semantic_model(
        name="Mixed Model",
        tables=[
            {
                "name": "sales_data",
                "base_table": {
                    "table": "sales",
                    "data_connection_id": data_connection.id,
                },
                "dimensions": [
                    {"name": "product", "expr": "product", "data_type": "TEXT"},
                ],
                "facts": [
                    {"name": "amount", "expr": "amount", "data_type": "INTEGER"},
                ],
                "time_dimensions": [],
                "metrics": [],
            },
            {
                "name": "customer_data",
                "base_table": {
                    "table": "data_frame_file",
                    "file_reference": {
                        "thread_id": validator_checker.thread.thread_id,
                        "file_ref": csv_file.file_ref,
                        "sheet_name": None,
                    },
                },
                "dimensions": [
                    {"name": "cust_id", "expr": "customer_id", "data_type": "TEXT"},
                    {"name": "cust_name", "expr": "customer_name", "data_type": "TEXT"},
                ],
                "facts": [],
                "time_dimensions": [],
                "metrics": [],
            },
        ],
    )

    validator = await validator_checker.validate_model(semantic_model)

    assert validator.is_valid
    assert len(validator.errors) == 0


# ==================== Optional Thread ID Tests ====================


@pytest.mark.asyncio
async def test_validation_without_thread_id_data_connections_only(validator_checker):
    """Test validation without thread_id works for data connections."""
    from agent_platform.server.data_frames.semantic_data_model_validator import (
        SemanticDataModelValidator,
    )

    # Create a real SQLite connection with tables
    data_connection = await validator_checker.create_sqlite_connection_with_tables(
        {
            "products": [
                ("product_id", "INTEGER"),
                ("product_name", "TEXT"),
            ],
        }
    )

    semantic_model = validator_checker.build_semantic_model(
        name="Data Connection Model",
        tables=[
            {
                "name": "product_data",
                "base_table": {
                    "table": "products",
                    "data_connection_id": data_connection.id,
                },
                "dimensions": [
                    {"name": "id", "expr": "product_id", "data_type": "INTEGER"},
                    {"name": "name", "expr": "product_name", "data_type": "TEXT"},
                ],
                "facts": [],
                "time_dimensions": [],
                "metrics": [],
            }
        ],
    )

    # Validate without thread_id
    validator = SemanticDataModelValidator(
        semantic_data_model=semantic_model,
        thread_id=None,  # No thread context
        storage=validator_checker.sqlite_storage,
        user=validator_checker.user,
    )
    await validator.validate()

    # Should be valid since data connections don't require thread_id
    assert validator.is_valid
    assert len(validator.errors) == 0


@pytest.mark.asyncio
async def test_validation_without_thread_id_file_references_fail(validator_checker):
    """Test that file references cannot be resolved without thread_id."""
    from agent_platform.server.data_frames.semantic_data_model_validator import (
        SemanticDataModelValidator,
    )

    # Create a CSV file in the thread
    csv_file = await validator_checker.create_csv_file(
        filename="data.csv",
        headers=["col1", "col2"],
    )

    semantic_model = validator_checker.build_semantic_model(
        name="File Model",
        tables=[
            {
                "name": "file_data",
                "base_table": {
                    "table": "data_frame_file",
                    "file_reference": {
                        "thread_id": validator_checker.thread.thread_id,
                        "file_ref": csv_file.file_ref,
                        "sheet_name": None,
                    },
                },
                "dimensions": [
                    {"name": "column1", "expr": "col1", "data_type": "TEXT"},
                ],
                "facts": [],
                "time_dimensions": [],
                "metrics": [],
            }
        ],
    )

    # Validate without thread_id
    validator = SemanticDataModelValidator(
        semantic_data_model=semantic_model,
        thread_id=None,  # No thread context
        storage=validator_checker.sqlite_storage,
        user=validator_checker.user,
    )
    await validator.validate()

    # Should be valid - file can't be resolved without thread_id is just a warning
    assert validator.is_valid
    assert len(validator.errors) == 0

    # Should have warning since file can't be resolved without thread_id
    warnings = validator.warnings
    assert len(warnings) > 0
    warning_messages = [w["message"] for w in warnings]
    assert any(
        "cannot be resolved and validated without thread ID" in msg for msg in warning_messages
    )


@pytest.mark.asyncio
async def test_validation_without_thread_id_mixed_sources(validator_checker):
    """Test validation without thread_id on mixed data sources."""
    from agent_platform.server.data_frames.semantic_data_model_validator import (
        SemanticDataModelValidator,
    )

    # Create data connection (should validate successfully)
    data_connection = await validator_checker.create_sqlite_connection_with_tables(
        {
            "sales": [
                ("amount", "INTEGER"),
            ],
        }
    )

    # Create file (should fail validation without thread_id)
    csv_file = await validator_checker.create_csv_file(
        filename="customers.csv",
        headers=["customer_name"],
    )

    semantic_model = validator_checker.build_semantic_model(
        name="Mixed Model",
        tables=[
            {
                "name": "sales_data",
                "base_table": {
                    "table": "sales",
                    "data_connection_id": data_connection.id,
                },
                "dimensions": [],
                "facts": [
                    {"name": "amount", "expr": "amount", "data_type": "INTEGER"},
                ],
                "time_dimensions": [],
                "metrics": [],
            },
            {
                "name": "customer_data",
                "base_table": {
                    "table": "data_frame_file",
                    "file_reference": {
                        "thread_id": validator_checker.thread.thread_id,
                        "file_ref": csv_file.file_ref,
                        "sheet_name": None,
                    },
                },
                "dimensions": [
                    {"name": "name", "expr": "customer_name", "data_type": "TEXT"},
                ],
                "facts": [],
                "time_dimensions": [],
                "metrics": [],
            },
        ],
    )

    # Validate without thread_id
    validator = SemanticDataModelValidator(
        semantic_data_model=semantic_model,
        thread_id=None,  # No thread context
        storage=validator_checker.sqlite_storage,
        user=validator_checker.user,
    )
    await validator.validate()

    # Should be valid - file not found without thread_id is just a warning
    assert validator.is_valid

    # Should have no errors (data connection is valid)
    errors = validator.errors
    assert len(errors) == 0

    # Should have warnings for the file reference that couldn't be resolved
    warnings = validator.warnings
    assert len(warnings) > 0
    warning_messages = [w["message"] for w in warnings]
    assert any(
        "cannot be resolved and validated without thread ID" in msg for msg in warning_messages
    )
