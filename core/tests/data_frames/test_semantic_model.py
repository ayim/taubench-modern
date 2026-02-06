# Note: the test is just check if the structure can be type-checked from
# an example (using pyright).

import pytest
from pydantic import ValidationError

from agent_platform.core.semantic_data_model.types import (
    BaseTable,
    Dimension,
    Fact,
    Filter,
    LogicalTable,
    SemanticDataModel,
    TimeDimension,
)

dimension_example_1: Dimension = {
    "name": "product_category",
    "synonyms": ["item_category", "product_type"],
    "description": "The category of the product sold.",
    "expr": "cat",
    "data_type": "NUMBER",
    "unique": False,
    "sample_values": ["501", "544"],
}

dimension_example_2: Dimension = {
    "name": "store_country",
    "description": "The country where the sale took place.",
    "expr": "cntry",
    "data_type": "TEXT",
    "unique": False,
    "sample_values": ["USA", "GBR"],
}

dimension_example_3: Dimension = {
    "name": "sales_channel",
    "synonyms": ["channel", "distribution_channel"],
    "description": "The channel through which the sale was made.",
    "expr": "chn",
    "data_type": "TEXT",
    "unique": False,
    "sample_values": ["FB", "GOOGLE"],
}


dimensions_example: list[Dimension] = [
    dimension_example_1,
    dimension_example_2,
    dimension_example_3,
]

base_table_example: BaseTable = {
    "database": "sales",
    "schema": "public",
    "table": "sd_data",
}

time_dimensions_example: list[TimeDimension] = [
    {
        "name": "sale_timestamp",
        "synonyms": ["time_of_sale", "transaction_time"],
        "description": "The time when the sale occurred. In UTC.",
        "expr": "dt",
        "data_type": "TIMESTAMP",
        "unique": False,
    }
]

facts_example: list[Fact] = [
    {
        "name": "sales_amount",
        "synonyms": ["revenue", "total_sales"],
        "description": "The total amount of money generated from the sale.",
        "expr": "amt",
        "data_type": "NUMBER",
    },
    {
        "name": "sales_tax",
        "description": "The sales tax paid for this sale.",
        "expr": "amt * 0.0975",
        "data_type": "NUMBER",
    },
    {
        "name": "units_sold",
        "synonyms": ["quantity_sold", "number_of_units"],
        "description": "The number of units sold in the transaction.",
        "expr": "unts",
        "data_type": "NUMBER",
    },
    {
        "name": "cost",
        "description": "The cost of the product sold.",
        "expr": "cst",
        "data_type": "NUMBER",
    },
    {
        "name": "profit",
        "synonyms": ["earnings", "net income"],
        "description": "The profit generated from a sale.",
        "expr": "amt - cst",
        "data_type": "NUMBER",
    },
]

filter_example_1: Filter = {
    "name": "north_america",
    "synonyms": ["North America", "N.A.", "NA"],
    "description": "A filter to restrict only to north american countries",
    "expr": "cntry IN ('canada', 'mexico', 'usa')",
}

tables_example: list[LogicalTable] = [
    {
        "name": "sales_data",
        "description": """A logical table capturing daily sales information across different
             store locations and product categories.""",
        "base_table": base_table_example,
        "dimensions": dimensions_example,
        "time_dimensions": time_dimensions_example,
        "facts": facts_example,
        "filters": [
            filter_example_1,
        ],
    }
]

semantic_model_example: SemanticDataModel = SemanticDataModel.model_validate(
    {
        "name": "Sales Data",
        "description": "This semantic model can be used for asking questions over the sales data.",
        "tables": tables_example,
    }
)


def test_semantic_model_validation(data_regression):
    from agent_platform.core.semantic_data_model.validation import (
        validate_semantic_model_payload_and_extract_references,
    )

    references = validate_semantic_model_payload_and_extract_references(semantic_model_example)
    data_regression.check(references.errors)


