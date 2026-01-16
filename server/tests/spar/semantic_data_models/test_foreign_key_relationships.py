"""
Foreign Key Relationship Detection Tests

Tests that semantic data model generation correctly detects and represents
foreign key relationships, including both single-column and composite foreign keys.

These tests verify that the FK inspector and relationship detector produce
correct 1:1 column mappings for composite keys.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from agent_platform.orchestrator.agent_server_client import AgentServerClient

    from agent_platform.core.data_connections import DataConnection

pytestmark = [pytest.mark.spar, pytest.mark.semantic_data_models]


def _get_schema_from_data_connection(data_connection: DataConnection) -> str | None:
    """Extract schema from data connection configuration."""
    return getattr(data_connection.configuration, "schema", None)


class TestSingleColumnForeignKeys:
    """Tests for single-column foreign key detection."""

    @pytest.fixture(autouse=True)
    def skip_non_fk_engines(self, engine: str) -> None:
        """Skip engines that don't enforce/return FK constraints."""
        if engine not in ("postgres", "mysql"):
            pytest.skip(f"{engine} does not return FK constraint information")

    def test_single_column_fk_detected(
        self,
        agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
        openai_api_key: str,
    ) -> None:
        """
        Test that single-column FKs from schema.sql are detected correctly.

        Schema has: orders.customer_id -> customers.id
        Expected relationship_columns: [{"left_column": "customer_id", "right_column": "id"}]
        """
        from agent_platform.core.payloads.semantic_data_model_payloads import (
            DataConnectionInfo,
            GenerateSemanticDataModelPayload,
        )

        client, data_connection = agent_server_client_with_data_connection

        assert data_connection.id is not None

        # Get the schema from the data connection configuration
        schema = _get_schema_from_data_connection(data_connection)

        # Inspect only the tables needed for this test
        # Must include schema so FK inspector looks in the correct schema
        inspect_response = client.inspect_data_connection(
            connection_id=data_connection.id,
            tables_to_inspect=[
                {"name": "customers", "database": None, "schema": schema, "columns_to_inspect": None},
                {"name": "orders", "database": None, "schema": schema, "columns_to_inspect": None},
            ],
        )

        # Create a test agent (AgentServerClient tracks and cleans up created agents automatically)
        agent_id = client.create_agent_and_return_agent_id(
            name="FK Test Agent",
            action_packages=[],
            platform_configs=[{"kind": "openai", "openai_api_key": openai_api_key}],
            runbook="Test agent for FK detection.",
        )

        # Generate semantic data model
        payload = GenerateSemanticDataModelPayload(
            name="single_fk_test_model",
            description="Test model for single-column FK detection",
            data_connections_info=[
                DataConnectionInfo(
                    data_connection_id=data_connection.id,
                    tables_info=inspect_response["tables"],
                ),
            ],
            files_info=[],
            agent_id=agent_id,
        )

        result = client.generate_semantic_data_model(payload.model_dump())

        assert result is not None
        assert "semantic_model" in result

        semantic_model = result["semantic_model"]
        relationships = semantic_model.get("relationships", [])

        # Find the orders->customers relationship
        orders_customers_rel = None
        for rel in relationships:
            left_table = rel.get("left_table", "")
            right_table = rel.get("right_table", "")
            # Relationship could be in either direction
            if ("orders" in left_table and "customers" in right_table) or (
                "customers" in left_table and "orders" in right_table
            ):
                orders_customers_rel = rel
                break

        assert orders_customers_rel is not None, (
            f"Expected relationship between orders and customers not found. Available relationships: {relationships}"
        )

        # Verify it's a single-column relationship
        rel_columns = orders_customers_rel.get("relationship_columns", [])
        assert len(rel_columns) == 1, f"Expected 1 column pair, got {len(rel_columns)}: {rel_columns}"

        # Verify correct column mapping
        col_pair = rel_columns[0]
        column_names = {col_pair.get("left_column"), col_pair.get("right_column")}
        assert "customer_id" in column_names or "id" in column_names, (
            f"Expected customer_id or id in relationship columns, got: {col_pair}"
        )


