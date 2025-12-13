"""Unit tests for semantic data model enhancer prompts."""

import json


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

    semantic_model_example: SemanticDataModel = {
        "name": "Sales Data",
        "description": "This semantic model can be used for asking questions over the sales data.",
        "tables": tables_example,
    }

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

    semantic_model_example: SemanticDataModel = {
        "name": "Sales and Inventory Data",
        "description": ("This semantic model can be used for asking questions over sales and inventory data."),
        "tables": tables_example,
    }

    return semantic_model_example


def test_system_prompt_full_mode(file_regression):
    """Test the system prompt for full enhancement mode."""
    from agent_platform.server.semantic_data_models.enhancer.prompt_templates.system_prompt import (
        render_system_prompt,
    )

    prompt = render_system_prompt(mode="full", tables_to_enhance=None, table_to_columns_to_enhance=None)
    file_regression.check(prompt, basename="system_prompt_full_mode")


def test_system_prompt_tables_mode_single(file_regression):
    """Test the system prompt for tables enhancement mode (single table)."""
    from agent_platform.server.semantic_data_models.enhancer.prompt_templates.system_prompt import (
        render_system_prompt,
    )

    prompt = render_system_prompt(mode="tables", tables_to_enhance={"sales_data"}, table_to_columns_to_enhance=None)
    file_regression.check(prompt, basename="system_prompt_tables_mode_single")


def test_system_prompt_tables_mode_multiple(file_regression):
    """Test the system prompt for tables enhancement mode (multiple tables)."""
    from agent_platform.server.semantic_data_models.enhancer.prompt_templates.system_prompt import (
        render_system_prompt,
    )

    prompt = render_system_prompt(
        mode="tables",
        tables_to_enhance={"sales_data", "another_table"},
        table_to_columns_to_enhance=None,
    )
    file_regression.check(prompt, basename="system_prompt_tables_mode_multiple")


def test_system_prompt_columns_mode_single(file_regression):
    """Test the system prompt for columns enhancement mode (single column)."""
    from agent_platform.server.semantic_data_models.enhancer.prompt_templates.system_prompt import (
        render_system_prompt,
    )

    prompt = render_system_prompt(
        mode="columns",
        tables_to_enhance=None,
        table_to_columns_to_enhance={"sales_data": ["product_category"]},
    )
    file_regression.check(prompt, basename="system_prompt_columns_mode_single")


def test_system_prompt_columns_mode_multiple(file_regression):
    """Test the system prompt for columns enhancement mode (multiple columns)."""
    from agent_platform.server.semantic_data_models.enhancer.prompt_templates.system_prompt import (
        render_system_prompt,
    )

    prompt = render_system_prompt(
        mode="columns",
        tables_to_enhance=None,
        table_to_columns_to_enhance={"sales_data": ["product_category", "store_country"]},
    )
    file_regression.check(prompt, basename="system_prompt_columns_mode_multiple")


def test_user_prompt_full_mode(file_regression):
    """Test the user prompt for full enhancement mode."""
    from agent_platform.server.semantic_data_models.enhancer.prompt_templates.user_prompt import (
        render_user_prompt,
    )
    from agent_platform.server.semantic_data_models.enhancer.type_defs import (
        create_semantic_data_model_for_llm_from_semantic_data_model,
    )

    semantic_model = _get_example_semantic_model()
    model_for_llm = create_semantic_data_model_for_llm_from_semantic_data_model(semantic_model)

    prompt = render_user_prompt(
        mode="full",
        current_semantic_model=model_for_llm,
        tables_to_enhance=None,
        table_to_columns_to_enhance=None,
    )
    file_regression.check(prompt, basename="user_prompt_full_mode")


def test_user_prompt_full_mode_with_selection(file_regression):
    """Test the user prompt for full enhancement mode with specific table/column selection."""
    from agent_platform.server.semantic_data_models.enhancer.prompt_templates.user_prompt import (
        render_user_prompt,
    )
    from agent_platform.server.semantic_data_models.enhancer.type_defs import (
        create_semantic_data_model_for_llm_from_semantic_data_model,
    )

    semantic_model = _get_example_semantic_model()
    model_for_llm = create_semantic_data_model_for_llm_from_semantic_data_model(semantic_model)

    prompt = render_user_prompt(
        mode="full",
        current_semantic_model=model_for_llm,
        tables_to_enhance={"sales_data"},
        table_to_columns_to_enhance={"sales_data": ["product_category"]},
    )
    file_regression.check(prompt, basename="user_prompt_full_mode_with_selection")


def test_user_prompt_full_mode_mixed_selection(file_regression):
    """Test the user prompt for full enhancement mode with mixed selection: two tables, one with columns."""
    from agent_platform.server.semantic_data_models.enhancer.prompt_templates.user_prompt import (
        render_user_prompt,
    )
    from agent_platform.server.semantic_data_models.enhancer.type_defs import (
        create_semantic_data_model_for_llm_from_semantic_data_model,
    )

    semantic_model = _get_example_semantic_model_with_two_tables()
    model_for_llm = create_semantic_data_model_for_llm_from_semantic_data_model(semantic_model)

    prompt = render_user_prompt(
        mode="full",
        current_semantic_model=model_for_llm,
        tables_to_enhance={"sales_data", "inventory_data"},
        table_to_columns_to_enhance={"sales_data": ["product_category", "store_country"]},
    )
    file_regression.check(prompt, basename="user_prompt_full_mode_mixed_selection")