def test_semantic_model_validation_with_empty_file_reference():
    from agent_platform.core.semantic_data_model.validation import (
        EmptyFileReference,
        validate_semantic_model_payload_and_extract_references,
    )

    # Create a new small example from scratch with an empty file reference
    semantic_model_example: SemanticDataModel = SemanticDataModel.model_validate(
        {
            "name": "Sales Data",
            "description": "This semantic model can be used for asking questions over the sales data.",
            "tables": [
                {
                    "name": "sales_data",
                    "description": (
                        "A logical table capturing daily sales information across different"
                        "store locations and product categories."
                    ),
                    "base_table": {
                        "file_reference": {
                            "thread_id": "",
                            "file_ref": "",
                            "sheet_name": "",
                        },
                        "table": "sales_data",
                    },
                    "dimensions": [
                        {
                            "name": "product_category",
                            "expr": "cat",
                            "data_type": "NUMBER",
                            "description": "The category of the product sold.",
                        },
                    ],
                    "time_dimensions": [],
                    "facts": [],
                    "filters": [],
                }
            ],
        }
    )

    references = validate_semantic_model_payload_and_extract_references(semantic_model_example)
    assert not references.errors  # no errors are expected
    assert references.tables_with_unresolved_file_references == {
        EmptyFileReference(
            logical_table_name="sales_data",
            sheet_name="",
            base_table_table="sales_data",
        )
    }


def test_semantic_model_validation_missing_name():
    """Test validation when 'name' field is missing."""
    with pytest.raises(ValidationError, match="name\\s*Field required"):
        SemanticDataModel.model_validate(
            {
                "description": "Missing name",
                "tables": [
                    {
                        "name": "sales_data",
                        "base_table": {"table": "sales_data", "data_connection_id": "conn-1"},
                        "dimensions": [],
                    }
                ],
            }
        )


def test_semantic_model_validation_empty_tables():
    """Test validation when 'tables' is an empty list."""
    from agent_platform.core.semantic_data_model.validation import (
        validate_semantic_model_payload_and_extract_references,
    )

    semantic_model: SemanticDataModel = SemanticDataModel.model_validate(
        {
            "name": "Test Model",
            "description": "Empty tables",
            "tables": [],
        }
    )

    references = validate_semantic_model_payload_and_extract_references(semantic_model)
    assert len(references.errors) == 1
    assert "'tables' or 'schemas' must be specified (and not empty)" in references.errors[0]


def test_semantic_model_validation_missing_table_name():
    """Test validation when a table is missing 'name' field."""
    data: dict = {
        "name": "Test Model",
        "tables": [
            {
                "description": "Missing name",
                "base_table": {"table": "sales_data", "data_connection_id": "conn-1"},
                "dimensions": [],
            }
        ],
    }

    with pytest.raises(ValidationError, match=r"tables\.0\.name[\s\S]*Field required"):
        SemanticDataModel.model_validate(data)


def test_semantic_model_validation_missing_base_table():
    """Test validation when a table is missing 'base_table' field."""
    # Since SemanticDataModel is now a Pydantic BaseModel with required fields,
    # missing base_table is caught at validation time by Pydantic
    with pytest.raises(ValidationError, match=r"tables\.0\.base_table[\s\S]*Field required"):
        SemanticDataModel.model_validate(
            {
                "name": "Test Model",
                "tables": [
                    {
                        "name": "sales_data",
                        "description": "Missing base_table",
                        "dimensions": [],
                    }
                ],
            }
        )


def test_semantic_model_validation_missing_base_table_table():
    """Test validation when base_table is missing 'table' field."""
    from agent_platform.core.semantic_data_model.validation import (
        validate_semantic_model_payload_and_extract_references,
    )

    semantic_model: SemanticDataModel = SemanticDataModel.model_validate(
        {
            "name": "Test Model",
            "tables": [
                {
                    "name": "sales_data",
                    "base_table": {"data_connection_id": "conn-1"},
                    "dimensions": [],
                }
            ],
        }
    )

    references = validate_semantic_model_payload_and_extract_references(semantic_model)
    assert len(references.errors) == 1
    assert "'table' must be specified" in references.errors[0], f"Error was {references.errors[0]}"


def test_semantic_model_validation_duplicate_logical_table_names():
    """Test validation when duplicate logical table names are present."""
    from agent_platform.core.semantic_data_model.validation import (
        validate_semantic_model_payload_and_extract_references,
    )

    semantic_model: SemanticDataModel = SemanticDataModel.model_validate(
        {
            "name": "Test Model",
            "tables": [
                {
                    "name": "sales_data",
                    "base_table": {"table": "real_table_1", "data_connection_id": "conn-1"},
                    "dimensions": [],
                },
                {
                    "name": "sales_data",  # Duplicate name
                    "base_table": {"table": "real_table_2", "data_connection_id": "conn-1"},
                    "dimensions": [],
                },
            ],
        }
    )

    references = validate_semantic_model_payload_and_extract_references(semantic_model)
    assert len(references.errors) == 1
    assert "referenced more than once" in references.errors[0]
    assert "sales_data" in references.errors[0]


