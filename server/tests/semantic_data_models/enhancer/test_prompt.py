"""Unit tests for semantic data model enhancer prompts."""


def _get_example_semantic_model():
    """Get an example semantic model for testing prompts."""
    from agent_platform.core.data_frames.semantic_data_model_types import (
        BaseTable,
        Dimension,
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

    tables_example: list[LogicalTable] = [
        {
            "name": "sales_data",
            "description": """A logical table capturing daily sales information across different
                store locations and product categories.""",
            "base_table": base_table_example,
            "dimensions": [dimension_example_1, dimension_example_2],
            "time_dimensions": time_dimensions_example,
            "facts": [],
            "filters": [],
        }
    ]

    semantic_model_example: SemanticDataModel = SemanticDataModel.model_validate(
        {
            "name": "Sales Data",
            "description": "This semantic model can be used for asking questions over the sales data.",
            "tables": tables_example,
        }
    )

    return semantic_model_example


def _get_example_semantic_model_with_two_tables():
    """Get an example semantic model with two tables for testing mixed mode prompts."""
    from agent_platform.core.data_frames.semantic_data_model_types import (
        BaseTable,
        Dimension,
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

    base_table_example_1: BaseTable = {
        "database": "sales",
        "schema": "public",
        "table": "sd_data",
    }

    base_table_example_2: BaseTable = {
        "database": "inventory",
        "schema": "public",
        "table": "inv_data",
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

    tables_example: list[LogicalTable] = [
        {
            "name": "sales_data",
            "description": """A logical table capturing daily sales information across different
                store locations and product categories.""",
            "base_table": base_table_example_1,
            "dimensions": [dimension_example_1, dimension_example_2],
            "time_dimensions": time_dimensions_example,
            "facts": [],
            "filters": [],
        },
        {
            "name": "inventory_data",
            "description": "A logical table tracking inventory levels across warehouses.",
            "base_table": base_table_example_2,
            "dimensions": [
                {
                    "name": "warehouse_id",
                    "description": "Unique identifier for the warehouse.",
                    "expr": "wh_id",
                    "data_type": "TEXT",
                    "unique": False,
                    "sample_values": ["WH001", "WH002"],
                }
            ],
            "time_dimensions": [],
            "facts": [],
            "filters": [],
        },
    ]

    semantic_model_example: SemanticDataModel = SemanticDataModel.model_validate(
        {
            "name": "Sales and Inventory Data",
            "description": ("This semantic model can be used for asking questions over sales and inventory data."),
            "tables": tables_example,
        }
    )

    return semantic_model_example


def test_system_prompt_full_mode(file_regression):
    """Test the system prompt for full enhancement mode."""
    from agent_platform.server.semantic_data_models.enhancer.strategies import create_strategy_from_mode

    semantic_model = _get_example_semantic_model()

    strategy = create_strategy_from_mode(
        semantic_model,
        "full",
        None,
        None,
    )

    prompt = strategy.system_prompt()
    file_regression.check(prompt, basename="system_prompt_full_mode")


def test_system_prompt_tables_mode_single(file_regression):
    """Test the system prompt for tables enhancement mode (single table)."""
    from agent_platform.server.semantic_data_models.enhancer.strategies import create_strategy_from_mode

    semantic_model = _get_example_semantic_model()
    strategy = create_strategy_from_mode(
        semantic_model,
        "tables",
        {"sales_data"},
        None,
    )
    prompt = strategy.system_prompt()
    file_regression.check(prompt, basename="system_prompt_tables_mode_single")


def test_system_prompt_tables_mode_multiple(file_regression):
    """Test the system prompt for tables enhancement mode (multiple tables)."""
    from agent_platform.server.semantic_data_models.enhancer.strategies import create_strategy_from_mode

    semantic_model = _get_example_semantic_model_with_two_tables()
    strategy = create_strategy_from_mode(
        semantic_model,
        "tables",
        {"sales_data", "inventory_data"},
        None,
    )
    prompt = strategy.system_prompt()
    file_regression.check(prompt, basename="system_prompt_tables_mode_multiple")


def test_system_prompt_columns_mode_single(file_regression):
    """Test the system prompt for columns enhancement mode (single column)."""
    from agent_platform.server.semantic_data_models.enhancer.strategies import create_strategy_from_mode

    semantic_model = _get_example_semantic_model()
    strategy = create_strategy_from_mode(
        semantic_model,
        "columns",
        None,
        {"sales_data": ["product_category"]},
    )
    prompt = strategy.system_prompt()
    file_regression.check(prompt, basename="system_prompt_columns_mode_single")


def test_system_prompt_columns_mode_multiple(file_regression):
    """Test the system prompt for columns enhancement mode (multiple columns)."""
    from agent_platform.server.semantic_data_models.enhancer.strategies import create_strategy_from_mode

    semantic_model = _get_example_semantic_model()
    strategy = create_strategy_from_mode(
        semantic_model,
        "columns",
        None,
        {"sales_data": ["product_category", "store_country"]},
    )
    prompt = strategy.system_prompt()
    file_regression.check(prompt, basename="system_prompt_columns_mode_multiple")


def test_user_prompt_full_mode(file_regression):
    """Test the user prompt for full enhancement mode."""
    from agent_platform.server.semantic_data_models.enhancer.strategies import create_strategy_from_mode
    from agent_platform.server.semantic_data_models.enhancer.type_defs import (
        create_semantic_data_model_for_llm_from_semantic_data_model,
    )

    semantic_model = _get_example_semantic_model()
    model_for_llm = create_semantic_data_model_for_llm_from_semantic_data_model(semantic_model)

    strategy = create_strategy_from_mode(
        semantic_model,
        "full",
        None,
        None,
    )
    prompt = strategy.user_prompt(
        current_semantic_model=model_for_llm,
        data_connection_tables=None,
    )
    file_regression.check(prompt, basename="user_prompt_full_mode")


def test_user_prompt_full_mode_with_selection(file_regression):
    """Test the user prompt for full enhancement mode with specific table/column selection."""
    from agent_platform.server.semantic_data_models.enhancer.strategies import create_strategy_from_mode
    from agent_platform.server.semantic_data_models.enhancer.type_defs import (
        create_semantic_data_model_for_llm_from_semantic_data_model,
    )

    semantic_model = _get_example_semantic_model()
    model_for_llm = create_semantic_data_model_for_llm_from_semantic_data_model(semantic_model)

    strategy = create_strategy_from_mode(
        semantic_model,
        "full",
        {"sales_data"},
        {"sales_data": ["product_category"]},
    )
    prompt = strategy.user_prompt(
        current_semantic_model=model_for_llm,
        data_connection_tables=None,
    )
    file_regression.check(prompt, basename="user_prompt_full_mode_with_selection")


def test_user_prompt_full_mode_mixed_selection(file_regression):
    """Test the user prompt for full enhancement mode with mixed selection: two tables, one with columns."""
    from agent_platform.server.semantic_data_models.enhancer.strategies import create_strategy_from_mode
    from agent_platform.server.semantic_data_models.enhancer.type_defs import (
        create_semantic_data_model_for_llm_from_semantic_data_model,
    )

    semantic_model = _get_example_semantic_model_with_two_tables()
    model_for_llm = create_semantic_data_model_for_llm_from_semantic_data_model(semantic_model)

    strategy = create_strategy_from_mode(
        semantic_model,
        "full",
        {"sales_data", "inventory_data"},
        {"sales_data": ["product_category", "store_country"]},
    )
    prompt = strategy.user_prompt(
        current_semantic_model=model_for_llm,
        data_connection_tables=None,
    )
    file_regression.check(prompt, basename="user_prompt_full_mode_mixed_selection")


def test_user_prompt_tables_mode(file_regression):
    """Test the user prompt for tables enhancement mode."""
    from agent_platform.server.semantic_data_models.enhancer.strategies import create_strategy_from_mode
    from agent_platform.server.semantic_data_models.enhancer.type_defs import (
        create_semantic_data_model_for_llm_from_semantic_data_model,
    )

    semantic_model = _get_example_semantic_model()
    model_for_llm = create_semantic_data_model_for_llm_from_semantic_data_model(semantic_model)

    strategy = create_strategy_from_mode(
        semantic_model,
        "tables",
        {"sales_data"},
        None,
    )
    prompt = strategy.user_prompt(
        current_semantic_model=model_for_llm,
        data_connection_tables=None,
    )
    file_regression.check(prompt, basename="user_prompt_tables_mode")


def test_user_prompt_columns_mode(file_regression):
    """Test the user prompt for columns enhancement mode."""
    from agent_platform.server.semantic_data_models.enhancer.strategies import create_strategy_from_mode
    from agent_platform.server.semantic_data_models.enhancer.type_defs import (
        create_semantic_data_model_for_llm_from_semantic_data_model,
    )

    semantic_model = _get_example_semantic_model()
    model_for_llm = create_semantic_data_model_for_llm_from_semantic_data_model(semantic_model)

    strategy = create_strategy_from_mode(
        semantic_model,
        "columns",
        None,
        {"sales_data": ["product_category", "store_country"]},
    )
    prompt = strategy.user_prompt(
        current_semantic_model=model_for_llm,
        data_connection_tables=None,
    )
    file_regression.check(prompt, basename="user_prompt_columns_mode")
