"""Semantic data model types, utilities, and validation.

This module contains the core types and utilities for working with
semantic data models, which describe collections of database tables
with their relationships and metadata.
"""

from agent_platform.core.semantic_data_model.types import (
    # Enums
    CATEGORIES,
    # Type aliases
    QUERY_PARAMETER_TYPE_TO_PYTHON,
    # TypedDicts
    BaseTable,
    CategoriesType,
    CortexSearchService,
    DataConnectionSnapshotMetadata,
    Dimension,
    Fact,
    FileReference,
    FileSnapshotMetadata,
    Filter,
    InputDataConnectionSnapshot,
    LogicalTable,
    Metric,
    PrimaryKey,
    # Pydantic models
    QueryParameter,
    QueryParameterDataType,
    Relationship,
    RelationshipColumn,
    SampleValue,
    SemanticDataModel,
    SemanticDataModelMetadata,
    TimeDimension,
    ValidationMessage,
    ValidationMessageKind,
    ValidationMessageLevel,
    VerifiedQuery,
    # Exceptions
    VerifiedQueryNameError,
    VerifiedQueryNLQError,
    VerifiedQueryParameterError,
    VerifiedQuerySQLError,
    # Dataclasses
    VerifiedQueryValidationContext,
    VerifiedQueryValidationError,
)
from agent_platform.core.semantic_data_model.utils import (
    extract_missing_parameters,
    extract_parameters_from_sql,
)
from agent_platform.core.semantic_data_model.validation import (
    DataConnectionInfo,
    DataFrameConnectionInfo,
    EmptyFileReference,
    FileConnectionInfo,
    References,
    validate_semantic_model_payload_and_extract_references,
)

__all__ = [
    # Types module exports
    "CATEGORIES",
    "QUERY_PARAMETER_TYPE_TO_PYTHON",
    "BaseTable",
    "CategoriesType",
    "CortexSearchService",
    # Validation module exports
    "DataConnectionInfo",
    "DataConnectionSnapshotMetadata",
    "DataFrameConnectionInfo",
    "Dimension",
    "EmptyFileReference",
    "Fact",
    "FileConnectionInfo",
    "FileReference",
    "FileSnapshotMetadata",
    "Filter",
    "InputDataConnectionSnapshot",
    "LogicalTable",
    "Metric",
    "PrimaryKey",
    "QueryParameter",
    "QueryParameterDataType",
    "References",
    "Relationship",
    "RelationshipColumn",
    "SampleValue",
    "SemanticDataModel",
    "SemanticDataModelMetadata",
    "TimeDimension",
    "ValidationMessage",
    "ValidationMessageKind",
    "ValidationMessageLevel",
    "VerifiedQuery",
    "VerifiedQueryNLQError",
    "VerifiedQueryNameError",
    "VerifiedQueryParameterError",
    "VerifiedQuerySQLError",
    "VerifiedQueryValidationContext",
    "VerifiedQueryValidationError",
    # Utils module exports
    "extract_missing_parameters",
    "extract_parameters_from_sql",
    "validate_semantic_model_payload_and_extract_references",
]
