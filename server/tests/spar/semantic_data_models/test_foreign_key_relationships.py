"""
Foreign Key Relationship Detection Tests

Tests that the ForeignKeyInspector correctly extracts foreign key metadata
from database catalogs, including both single-column and composite foreign keys.

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from agent_platform.core.data_connections import DataConnection
    from agent_platform.core.payloads.data_connection import TableToInspect

pytestmark = [pytest.mark.spar, pytest.mark.semantic_data_models]


def _get_schema_from_data_connection(data_connection: DataConnection) -> str | None:
    """Extract schema from data connection configuration."""
    return getattr(data_connection.configuration, "schema", None)


async def _create_ibis_connection_for_data_connection(data_connection: DataConnection):
    """Create an Ibis connection for testing FK inspector."""
    from agent_platform.server.kernel.data_connection_inspector import DataConnectionInspector

    return await DataConnectionInspector.create_ibis_connection(data_connection)


class TestSingleColumnForeignKeys:
    """Tests for single-column foreign key detection."""

    @pytest.fixture(autouse=True)
    def skip_non_fk_engines(self, engine: str) -> None:
        """Skip engines that don't enforce/return FK constraints."""
        if engine not in ("postgres", "mysql"):
            pytest.skip(f"{engine} does not return FK constraint information")

    @pytest.mark.asyncio
    async def test_single_column_fk_detected(
        self,
        sdm_data_connection: DataConnection,
    ) -> None:
        """
        Test that single-column FKs from schema.sql are detected correctly.

        Schema has: orders.customer_id -> customers.id
        Expected FK metadata:
            - source_table: orders
            - source_columns: [customer_id]
            - target_table: customers
            - target_columns: [id]
        """
        from agent_platform.core.payloads.data_connection import TableToInspect
        from agent_platform.server.dialect import ForeignKeyInspectorFactory

        # Get schema from data connection
        schema = _get_schema_from_data_connection(sdm_data_connection)

        # Create Ibis connection
        connection = await _create_ibis_connection_for_data_connection(sdm_data_connection)

        # Create FK inspector for the engine
        fk_inspector = ForeignKeyInspectorFactory().create(sdm_data_connection.engine)

        # Inspect FK for orders and customers tables
        tables_to_inspect: list[TableToInspect] = [
            TableToInspect(name="customers", database=None, schema=schema),
            TableToInspect(name="orders", database=None, schema=schema),
        ]

        # Get foreign keys directly from inspector
        foreign_keys_map = await fk_inspector.get_foreign_keys(connection, tables_to_inspect)

        # Verify FK was detected
        assert "orders" in foreign_keys_map, f"Expected 'orders' table in FK map. Got: {list(foreign_keys_map.keys())}"
        orders_fks = foreign_keys_map["orders"]
        assert len(orders_fks) == 1, f"Expected exactly 1 FK on orders table, got {len(orders_fks)}: {orders_fks}"

        # Find the orders->customers FK
        orders_customers_fk = None
        for fk in orders_fks:
            if fk.target_table == "customers":
                orders_customers_fk = fk
                break

        assert orders_customers_fk is not None, f"Expected FK from orders to customers. Found FKs: {orders_fks}"

        # Verify single-column FK structure
        assert len(orders_customers_fk.source_columns) == 1, (
            f"Expected 1 source column, got {len(orders_customers_fk.source_columns)}: "
            f"{orders_customers_fk.source_columns}"
        )
        assert len(orders_customers_fk.target_columns) == 1, (
            f"Expected 1 target column, got {len(orders_customers_fk.target_columns)}: "
            f"{orders_customers_fk.target_columns}"
        )

        # Verify correct column mapping
        assert orders_customers_fk.source_columns[0] == "customer_id", (
            f"Expected source column 'customer_id', got '{orders_customers_fk.source_columns[0]}'"
        )
        assert orders_customers_fk.target_columns[0] == "id", (
            f"Expected target column 'id', got '{orders_customers_fk.target_columns[0]}'"
        )

        # Verify FK metadata
        assert orders_customers_fk.source_table == "orders"
        assert orders_customers_fk.target_table == "customers"
        assert orders_customers_fk.constraint_name is not None


