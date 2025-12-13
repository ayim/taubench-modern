import logging
import typing
from dataclasses import dataclass
from typing import Any

from agent_platform.core.data_frames.semantic_data_model_types import (
    CATEGORIES,
    BaseTable,
    CategoriesType,
    Dimension,
    Fact,
    LogicalTable,
    Metric,
    SemanticDataModel,
    TimeDimension,
)

DimensionTypes = Dimension | TimeDimension | Metric | Fact


log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True, unsafe_hash=True)
class KeyForBaseTable:
    database: str | None
    schema: str | None
    table: str | None

    def __str__(self) -> str:
        return f"{self.database}.{self.schema}.{self.table}"

    @classmethod
    def from_base_table(cls, base_table: BaseTable) -> "KeyForBaseTable":
        return KeyForBaseTable(
            database=base_table.get("database"),
            schema=base_table.get("schema"),
            table=base_table.get("table"),
        )


@dataclass(frozen=True, slots=True)
class ValueForBaseTable:
    table: LogicalTable


@dataclass(frozen=True, slots=True, unsafe_hash=True)
class KeyForDimension:
    key_for_base_table: KeyForBaseTable
    column_expr: str | None

    def __str__(self) -> str:
        return f"{self.key_for_base_table}.{self.column_expr}"

    @classmethod
    def from_category(cls, key_for_base_table: KeyForBaseTable, category: DimensionTypes) -> "KeyForDimension":
        return KeyForDimension(
            key_for_base_table=key_for_base_table,
            column_expr=category.get("expr"),
        )


@dataclass(frozen=True, slots=True)
class ValueForDimension:
    dimension: DimensionTypes
    category: CategoriesType
    logical_table: LogicalTable


class SemanticDataModelIndex:
    """
    Helper class to index a semantic data model for easier access.

    Note that it stores references to the original semantic data model, so that we can
    easily mutate it as needed.
    """

    def __init__(self, semantic_data_model: SemanticDataModel):
        # Index the semantic data model by the base_table information
        self.base_table_to_logical_table: dict[KeyForBaseTable, ValueForBaseTable] = {}
        self.dimension_key_to_dimension: dict[KeyForDimension, ValueForDimension] = {}

        self.logical_table_name_to_logical_table: dict[str, ValueForBaseTable] = {}
        self.table_name_and_dim_expr_to_dimension: dict[str, ValueForDimension] = {}

        tables = semantic_data_model.get("tables") or []
        for table in tables:
            logical_table_name = table.get("name")
            if not logical_table_name:
                log.critical(f"Logical table name not found in table: {table}")
                continue
            self.logical_table_name_to_logical_table[logical_table_name] = ValueForBaseTable(table=table)
            for category in CATEGORIES:
                category_items = table.get(category) or []
                for item in category_items:
                    self.table_name_and_dim_expr_to_dimension[f"{logical_table_name}.{item.get('expr')}"] = (
                        ValueForDimension(dimension=item, category=category, logical_table=table)
                    )

            base_table = table.get("base_table")
            if base_table:
                key = KeyForBaseTable.from_base_table(base_table)
                if key in self.base_table_to_logical_table:
                    log.critical(
                        f"Base table referenced more than once: {key}\n"
                        f"Previous: {self.base_table_to_logical_table[key]}\n"
                        f"New: {table}"
                    )
                else:
                    self.base_table_to_logical_table[key] = ValueForBaseTable(table=table)

                for category in CATEGORIES:
                    category_items = table.get(category) or []
                    for item in category_items:
                        category_key = KeyForDimension.from_category(key, item)
                        if category_key in self.dimension_key_to_dimension:
                            log.critical(
                                f"Dimension referencing the same column more than once:"
                                f" {category_key}\n"
                                f"Previous: {self.dimension_key_to_dimension[category_key]}\n"
                                f"New: {item}"
                            )
                        else:
                            self.dimension_key_to_dimension[category_key] = ValueForDimension(
                                dimension=item,
                                category=category,
                                logical_table=table,
                            )


def copy_synonyms_and_descriptions_from_existing_semantic_model(
    index_from: SemanticDataModelIndex, index_to: SemanticDataModelIndex
) -> list[KeyForDimension | KeyForBaseTable]:
    """
    Copy the synonyms and descriptions from the existing semantic model to the new semantic model.

    Args:
        index_from: The index of the existing semantic model.
        index_to: The index of the new semantic model.

    Returns:
        A list of keys that were found in the new semantic model but not in the existing
        semantic model.
    """

    missing_keys: list[KeyForDimension | KeyForBaseTable] = []

    # Copy synonyms and descriptions for base tables
    for key_to, value_to in index_to.base_table_to_logical_table.items():
        if key_to in index_from.base_table_to_logical_table:
            v: ValueForBaseTable = index_from.base_table_to_logical_table[key_to]
            table_from: LogicalTable = v.table
            table_to: LogicalTable = value_to.table

            # Copy name, synonyms and description from existing table to new table
            # Preserving the name is critical because logical names are used as keys in
            # tables_to_enhance and table_to_columns_to_enhance dictionaries
            if "name" in table_from:
                table_to["name"] = table_from["name"]
            if "synonyms" in table_from:
                table_to["synonyms"] = table_from["synonyms"]
            if "description" in table_from:
                table_to["description"] = table_from["description"]
        else:
            missing_keys.append(key_to)

    # Copy synonyms and descriptions for categories (dimensions, time_dimensions, metrics, facts)
    for key_to, value_to in index_to.dimension_key_to_dimension.items():
        if key_to in index_from.dimension_key_to_dimension:
            value_from: ValueForDimension = index_from.dimension_key_to_dimension[key_to]

            # Copy name, synonyms and description from existing category to new category
            # Preserving the name is critical because logical names may be used as keys
            # and existing columns not being enhanced should keep their enhanced names
            if "name" in value_from.dimension:
                value_to.dimension["name"] = value_from.dimension["name"]
            if "synonyms" in value_from.dimension:
                value_to.dimension["synonyms"] = value_from.dimension["synonyms"]
            if "description" in value_from.dimension:
                value_to.dimension["description"] = value_from.dimension["description"]

            if value_from.category != value_to.category:
                # We need to recategorize (put it in the proper category)

                curr_dimension = value_to.logical_table.get(value_to.category)
                if curr_dimension:
                    curr_dimension.remove(value_to.dimension)

                to_dimension: list[DimensionTypes] | None = value_to.logical_table.get(value_from.category)
                if not to_dimension:
                    to_dimension = []
                    value_to.logical_table[value_from.category] = typing.cast(Any, to_dimension)
                to_dimension.append(value_to.dimension)
        else:
            missing_keys.append(key_to)

    return missing_keys
