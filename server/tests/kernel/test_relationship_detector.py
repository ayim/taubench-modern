"""Unit tests for relationship detector module."""

from agent_platform.core.payloads.data_connection import (
    ColumnInfo,
    ForeignKeyAction,
    ForeignKeyInfo,
    TableInfo,
)
from agent_platform.server.kernel.relationship_detector import (
    RelationshipDetector,
)


def create_table_info(
    name: str,
    columns: list[dict],
    primary_keys: list[str] | None = None,
    foreign_keys: list[ForeignKeyInfo] | None = None,
) -> TableInfo:
    """Helper to create TableInfo for testing."""
    column_infos = [
        ColumnInfo(
            name=col["name"],
            data_type=col.get("data_type", "integer"),
            sample_values=None,
            primary_key=col.get("primary_key", False),
            unique=None,
            description=None,
            synonyms=None,
        )
        for col in columns
    ]
    return TableInfo(
        name=name,
        database=None,
        schema=None,
        description=None,
        columns=column_infos,
        primary_keys=primary_keys or [],
        foreign_keys=foreign_keys or [],
    )


class TestRelationshipDetectorForeignKeys:
    """Test FK-based relationship detection (FR4.1)."""

    def test_detect_single_fk_relationship(self):
        """Test detecting a simple FK relationship."""
        customers = create_table_info(
            "customers",
            [{"name": "id", "data_type": "integer", "primary_key": True}],
            primary_keys=["id"],
        )

        fk = ForeignKeyInfo(
            constraint_name="fk_orders_customer",
            source_table="orders",
            source_columns=["customer_id"],
            target_table="customers",
            target_columns=["id"],
            on_delete=ForeignKeyAction.CASCADE,
            on_update=ForeignKeyAction.CASCADE,
        )

        orders = create_table_info(
            "orders",
            [
                {"name": "id", "data_type": "integer", "primary_key": True},
                {"name": "customer_id", "data_type": "integer"},
            ],
            primary_keys=["id"],
            foreign_keys=[fk],
        )

        detector = RelationshipDetector([customers, orders])
        relationships = detector._detect_from_foreign_keys()

        assert len(relationships) == 1
        rel = relationships[0]
        assert rel.left_table == "orders"
        assert rel.right_table == "customers"
        assert len(rel.relationship_columns) == 1
        assert rel.relationship_columns[0].left_column == "customer_id"
        assert rel.relationship_columns[0].right_column == "id"

    def test_detect_composite_fk_relationship(self):
        """Test detecting composite FK (multiple columns)."""
        table_a = create_table_info(
            "table_a",
            [
                {"name": "pk1", "data_type": "integer", "primary_key": True},
                {"name": "pk2", "data_type": "integer", "primary_key": True},
            ],
            primary_keys=["pk1", "pk2"],
        )

        fk = ForeignKeyInfo(
            constraint_name="fk_composite",
            source_table="table_b",
            source_columns=["col1", "col2"],
            target_table="table_a",
            target_columns=["pk1", "pk2"],
            on_delete=ForeignKeyAction.RESTRICT,
            on_update=ForeignKeyAction.RESTRICT,
        )

        table_b = create_table_info(
            "table_b",
            [
                {"name": "id", "data_type": "integer", "primary_key": True},
                {"name": "col1", "data_type": "integer"},
                {"name": "col2", "data_type": "integer"},
            ],
            primary_keys=["id"],
            foreign_keys=[fk],
        )

        detector = RelationshipDetector([table_a, table_b])
        relationships = detector._detect_from_foreign_keys()

        assert len(relationships) == 1
        rel = relationships[0]
        assert len(rel.relationship_columns) == 2

    def test_fk_to_nonexistent_table_ignored(self):
        """Test that FK to table not in model is ignored."""
        fk = ForeignKeyInfo(
            constraint_name="fk_to_external",
            source_table="orders",
            source_columns=["external_id"],
            target_table="external_table",  # Not in our model
            target_columns=["id"],
            on_delete=None,
            on_update=None,
        )

        orders = create_table_info(
            "orders",
            [{"name": "id"}, {"name": "external_id"}],
            foreign_keys=[fk],
        )

        detector = RelationshipDetector([orders])
        relationships = detector._detect_from_foreign_keys()

        assert len(relationships) == 0