class TestUniqueIndexForeignKeys:
    """Tests for FK detection when referencing UNIQUE INDEX instead of PRIMARY KEY.

    This reproduces the BIRD database scenario where:
    - Foreign keys reference columns with UNIQUE INDEX (not PRIMARY KEY or UNIQUE CONSTRAINT)
    - information_schema.referential_constraints.unique_constraint_name may be NULL
    - But database system catalogs (pg_catalog.pg_constraint for PostgreSQL,
      information_schema.key_column_usage for MySQL) still have complete FK metadata

    This occurs when databases are transpiled from SQLite using sqlglot,
    which may create UNIQUE INDEXes instead of UNIQUE CONSTRAINTs.
    """

    @pytest.fixture(autouse=True)
    def skip_non_fk_engines(self, engine: str) -> None:
        """Skip engines that don't enforce/return FK constraints."""
        if engine not in ("postgres", "mysql"):
            pytest.skip(f"{engine} does not return FK constraint information")

    @pytest.mark.asyncio
    async def test_fk_detection_with_unique_index_target(
        self,
        sdm_data_connection: DataConnection,
    ) -> None:
        """
        Test that FKs are detected when they reference UNIQUE INDEX (not PRIMARY KEY).

        Schema has: outlets.(country_code, territory_code) -> territories.(country_code, territory_code)
        where territories.(country_code, territory_code) has UNIQUE INDEX (not PK or UNIQUE constraint)

        This tests the BIRD database scenario where SQLite databases are transpiled to SQL databases
        and UNIQUE INDEXes are created instead of UNIQUE CONSTRAINTs.
        """
        from agent_platform.core.payloads.data_connection import TableToInspect
        from agent_platform.server.dialect import ForeignKeyInspectorFactory

        # Get schema from data connection
        schema = _get_schema_from_data_connection(sdm_data_connection)

        # Create Ibis connection
        connection = await _create_ibis_connection_for_data_connection(sdm_data_connection)

        # Create FK inspector
        fk_inspector = ForeignKeyInspectorFactory().create(sdm_data_connection.engine)

        # Inspect FK for territories and outlets tables
        tables_to_inspect: list[TableToInspect] = [
            TableToInspect(name="territories", database=None, schema=schema),
            TableToInspect(name="outlets", database=None, schema=schema),
        ]

        # Get foreign keys directly from inspector
        foreign_keys_map = await fk_inspector.get_foreign_keys(connection, tables_to_inspect)

        # Verify FK was detected - outlets table should have FKs
        assert "outlets" in foreign_keys_map, (
            "FK inspector failed to detect any foreign keys on 'outlets' table. "
            "Expected FK: outlets.(country_code, territory_code) -> territories.(country_code, territory_code). "
            f"Tables with detected FKs: {list(foreign_keys_map.keys())}"
        )

        # Verify FK was detected
        outlets_fks = foreign_keys_map["outlets"]
        assert len(outlets_fks) == 1, f"Expected exactly 1 FK on outlets table, got {len(outlets_fks)}: {outlets_fks}"

        # Find the outlets->territories FK
        outlets_territories_fk = None
        for fk in outlets_fks:
            if fk.target_table == "territories":
                outlets_territories_fk = fk
                break

        assert outlets_territories_fk is not None, (
            f"Expected FK from outlets to territories (UNIQUE INDEX target). "
            f"This indicates FK inspector failed to detect FK referencing UNIQUE INDEX. "
            f"Found FKs: {outlets_fks}"
        )

        # Verify composite (2-column) FK structure
        assert len(outlets_territories_fk.source_columns) == 2, (
            f"Expected 2 source columns for composite FK, got {len(outlets_territories_fk.source_columns)}: "
            f"{outlets_territories_fk.source_columns}"
        )
        assert len(outlets_territories_fk.target_columns) == 2, (
            f"Expected 2 target columns for composite FK, got {len(outlets_territories_fk.target_columns)}: "
            f"{outlets_territories_fk.target_columns}"
        )

        # Verify correct 1:1 column pairing (order matters for composite FKs)
        source_cols = outlets_territories_fk.source_columns
        target_cols = outlets_territories_fk.target_columns

        # Create pairs
        column_pairs = list(zip(source_cols, target_cols, strict=True))

        # Expected pairs (order may vary between (country, territory) or (territory, country))
        expected_pairs_set = {
            ("country_code", "country_code"),
            ("territory_code", "territory_code"),
        }
        actual_pairs_set = set(column_pairs)

        assert actual_pairs_set == expected_pairs_set, (
            f"Expected column pairs {expected_pairs_set}, got {actual_pairs_set}. "
            f"This indicates incorrect 1:1 column pairing in composite FK."
        )


