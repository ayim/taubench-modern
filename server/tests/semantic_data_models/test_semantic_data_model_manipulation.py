from agent_platform.core.data_frames.semantic_data_model_types import CATEGORIES
from agent_platform.server.semantic_data_models.semantic_data_model_manipulation import (
    SemanticDataModelIndex,
    copy_synonyms_and_descriptions_from_existing_semantic_model,
)


def test_copy_synonyms_and_descriptions_all_matches():
    """Test copying synonyms and descriptions when all tables and categories match."""
    from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel

    # Create existing semantic model with synonyms and descriptions
    existing_semantic_model: SemanticDataModel = {
        "name": "my-semantic-model",
        "tables": [
            {
                "base_table": {"database": "db1", "schema": "schema1", "table": "table1"},
                "name": "table1",
                "synonyms": ["existing_table1", "old_table1"],
                "description": "Existing table 1 description",
                "dimensions": [
                    {
                        "name": "dim1",
                        "expr": "col1",
                        "synonyms": ["existing_dim1", "old_dim1"],
                        "description": "Existing dimension 1 description",
                    }
                ],
                "time_dimensions": [
                    {
                        "name": "time_dim1",
                        "expr": "col2",
                        "synonyms": ["existing_time_dim1", "old_time_dim1"],
                        "description": "Existing time dimension 1 description",
                    }
                ],
                "metrics": [
                    {
                        "name": "metric1",
                        "expr": "sum(col3)",
                        "synonyms": ["existing_metric1", "old_metric1"],
                        "description": "Existing metric 1 description",
                    }
                ],
                "facts": [
                    {
                        "name": "fact1",
                        "expr": "col4",
                        "synonyms": ["existing_fact1", "old_fact1"],
                        "description": "Existing fact 1 description",
                    }
                ],
            },
            {
                "base_table": {"database": "db2", "schema": "schema2", "table": "table2"},
                "name": "table2",
                "synonyms": ["existing_table2", "old_table2"],
                "description": "Existing table 2 description",
                "dimensions": [
                    {
                        "name": "dim2",
                        "expr": "col2",
                        "synonyms": ["existing_dim2", "old_dim2"],
                        "description": "Existing dimension 2 description",
                    }
                ],
                "metrics": [
                    {
                        "name": "metric2",
                        "expr": "count(col2)",
                        "synonyms": ["existing_metric2", "old_metric2"],
                        "description": "Existing metric 2 description",
                    }
                ],
            },
        ],
    }

    # Create new semantic model without synonyms and descriptions
    new_semantic_model: SemanticDataModel = {
        "name": "my-semantic-model",
        "tables": [
            {
                "base_table": {"database": "db1", "schema": "schema1", "table": "table1"},
                "name": "table1",
                "dimensions": [
                    {
                        "name": "dim1",
                        "expr": "col1",
                    }
                ],
                "time_dimensions": [
                    {
                        "name": "time_dim1",
                        "expr": "col2",
                    }
                ],
                "metrics": [
                    {
                        "name": "metric1",
                        "expr": "sum(col3)",
                    }
                ],
                "facts": [
                    {
                        "name": "fact1",
                        "expr": "col4",
                    }
                ],
            },
            {
                "base_table": {"database": "db2", "schema": "schema2", "table": "table2"},
                "name": "table2",
                "dimensions": [
                    {
                        "name": "dim2",
                        "expr": "col2",
                    }
                ],
                "metrics": [
                    {
                        "name": "metric2",
                        "expr": "count(col2)",
                    }
                ],
            },
        ],
    }

    index_from = SemanticDataModelIndex(existing_semantic_model)
    index_to = SemanticDataModelIndex(new_semantic_model)

    # Execute the function
    missing_keys = copy_synonyms_and_descriptions_from_existing_semantic_model(index_from, index_to)

    # Assert no missing keys since all match
    assert missing_keys == []

    new_index = SemanticDataModelIndex(new_semantic_model)

    # Assert that synonyms and descriptions were copied to tables
    table1 = new_index.logical_table_name_to_logical_table["table1"].table
    assert table1.get("synonyms") == ["existing_table1", "old_table1"]
    assert table1.get("description") == "Existing table 1 description"

    # Assert that synonyms and descriptions were copied to categories
    # Check dimension
    dim1 = new_index.table_name_and_dim_expr_to_dimension["table1.col1"].dimension
    assert dim1.get("synonyms") == ["existing_dim1", "old_dim1"]
    assert dim1.get("description") == "Existing dimension 1 description"
    return

    # Check time dimension
    time_dim1_key = None
    for key, category in index_to.category_to_key_for_category.items():
        if category.get("name") == "time_dim1":
            time_dim1_key = key
            break
    assert time_dim1_key is not None
    time_dim1 = index_to.category_to_key_for_category[time_dim1_key]
    assert time_dim1["synonyms"] == ["existing_time_dim1", "old_time_dim1"]
    assert time_dim1["description"] == "Existing time dimension 1 description"

    # Check metric
    metric1_key = None
    for key, category in index_to.category_to_key_for_category.items():
        if category.get("name") == "metric1":
            metric1_key = key
            break
    assert metric1_key is not None
    metric1 = index_to.category_to_key_for_category[metric1_key]
    assert metric1["synonyms"] == ["existing_metric1", "old_metric1"]
    assert metric1["description"] == "Existing metric 1 description"

    # Check fact
    fact1_key = None
    for key, category in index_to.category_to_key_for_category.items():
        if category.get("name") == "fact1":
            fact1_key = key
            break
    assert fact1_key is not None
    fact1 = index_to.category_to_key_for_category[fact1_key]
    assert fact1["synonyms"] == ["existing_fact1", "old_fact1"]
    assert fact1["description"] == "Existing fact 1 description"


