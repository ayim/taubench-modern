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

base_table_example: BaseTable = {"database": "sales", "schema": "public", "table": "sd_data"}

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