class TestCompositeForeignKeys:
    """Tests for composite (multi-column) foreign key detection."""

    @pytest.fixture(autouse=True)
    def skip_non_fk_engines(self, engine: str) -> None:
        """Skip engines that don't enforce/return FK constraints."""
        if engine not in ("postgres", "mysql"):
            pytest.skip(f"{engine} does not return FK constraint information")

    @pytest.mark.asyncio
    async def test_composite_fk_columns_detected(
        self,
        sdm_data_connection: DataConnection,
    ) -> None:
        """
        Test that composite FKs produce correct 1:1 column pairings.

        Schema has: stores.(country_code, region_code) -> regions.(country_code, region_code)

        Expected FK metadata:
            - source_columns: [country_code, region_code]
            - target_columns: [country_code, region_code]
            (with correct 1:1 pairing by ordinal position)
        """
        from agent_platform.core.payloads.data_connection import TableToInspect
        from agent_platform.server.dialect import ForeignKeyInspectorFactory

        # Get schema from data connection
        schema = _get_schema_from_data_connection(sdm_data_connection)

        # Create Ibis connection
        connection = await _create_ibis_connection_for_data_connection(sdm_data_connection)

        # Create FK inspector
        fk_inspector = ForeignKeyInspectorFactory().create(sdm_data_connection.engine)

        # Inspect FK for regions and stores tables
        tables_to_inspect: list[TableToInspect] = [
            TableToInspect(name="regions", database=None, schema=schema),
            TableToInspect(name="stores", database=None, schema=schema),
        ]

        # Get foreign keys directly from inspector
        foreign_keys_map = await fk_inspector.get_foreign_keys(connection, tables_to_inspect)

        # Verify FK was detected - stores table should have FKs
        assert "stores" in foreign_keys_map, (
            "FK inspector failed to detect any foreign keys on 'stores' table. "
            "Expected FK: stores.(country_code, region_code) -> regions.(country_code, region_code). "
            f"Tables with detected FKs: {list(foreign_keys_map.keys())}"
        )

        # Verify FK was detected
        stores_fks = foreign_keys_map["stores"]
        assert len(stores_fks) == 1, f"Expected exactly 1 FK on stores table, got {len(stores_fks)}: {stores_fks}"

        # Find the stores->regions FK
        stores_regions_fk = None
        for fk in stores_fks:
            if fk.target_table == "regions":
                stores_regions_fk = fk
                break

        assert stores_regions_fk is not None, f"Expected FK from stores to regions. Found FKs: {stores_fks}"

        # Verify composite (2-column) FK structure
        assert len(stores_regions_fk.source_columns) == 2, (
            f"Expected 2 source columns for composite FK, got {len(stores_regions_fk.source_columns)}. "
            f"Columns: {stores_regions_fk.source_columns}"
        )
        assert len(stores_regions_fk.target_columns) == 2, (
            f"Expected 2 target columns for composite FK, got {len(stores_regions_fk.target_columns)}. "
            f"Columns: {stores_regions_fk.target_columns}"
        )

        # Verify correct 1:1 column mappings (order matters for composite FKs)
        source_cols = stores_regions_fk.source_columns
        target_cols = stores_regions_fk.target_columns

        # Create pairs by position
        column_pairs = list(zip(source_cols, target_cols, strict=True))

        # Expected pairs: country_code<->country_code, region_code<->region_code
        # Order may vary, so we check as a set
        expected_pairs_set = {
            ("country_code", "country_code"),
            ("region_code", "region_code"),
        }
        actual_pairs_set = set(column_pairs)

        assert actual_pairs_set == expected_pairs_set, (
            f"Expected correct 1:1 column pairing for composite FK. "
            f"Got: {column_pairs}. "
            f"Expected pairs: {expected_pairs_set}"
        )

        # Additional check: ensure no cross-mappings
        for src_col, tgt_col in column_pairs:
            # country_code should map to country_code, not region_code
            if "country" in src_col:
                assert "country" in tgt_col, f"Incorrect mapping: {src_col} -> {tgt_col}"
            if "region" in src_col:
                assert "region" in tgt_col, f"Incorrect mapping: {src_col} -> {tgt_col}"

    @pytest.mark.asyncio
    async def test_composite_fk_with_pk_and_unique_constraint(
        self,
        sdm_data_connection: DataConnection,
    ) -> None:
        """
        Test that composite FKs are detected when referencing a UNIQUE CONSTRAINT
        on a table that also has a separate PRIMARY KEY.

        Schema has:
            - departments table with:
                - PRIMARY KEY (dept_id)
                - UNIQUE (dept_code, region_code)
            - employees table with FK referencing the UNIQUE CONSTRAINT:
                employees.(dept_code, region_code) -> departments.(dept_code, region_code)

        This tests the scenario where the FK references a UNIQUE CONSTRAINT
        (not the PRIMARY KEY) when both exist on the parent table.
        """
        from agent_platform.core.payloads.data_connection import TableToInspect
        from agent_platform.server.dialect import ForeignKeyInspectorFactory

        # Get schema from data connection
        schema = _get_schema_from_data_connection(sdm_data_connection)

        # Create Ibis connection
        connection = await _create_ibis_connection_for_data_connection(sdm_data_connection)

        # Create FK inspector
        fk_inspector = ForeignKeyInspectorFactory().create(sdm_data_connection.engine)

        # Inspect FK for departments and employees tables
        tables_to_inspect: list[TableToInspect] = [
            TableToInspect(name="departments", database=None, schema=schema),
            TableToInspect(name="employees", database=None, schema=schema),
        ]

        # Get foreign keys directly from inspector
        foreign_keys_map = await fk_inspector.get_foreign_keys(connection, tables_to_inspect)

        # Verify FK was detected - employees table should have FKs
        assert "employees" in foreign_keys_map, (
            "FK inspector failed to detect any foreign keys on 'employees' table. "
            "Expected FK: employees.(dept_code, region_code) -> departments.(dept_code, region_code). "
            f"Tables with detected FKs: {list(foreign_keys_map.keys())}"
        )

        # Verify FK was detected
        employees_fks = foreign_keys_map["employees"]
        assert len(employees_fks) == 1, (
            f"Expected exactly 1 FK on employees table, got {len(employees_fks)}: {employees_fks}"
        )

        # Find the employees->departments FK
        employees_departments_fk = next(fk for fk in employees_fks if fk.target_table == "departments")

        assert employees_departments_fk is not None, (
            f"Expected FK from employees to departments (UNIQUE CONSTRAINT target). "
            f"This indicates FK inspector failed to detect FK referencing UNIQUE CONSTRAINT "
            f"when parent table also has a PRIMARY KEY. Found FKs: {employees_fks}"
        )

        # Verify composite (2-column) FK structure
        assert len(employees_departments_fk.source_columns) == 2, (
            f"Expected 2 source columns for composite FK, got {len(employees_departments_fk.source_columns)}: "
            f"{employees_departments_fk.source_columns}"
        )
        assert len(employees_departments_fk.target_columns) == 2, (
            f"Expected 2 target columns for composite FK, got {len(employees_departments_fk.target_columns)}: "
            f"{employees_departments_fk.target_columns}"
        )

        # Verify correct 1:1 column pairing
        source_cols = employees_departments_fk.source_columns
        target_cols = employees_departments_fk.target_columns

        # Create pairs by position
        column_pairs = list(zip(source_cols, target_cols, strict=True))

        # Expected pairs: dept_code<->dept_code, region_code<->region_code
        expected_pairs_set = {
            ("dept_code", "dept_code"),
            ("region_code", "region_code"),
        }
        actual_pairs_set = set(column_pairs)

        assert actual_pairs_set == expected_pairs_set, (
            f"Expected correct 1:1 column pairing for composite FK referencing UNIQUE CONSTRAINT. "
            f"Got: {column_pairs}. "
            f"Expected pairs: {expected_pairs_set}"
        )