def test_user_prompt_tables_mode(file_regression):
    """Test the user prompt for tables enhancement mode."""
    from agent_platform.server.semantic_data_models.enhancer.prompt_templates.user_prompt import (
        render_user_prompt,
    )
    from agent_platform.server.semantic_data_models.enhancer.type_defs import (
        create_semantic_data_model_for_llm_from_semantic_data_model,
    )

    semantic_model = _get_example_semantic_model()
    model_for_llm = create_semantic_data_model_for_llm_from_semantic_data_model(semantic_model)

    prompt = render_user_prompt(
        mode="tables",
        current_semantic_model=model_for_llm,
        tables_to_enhance={"sales_data"},
        table_to_columns_to_enhance=None,
    )
    file_regression.check(prompt, basename="user_prompt_tables_mode")


def test_user_prompt_columns_mode(file_regression):
    """Test the user prompt for columns enhancement mode."""
    from agent_platform.server.semantic_data_models.enhancer.prompt_templates.user_prompt import (
        render_user_prompt,
    )
    from agent_platform.server.semantic_data_models.enhancer.type_defs import (
        create_semantic_data_model_for_llm_from_semantic_data_model,
    )

    semantic_model = _get_example_semantic_model()
    model_for_llm = create_semantic_data_model_for_llm_from_semantic_data_model(semantic_model)

    prompt = render_user_prompt(
        mode="columns",
        current_semantic_model=model_for_llm,
        tables_to_enhance=None,
        table_to_columns_to_enhance={"sales_data": ["product_category", "store_country"]},
    )
    file_regression.check(prompt, basename="user_prompt_columns_mode")


def test_quality_check_system_prompt(file_regression):
    """Test the quality check system prompt."""
    from agent_platform.server.semantic_data_models.enhancer.prompt_templates.quality_check_prompt import (
        render_quality_check_system_prompt,
    )

    prompt = render_quality_check_system_prompt()
    file_regression.check(prompt, basename="quality_check_system_prompt")


def test_quality_check_user_prompt(file_regression):
    """Test the quality check user prompt."""
    from agent_platform.server.semantic_data_models.enhancer.prompt_templates.quality_check_user_prompt import (
        render_quality_check_user_prompt,
    )

    semantic_model = _get_example_semantic_model()
    enhanced_model_json = json.dumps(semantic_model, indent=2)

    prompt = render_quality_check_user_prompt(enhanced_model_json)
    file_regression.check(prompt, basename="quality_check_user_prompt")


def test_quality_check_user_prompt_tables_mode(file_regression):
    """Test the quality check user prompt with tables mode."""
    from agent_platform.server.semantic_data_models.enhancer.prompt_templates.quality_check_user_prompt import (
        render_quality_check_user_prompt,
    )

    semantic_model = _get_example_semantic_model()
    enhanced_model_json = json.dumps(semantic_model, indent=2)

    prompt = render_quality_check_user_prompt(
        enhanced_model_json,
        mode="tables",
        tables_to_enhance={"sales_data"},
    )
    file_regression.check(prompt, basename="quality_check_user_prompt_tables_mode")


def test_quality_check_user_prompt_columns_mode(file_regression):
    """Test the quality check user prompt with columns mode."""
    from agent_platform.server.semantic_data_models.enhancer.prompt_templates.quality_check_user_prompt import (
        render_quality_check_user_prompt,
    )

    semantic_model = _get_example_semantic_model()
    enhanced_model_json = json.dumps(semantic_model, indent=2)

    prompt = render_quality_check_user_prompt(
        enhanced_model_json,
        mode="columns",
        table_to_columns_to_enhance={"sales_data": ["product_category", "store_country"]},
    )
    file_regression.check(prompt, basename="quality_check_user_prompt_columns_mode")


def test_quality_check_user_prompt_full_mode_with_tables(file_regression):
    """Test the quality check user prompt with full mode and specific tables."""
    from agent_platform.server.semantic_data_models.enhancer.prompt_templates.quality_check_user_prompt import (
        render_quality_check_user_prompt,
    )

    semantic_model = _get_example_semantic_model_with_two_tables()
    enhanced_model_json = json.dumps(semantic_model, indent=2)

    prompt = render_quality_check_user_prompt(
        enhanced_model_json,
        mode="full",
        tables_to_enhance={"sales_data", "inventory_data"},
    )
    file_regression.check(prompt, basename="quality_check_user_prompt_full_mode_with_tables")


def test_quality_check_user_prompt_full_mode_with_columns(file_regression):
    """Test the quality check user prompt with full mode and specific columns."""
    from agent_platform.server.semantic_data_models.enhancer.prompt_templates.quality_check_user_prompt import (
        render_quality_check_user_prompt,
    )

    semantic_model = _get_example_semantic_model()
    enhanced_model_json = json.dumps(semantic_model, indent=2)

    prompt = render_quality_check_user_prompt(
        enhanced_model_json,
        mode="full",
        table_to_columns_to_enhance={"sales_data": ["product_category"]},
    )
    file_regression.check(prompt, basename="quality_check_user_prompt_full_mode_with_columns")


def test_quality_check_user_prompt_full_mode_mixed(file_regression):
    """Test the quality check user prompt with full mode and mixed tables/columns selection."""
    from agent_platform.server.semantic_data_models.enhancer.prompt_templates.quality_check_user_prompt import (
        render_quality_check_user_prompt,
    )

    semantic_model = _get_example_semantic_model_with_two_tables()
    enhanced_model_json = json.dumps(semantic_model, indent=2)

    prompt = render_quality_check_user_prompt(
        enhanced_model_json,
        mode="full",
        tables_to_enhance={"inventory_data"},
        table_to_columns_to_enhance={"sales_data": ["product_category", "store_country"]},
    )
    file_regression.check(prompt, basename="quality_check_user_prompt_full_mode_mixed")