def test_copy_synonyms_and_descriptions_no_matches():
    """Test copying synonyms and descriptions when no tables and categories match."""
    from agent_platform.core.data_frames.semantic_data_model_types import (
        SemanticDataModel,
    )

    # Create existing semantic model
    existing_semantic_model: SemanticDataModel = {
        "name": "my-semantic-model",
        "tables": [
            {
                "base_table": {"database": "db1", "schema": "schema1", "table": "table1"},
                "name": "table1",
                "synonyms": ["existing_table1"],
                "description": "Existing table 1 description",
                "dimensions": [
                    {
                        "name": "dim1",
                        "expr": "col1",
                        "synonyms": ["existing_dim1"],
                        "description": "Existing dimension 1 description",
                    }
                ],
                "metrics": [
                    {
                        "name": "metric1",
                        "expr": "sum(col1)",
                        "synonyms": ["existing_metric1"],
                        "description": "Existing metric 1 description",
                    }
                ],
            }
        ],
    }

    # Create new semantic model with completely different tables and categories
    new_semantic_model: SemanticDataModel = {
        "name": "my-semantic-model",
        "tables": [
            {
                "base_table": {"database": "db3", "schema": "schema3", "table": "table3"},
                "name": "table3",
                "dimensions": [
                    {
                        "name": "dim3",
                        "expr": "col3",
                    }
                ],
                "time_dimensions": [
                    {
                        "name": "time_dim3",
                        "expr": "time_col3",
                    }
                ],
                "metrics": [
                    {
                        "name": "metric3",
                        "expr": "avg(col3)",
                    }
                ],
                "facts": [
                    {
                        "name": "fact3",
                        "expr": "col4",
                    }
                ],
            },
            {
                "base_table": {"database": "db4", "schema": "schema4", "table": "table4"},
                "name": "table4",
                "dimensions": [
                    {
                        "name": "dim4",
                        "expr": "col5",
                    }
                ],
                "metrics": [
                    {
                        "name": "metric4",
                        "expr": "max(col5)",
                    }
                ],
            },
        ],
    }

    index_from = SemanticDataModelIndex(existing_semantic_model)
    index_to = SemanticDataModelIndex(new_semantic_model)

    # Execute the function
    missing_keys = copy_synonyms_and_descriptions_from_existing_semantic_model(index_from, index_to)

    # Assert that all keys are missing since none match
    assert len(missing_keys) == 8  # 2 base tables + 6 dimensions

    # Verify that the missing keys include both base table keys and category keys
    base_table_keys = [key for key in missing_keys if hasattr(key, "key_for_base_table") is False]
    category_keys = [key for key in missing_keys if hasattr(key, "key_for_base_table") is True]

    assert len(base_table_keys) == 2  # Two base tables
    assert len(category_keys) == 6  # Two categories (dimension + metric from each table)

    # Assert that no synonyms or descriptions were copied (they should remain None/empty)
    for table in new_semantic_model.get("tables") or []:
        assert "synonyms" not in table or table["synonyms"] is None
        assert "description" not in table or table["description"] is None

        for category_type in CATEGORIES:
            for category in table.get(category_type, []):
                assert "synonyms" not in category or category["synonyms"] is None
                assert "description" not in category or category["description"] is None


def test_copy_synonyms_and_descriptions_with_recategorization():
    """Test copying synonyms and descriptions when a column changes category
    (dimension to metric)."""
    from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel

    # Create existing semantic model with a dimension
    existing_semantic_model: SemanticDataModel = {
        "name": "my-semantic-model",
        "tables": [
            {
                "base_table": {"database": "db1", "schema": "schema1", "table": "table1"},
                "name": "table1",
                "synonyms": ["existing_table1"],
                "description": "Existing table 1 description",
                "dimensions": [
                    {
                        "name": "user_count",
                        "expr": "count(user_id)",
                        "synonyms": ["existing_user_count", "old_user_count"],
                        "description": "Existing user count description",
                    }
                ],
            }
        ],
    }

    # Create new semantic model where the same column is now a metric
    new_semantic_model: SemanticDataModel = {
        "name": "my-semantic-model",
        "tables": [
            {
                "base_table": {"database": "db1", "schema": "schema1", "table": "table1"},
                "name": "table1",
                "metrics": [
                    {
                        "name": "user_count",
                        "expr": "count(user_id)",
                    }
                ],
            }
        ],
    }

    index_from = SemanticDataModelIndex(existing_semantic_model)
    index_to = SemanticDataModelIndex(new_semantic_model)

    # Execute the function
    missing_keys = copy_synonyms_and_descriptions_from_existing_semantic_model(index_from, index_to)

    # Assert no missing keys since the column matches (just different category)
    assert missing_keys == []

    new_index = SemanticDataModelIndex(new_semantic_model)
    dim_value = new_index.table_name_and_dim_expr_to_dimension["table1.count(user_id)"]
    assert dim_value.dimension.get("synonyms") == ["existing_user_count", "old_user_count"]