def test_semantic_model_validation_mixed_references():
    """Test validation with mixed data connection and file references."""
    from agent_platform.core.semantic_data_model.validation import (
        validate_semantic_model_payload_and_extract_references,
    )

    semantic_model: SemanticDataModel = SemanticDataModel.model_validate(
        {
            "name": "Test Model",
            "tables": [
                {
                    "name": "sales_data_db",
                    "base_table": {
                        "table": "sales_table",
                        "data_connection_id": "conn-1",
                        "database": "mydb",
                        "schema": "public",
                    },
                    "dimensions": [{"name": "product", "expr": "product_col", "data_type": "TEXT"}],
                },
                {
                    "name": "sales_data_file",
                    "base_table": {
                        "table": "sales_file_table",
                        "file_reference": {
                            "thread_id": "thread-123",
                            "file_ref": "sales.csv",
                            "sheet_name": None,
                        },
                    },
                    "dimensions": [{"name": "amount", "expr": "amount_col", "data_type": "NUMBER"}],
                },
            ],
        }
    )

    references = validate_semantic_model_payload_and_extract_references(semantic_model)
    assert not references.errors  # Should be valid
    assert len(references.data_connection_ids) == 1
    assert "conn-1" in references.data_connection_ids
    assert len(references.file_references) == 1
    assert len(references.logical_table_name_to_connection_info) == 2


def test_semantic_model_validation_missing_data_connection_and_file_reference():
    """Test validation when base_table has neither data_connection_id nor file_reference."""
    from agent_platform.core.semantic_data_model.validation import (
        validate_semantic_model_payload_and_extract_references,
    )

    semantic_model: SemanticDataModel = SemanticDataModel.model_validate(
        {
            "name": "Test Model",
            "tables": [
                {
                    "name": "sales_data",
                    "base_table": {
                        "table": "sales_table",
                        # Missing both data_connection_id and file_reference (means it's a data frame)
                    },
                    "dimensions": [],
                }
            ],
        }
    )

    references = validate_semantic_model_payload_and_extract_references(semantic_model)
    assert len(references.errors) == 0


def test_semantic_model_validation_unresolved_data_connection_name():
    """Test validation when data_connection_name is present but data_connection_id is not.

    This happens when an SDM is imported from a package but the referenced
    data connection does not exist in the current environment.
    """
    from agent_platform.core.semantic_data_model.validation import (
        validate_semantic_model_payload_and_extract_references,
    )

    semantic_model: SemanticDataModel = SemanticDataModel.model_validate(
        {
            "name": "Test Model",
            "tables": [
                {
                    "name": "sales_data",
                    "base_table": {
                        "table": "sales_table",
                        # data_connection_name is present but data_connection_id is not
                        # This simulates an unresolved connection from package import
                        "data_connection_name": "postgres-spar",
                    },
                    "dimensions": [
                        {"name": "product", "expr": "product_col", "data_type": "TEXT"},
                    ],
                }
            ],
        }
    )

    references = validate_semantic_model_payload_and_extract_references(semantic_model)

    # Should have exactly one error for the unresolved connection
    assert len(references.errors) == 1
    assert "postgres-spar" in references.errors[0]
    assert "not found" in references.errors[0]
    assert "sales_data" in references.errors[0]

    # Check the structured error has the correct kind
    assert len(references._structured_errors) == 1
    error = references._structured_errors[0]
    assert error["level"] == "error"
    assert error["kind"] == "missing_data_connection"


def test_semantic_model_validation_resolved_data_connection_name():
    """Test no error when both data_connection_name and data_connection_id are present.

    When the connection is successfully resolved, both fields may be present temporarily
    before data_connection_name is stripped. This should not cause errors.
    """
    from agent_platform.core.semantic_data_model.validation import (
        validate_semantic_model_payload_and_extract_references,
    )

    semantic_model: SemanticDataModel = SemanticDataModel.model_validate(
        {
            "name": "Test Model",
            "tables": [
                {
                    "name": "sales_data",
                    "base_table": {
                        "table": "sales_table",
                        # Both name and ID are present (resolved connection)
                        "data_connection_name": "postgres-spar",
                        "data_connection_id": "conn-123",
                    },
                    "dimensions": [
                        {"name": "product", "expr": "product_col", "data_type": "TEXT"},
                    ],
                }
            ],
        }
    )

    references = validate_semantic_model_payload_and_extract_references(semantic_model)

    # Should have no errors - the connection is resolved
    assert len(references.errors) == 0
    # The data_connection_id should be in the references
    assert "conn-123" in references.data_connection_ids
