# Note: the test is just check if the structure can be type-checked from
# an example (using pyright).

from agent_platform.core.data_frames.semantic_data_model_types import (
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

semantic_model_example: SemanticDataModel = {
    "name": "Sales Data",
    "description": "This semantic model can be used for asking questions over the sales data.",
    "tables": tables_example,
}


def test_semantic_model_validation(data_regression):
    from agent_platform.core.data_frames.semantic_data_model_validation import (
        validate_semantic_model_payload_and_extract_references,
    )

    references = validate_semantic_model_payload_and_extract_references(semantic_model_example)
    data_regression.check(references.errors)


def test_semantic_model_validation_with_empty_file_reference():
    from agent_platform.core.data_frames.semantic_data_model_validation import (
        EmptyFileReference,
        validate_semantic_model_payload_and_extract_references,
    )

    # Create a new small example from scratch with an empty file reference
    semantic_model_example: SemanticDataModel = {
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
    import typing

    from agent_platform.core.data_frames.semantic_data_model_validation import (
        validate_semantic_model_payload_and_extract_references,
    )

    semantic_model: dict = {
        "description": "Missing name",
        "tables": [
            {
                "name": "sales_data",
                "base_table": {"table": "sales_data", "data_connection_id": "conn-1"},
                "dimensions": [],
            }
        ],
    }

    references = validate_semantic_model_payload_and_extract_references(
        typing.cast(SemanticDataModel, semantic_model)
    )
    assert len(references.errors) == 1
    assert "'name' must be specified" in references.errors[0]


def test_semantic_model_validation_missing_tables():
    """Test validation when 'tables' field is missing."""
    from agent_platform.core.data_frames.semantic_data_model_validation import (
        validate_semantic_model_payload_and_extract_references,
    )

    semantic_model: SemanticDataModel = {
        "name": "Test Model",
        "description": "Missing tables",
    }

    references = validate_semantic_model_payload_and_extract_references(semantic_model)
    assert len(references.errors) == 1
    assert "'tables' must be specified" in references.errors[0]


def test_semantic_model_validation_empty_tables():
    """Test validation when 'tables' is an empty list."""
    from agent_platform.core.data_frames.semantic_data_model_validation import (
        validate_semantic_model_payload_and_extract_references,
    )

    semantic_model: SemanticDataModel = {
        "name": "Test Model",
        "description": "Empty tables",
        "tables": [],
    }

    references = validate_semantic_model_payload_and_extract_references(semantic_model)
    assert len(references.errors) == 1
    assert "'tables' must be specified (and not empty)" in references.errors[0]


def test_semantic_model_validation_missing_table_name():
    """Test validation when a table is missing 'name' field."""
    import typing

    from agent_platform.core.data_frames.semantic_data_model_validation import (
        validate_semantic_model_payload_and_extract_references,
    )

    semantic_model: dict = {
        "name": "Test Model",
        "tables": [
            {
                "description": "Missing name",
                "base_table": {"table": "sales_data", "data_connection_id": "conn-1"},
                "dimensions": [],
            }
        ],
    }

    references = validate_semantic_model_payload_and_extract_references(
        typing.cast(SemanticDataModel, semantic_model)
    )
    assert len(references.errors) == 1
    assert "'name' must be specified in a semantic data model table" in references.errors[0]


def test_semantic_model_validation_missing_base_table():
    """Test validation when a table is missing 'base_table' field."""
    import typing

    from agent_platform.core.data_frames.semantic_data_model_validation import (
        validate_semantic_model_payload_and_extract_references,
    )

    semantic_model: dict = {
        "name": "Test Model",
        "tables": [
            {
                "name": "sales_data",
                "description": "Missing base_table",
                "dimensions": [],
            }
        ],
    }

    references = validate_semantic_model_payload_and_extract_references(
        typing.cast(SemanticDataModel, semantic_model)
    )
    assert len(references.errors) == 1
    assert "'base_table' must be specified" in references.errors[0]


def test_semantic_model_validation_missing_base_table_table():
    """Test validation when base_table is missing 'table' field."""
    from agent_platform.core.data_frames.semantic_data_model_validation import (
        validate_semantic_model_payload_and_extract_references,
    )

    semantic_model: SemanticDataModel = {
        "name": "Test Model",
        "tables": [
            {
                "name": "sales_data",
                "base_table": {"data_connection_id": "conn-1"},
                "dimensions": [],
            }
        ],
    }

    references = validate_semantic_model_payload_and_extract_references(semantic_model)
    assert len(references.errors) == 1
    assert "'table' must be specified" in references.errors[0]


def test_semantic_model_validation_duplicate_logical_table_names():
    """Test validation when duplicate logical table names are present."""
    from agent_platform.core.data_frames.semantic_data_model_validation import (
        validate_semantic_model_payload_and_extract_references,
    )

    semantic_model: SemanticDataModel = {
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

    references = validate_semantic_model_payload_and_extract_references(semantic_model)
    assert len(references.errors) == 1
    assert "referenced more than once" in references.errors[0]
    assert "sales_data" in references.errors[0]


def test_semantic_model_validation_mixed_references():
    """Test validation with mixed data connection and file references."""
    from agent_platform.core.data_frames.semantic_data_model_validation import (
        validate_semantic_model_payload_and_extract_references,
    )

    semantic_model: SemanticDataModel = {
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

    references = validate_semantic_model_payload_and_extract_references(semantic_model)
    assert not references.errors  # Should be valid
    assert len(references.data_connection_ids) == 1
    assert "conn-1" in references.data_connection_ids
    assert len(references.file_references) == 1
    assert len(references.logical_table_name_to_connection_info) == 2


def test_semantic_model_validation_missing_data_connection_and_file_reference():
    """Test validation when base_table has neither data_connection_id nor file_reference."""
    from agent_platform.core.data_frames.semantic_data_model_validation import (
        validate_semantic_model_payload_and_extract_references,
    )

    semantic_model: SemanticDataModel = {
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

    references = validate_semantic_model_payload_and_extract_references(semantic_model)
    assert len(references.errors) == 0