def test_copy_preserves_table_names():
    """REGRESSION TEST: Verify that table logical names are preserved during copy - Bug fix."""
    from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel

    # Existing model with enhanced logical table name
    existing_semantic_model: SemanticDataModel = {
        "name": "my-semantic-model",
        "tables": [
            {
                "base_table": {"database": "db1", "schema": "public", "table": "customers"},
                "name": "customer_master",  # Enhanced logical name
                "synonyms": ["clients", "buyers"],
                "description": "Master customer data",
                "dimensions": [
                    {
                        "name": "customer_id",
                        "expr": "id",
                        "synonyms": ["cust_id"],
                        "description": "Unique customer identifier",
                    }
                ],
            }
        ],
    }

    # New model generated from DB with default name
    new_semantic_model: SemanticDataModel = {
        "name": "my-semantic-model",
        "tables": [
            {
                "base_table": {"database": "db1", "schema": "public", "table": "customers"},
                "name": "customers",  # Default name from generator
                "dimensions": [
                    {
                        "name": "id",
                        "expr": "id",
                    }
                ],
            }
        ],
    }

    index_from = SemanticDataModelIndex(existing_semantic_model)
    index_to = SemanticDataModelIndex(new_semantic_model)

    # Execute the function
    missing_keys = copy_synonyms_and_descriptions_from_existing_semantic_model(index_from, index_to)

    # No missing keys - table matches by base_table
    assert missing_keys == []

    # Verify the enhanced name was preserved
    updated_table = new_semantic_model["tables"][0]  # type: ignore[index]
    assert updated_table["name"] == "customer_master", (  # type: ignore[typeddict-item]
        "Table name should be preserved from existing model"
    )
    assert updated_table["synonyms"] == ["clients", "buyers"]  # type: ignore[typeddict-item]
    assert updated_table["description"] == "Master customer data"  # type: ignore[typeddict-item]


def test_copy_preserves_column_names():
    """REGRESSION TEST: Verify that column logical names are preserved during copy - Bug fix."""
    from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel

    # Existing model with enhanced logical column names
    existing_semantic_model: SemanticDataModel = {
        "name": "my-semantic-model",
        "tables": [
            {
                "base_table": {"database": "db1", "schema": "public", "table": "customers"},
                "name": "customers",
                "dimensions": [
                    {
                        "name": "customer_identifier",  # Enhanced logical name
                        "expr": "id",
                        "synonyms": ["cust_id", "customer_id"],
                        "description": "Unique customer identifier",
                    },
                    {
                        "name": "customer_full_name",  # Enhanced logical name
                        "expr": "name",
                        "synonyms": ["cust_name"],
                        "description": "Customer full name",
                    },
                ],
            }
        ],
    }

    # New model from generator with default column names
    new_semantic_model: SemanticDataModel = {
        "name": "my-semantic-model",
        "tables": [
            {
                "base_table": {"database": "db1", "schema": "public", "table": "customers"},
                "name": "customers",
                "dimensions": [
                    {
                        "name": "id",  # Default name from generator
                        "expr": "id",
                    },
                    {
                        "name": "name",  # Default name from generator
                        "expr": "name",
                    },
                ],
            }
        ],
    }

    index_from = SemanticDataModelIndex(existing_semantic_model)
    index_to = SemanticDataModelIndex(new_semantic_model)

    # Execute the function
    missing_keys = copy_synonyms_and_descriptions_from_existing_semantic_model(index_from, index_to)

    # No missing keys - columns match by base_table + expr
    assert missing_keys == []

    # Verify the enhanced names were preserved
    updated_table = new_semantic_model["tables"][0]  # type: ignore[index]
    dim1 = updated_table["dimensions"][0]  # type: ignore[typeddict-item, index]
    assert dim1["name"] == "customer_identifier", (  # type: ignore[typeddict-item]
        "Column name should be preserved from existing model"
    )
    assert dim1["synonyms"] == ["cust_id", "customer_id"]  # type: ignore[typeddict-item]
    assert dim1["description"] == "Unique customer identifier"  # type: ignore[typeddict-item]

    dim2 = updated_table["dimensions"][1]  # type: ignore[typeddict-item, index]
    assert dim2["name"] == "customer_full_name", (  # type: ignore[typeddict-item]
        "Column name should be preserved from existing model"
    )
    assert dim2["synonyms"] == ["cust_name"]  # type: ignore[typeddict-item]
    assert dim2["description"] == "Customer full name"  # type: ignore[typeddict-item]