class TestCompositeForeignKeys:
    """Tests for composite (multi-column) foreign key detection."""

    @pytest.fixture(autouse=True)
    def skip_non_fk_engines(self, engine: str) -> None:
        """Skip engines that don't enforce/return FK constraints."""
        if engine not in ("postgres", "mysql"):
            pytest.skip(f"{engine} does not return FK constraint information")

    def test_composite_fk_columns_detected(
        self,
        agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
        openai_api_key: str,
    ) -> None:
        """
        Test that composite FKs produce correct 1:1 column pairings.

        Schema has: stores.(country_code, region_code) -> regions.(country_code, region_code)

        Expected relationship_columns:
            [
                {"left_column": "country_code", "right_column": "country_code"},
                {"left_column": "region_code", "right_column": "region_code"}
            ]

        """
        from agent_platform.core.payloads.semantic_data_model_payloads import (
            DataConnectionInfo,
            GenerateSemanticDataModelPayload,
        )

        client, data_connection = agent_server_client_with_data_connection

        assert data_connection.id is not None

        # Get the schema from the data connection configuration
        schema = _get_schema_from_data_connection(data_connection)

        # Inspect the composite FK tables
        # Must include schema so FK inspector looks in the correct schema
        inspect_response = client.inspect_data_connection(
            connection_id=data_connection.id,
            tables_to_inspect=[
                {"name": "regions", "database": None, "schema": schema, "columns_to_inspect": None},
                {"name": "stores", "database": None, "schema": schema, "columns_to_inspect": None},
            ],
        )

        # Verify tables were found (composite_fk_schema.sql was loaded)
        table_names = [t["name"] for t in inspect_response.get("tables", [])]
        if "regions" not in table_names or "stores" not in table_names:
            pytest.skip("Composite FK test tables (regions, stores) not found in database")

        # Create a test agent (AgentServerClient tracks and cleans up created agents automatically)
        agent_id = client.create_agent_and_return_agent_id(
            name="Composite FK Test Agent",
            action_packages=[],
            platform_configs=[{"kind": "openai", "openai_api_key": openai_api_key}],
            runbook="Test agent for composite FK detection.",
        )

        # Generate semantic data model
        payload = GenerateSemanticDataModelPayload(
            name="composite_fk_test_model",
            description="Test model for composite FK detection",
            data_connections_info=[
                DataConnectionInfo(
                    data_connection_id=data_connection.id,
                    tables_info=inspect_response["tables"],
                ),
            ],
            files_info=[],
            agent_id=agent_id,
        )

        result = client.generate_semantic_data_model(payload.model_dump())

        assert result is not None
        assert "semantic_model" in result

        semantic_model = result["semantic_model"]
        relationships = semantic_model.get("relationships", [])

        # Find the stores->regions relationship
        stores_regions_rel = None
        for rel in relationships:
            left_table = rel.get("left_table", "")
            right_table = rel.get("right_table", "")
            if ("stores" in left_table and "regions" in right_table) or (
                "regions" in left_table and "stores" in right_table
            ):
                stores_regions_rel = rel
                break

        assert stores_regions_rel is not None, (
            f"Expected relationship between stores and regions not found. Available relationships: {relationships}"
        )

        # Verify it's a 2-column composite relationship
        rel_columns = stores_regions_rel.get("relationship_columns", [])
        assert len(rel_columns) == 2, (
            f"Expected exactly 2 column pairs for composite FK, got {len(rel_columns)}. "
            f"This may indicate a Cartesian product bug. Columns: {rel_columns}"
        )

        # Verify correct 1:1 column mappings
        # Extract the column pairs as sets for easier comparison
        column_pairs = {(col.get("left_column"), col.get("right_column")) for col in rel_columns}

        # The mapping should be: country_code->country_code, region_code->region_code
        expected_pairs = {("country_code", "country_code"), ("region_code", "region_code")}

        assert column_pairs == expected_pairs, (
            f"Expected correct 1:1 column pairing for composite FK. "
            f"Got: {rel_columns}. "
            f"Expected pairs like: country_code<->country_code, region_code<->region_code"
        )

        # Additional check: ensure no cross-mappings (Cartesian product symptom)
        for col in rel_columns:
            left = col.get("left_column", "")
            right = col.get("right_column", "")
            # country_code should map to country_code, not region_code
            if "country" in left:
                assert "country" in right, f"Incorrect mapping: {left} -> {right}"
            if "region" in left:
                assert "region" in right, f"Incorrect mapping: {left} -> {right}"
