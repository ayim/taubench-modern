from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sema4ai_docint.models.data_model import DataModel
from sema4ai_docint.utils import normalize_name
from sema4ai_docint.validation.models import ValidationRule


@dataclass(frozen=True)
class DataModelPayload:
    """Payload for the DataModel object."""

    name: str
    description: str
    schema: dict[str, Any]
    views: list[dict[str, Any]] | None = None
    quality_checks: list[dict[str, str]] | None = None
    prompt: str | None = None
    summary: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @classmethod
    def model_validate(cls, data: Any) -> DataModelPayload:
        # Defensive copy
        if isinstance(data, dict):
            obj = dict(data)
        else:
            obj = dict(getattr(data, "__dict__", {}))

        name = normalize_name(str(obj.get("name")))
        description = obj.get("description")
        schema = obj.get("schema")
        views = obj.get("views")
        quality_checks = obj.get("quality_checks")
        prompt = obj.get("prompt")
        summary = obj.get("summary")
        created_at = obj.get("created_at")
        updated_at = obj.get("updated_at")

        if not name:
            raise ValueError("DataModel.name is required")
        if not description:
            raise ValueError("DataModel.description is required")
        if not schema:
            raise ValueError("DataModel.schema is required")

        return cls(
            name=str(name),
            description=str(description),
            schema=schema,
            views=views,
            quality_checks=quality_checks,
            prompt=prompt,
            summary=summary,
            created_at=created_at,
            updated_at=updated_at,
        )

    def to_data_model(self) -> DataModel:
        return DataModel(
            name=self.name,
            description=self.description,
            model_schema=self.schema,  # Map schema to model_schema
            views=self.views,
            quality_checks=self.quality_checks,
            prompt=self.prompt,
            summary=self.summary,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


def model_to_spec_dict(model: DataModel) -> dict[str, Any]:
    """Convert internal DataModel to an API response dict using snake_case keys."""
    return {
        "name": getattr(model, "name", None),
        "description": getattr(model, "description", None),
        "schema": getattr(model, "model_schema", None),
        "views": getattr(model, "views", None),
        "quality_checks": getattr(model, "quality_checks", None),
        "prompt": getattr(model, "prompt", None),
        "summary": getattr(model, "summary", None),
        "created_at": getattr(model, "created_at", None),
        "updated_at": getattr(model, "updated_at", None),
    }


def summary_from_model(model: DataModel) -> dict[str, Any]:
    """Build DataModelSummary (name, description, schema)."""
    return {
        "name": model.name,
        "description": model.description,
        "schema": model.model_schema,
    }


@dataclass(frozen=True)
class CreateDataModelRequest:
    """Request payload for creating a data model."""

    data_model: DataModelPayload


@dataclass(frozen=True)
class PartialDataModelPayload:
    """Payload for partial updates of a DataModel (all fields optional)."""

    description: str | None = None
    schema: dict[str, Any] | None = None
    views: list[dict[str, Any]] | None = None
    quality_checks: list[dict[str, str]] | None = None
    prompt: str | None = None
    summary: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @classmethod
    def model_validate(cls, data: Any) -> PartialDataModelPayload:
        # Defensive copy
        if isinstance(data, dict):
            obj = dict(data)
        else:
            obj = dict(getattr(data, "__dict__", {}))

        description = obj.get("description")
        schema = obj.get("schema")
        views = obj.get("views")
        quality_checks = obj.get("quality_checks")
        prompt = obj.get("prompt")
        summary = obj.get("summary")
        created_at = obj.get("created_at")
        updated_at = obj.get("updated_at")

        return cls(
            description=str(description) if description is not None else None,
            schema=schema,
            views=views,
            quality_checks=quality_checks,
            prompt=prompt,
            summary=summary,
            created_at=created_at,
            updated_at=updated_at,
        )


@dataclass(frozen=True)
class UpdateDataModelRequest:
    """Request payload for updating a data model (partial)."""

    data_model: PartialDataModelPayload


@dataclass(frozen=True)
class GenerateDataQualityChecksRequest:
    """Request payload for generating data quality checks."""

    data_model_name: str
    description: str
    limit: int = 1


@dataclass(frozen=True)
class ExecuteDataQualityChecksRequest:
    """Request payload for executing data quality checks."""

    quality_checks: list[ValidationRule]
    document_id: str


@dataclass(frozen=True)
class GenerateDataQualityChecksResponse:
    """Response payload for generating data quality checks."""

    quality_checks: list[ValidationRule]

    @classmethod
    def model_validate(cls, data: list[ValidationRule]) -> GenerateDataQualityChecksResponse:
        return cls(quality_checks=data)
