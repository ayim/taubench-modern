"""Relationship detection for semantic data models.

This module provides automatic detection of table relationships using foreign key constraints.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from structlog import get_logger

if TYPE_CHECKING:
    from agent_platform.core.payloads.data_connection import TableInfo

logger = get_logger(__name__)


@dataclass(frozen=True)
class RelationshipColumn:
    """A pair of columns that form a relationship between two tables."""

    left_column: str
    right_column: str


@dataclass
class DetectedRelationship:
    """A relationship detected automatically from foreign key constraints.

    Note: Only many_to_one relationships are currently supported.
    """

    name: str
    left_table: str
    right_table: str
    relationship_columns: list[RelationshipColumn]
    auto_detected: bool = True


class RelationshipDetector:
    """Detects relationships between tables using foreign key constraints."""

    def __init__(
        self,
        tables_with_metadata: list[TableInfo],  # From data_connection.TableInfo
    ):
        self.tables = tables_with_metadata
        self.table_by_name = {t.name: t for t in tables_with_metadata}

    def detect_all_relationships(self) -> list[DetectedRelationship]:
        """Detect all relationships using foreign key constraints.

        Returns:
            List of detected relationships from foreign key constraints
        """
        return self._detect_from_foreign_keys()

    def _detect_from_foreign_keys(self) -> list[DetectedRelationship]:
        """Detect relationships from foreign key constraints.

        Returns:
            List of relationships detected from FK constraints
        """
        relationships = []

        for table in self.tables:
            if not table.foreign_keys:
                continue

            for fk in table.foreign_keys:
                # Check if target table exists in our table set
                if fk.target_table not in self.table_by_name:
                    logger.debug(f"Skipping FK {fk.constraint_name}: target table {fk.target_table} not in model")
                    continue

                # Build relationship columns
                rel_columns = [
                    RelationshipColumn(left_column=src_col, right_column=tgt_col)
                    for src_col, tgt_col in zip(fk.source_columns, fk.target_columns, strict=False)
                ]

                relationship = DetectedRelationship(
                    name=f"{fk.source_table}_{fk.target_table}_{fk.constraint_name}",
                    left_table=fk.source_table,
                    right_table=fk.target_table,
                    relationship_columns=rel_columns,
                )
                relationships.append(relationship)

        logger.info(f"Detected {len(relationships)} relationships from foreign keys")
        return relationships
