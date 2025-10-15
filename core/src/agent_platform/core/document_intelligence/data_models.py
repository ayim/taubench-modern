from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sema4ai_docint.models.data_model import DataModel
from sema4ai_docint.utils import normalize_name
from sema4ai_docint.validation.models import ValidationRule

from agent_platform.core.files import UploadedFile


@dataclass(frozen=True)
class DataModelPayload:
    """Payload for the DataModel object."""

    name: str
    description: str
    model_schema: dict[str, Any]
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
        model_schema = obj.get("model_schema")
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
        if not model_schema:
            raise ValueError("DataModel.schema is required")

        return cls(
            name=str(name),
            description=str(description),
            model_schema=model_schema,
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
            model_schema=self.model_schema,
            views=self.views,
            quality_checks=self.quality_checks,
            prompt=self.prompt,
            summary=self.summary,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


@dataclass(frozen=True)
class DataModelSummary:
    """Summary of a data model."""

    name: str
    description: str
    model_schema: dict[str, Any]


def summary_from_model(model: DataModel) -> DataModelSummary:
    """Build DataModelSummary (name, description, schema)."""
    return DataModelSummary(
        name=model.name,
        description=model.description,
        model_schema=model.model_schema,
    )


@dataclass(frozen=True)
class CreateDataModelRequest:
    """Request payload for creating a data model."""

    data_model: DataModelPayload


@dataclass(frozen=True)
class DataModelResponse:
    """Response payload for creating/getting a data model."""

    data_model: DataModel


@dataclass(frozen=True)
class GenerateDataModelResponse:
    """Response payload for generating a data model."""

    model_schema: dict[str, Any]
    uploaded_file: UploadedFile | None = None


@dataclass(frozen=True)
class PartialDataModelPayload:
    """Payload for partial updates of a DataModel (all fields optional)."""

    description: str | None = None
    model_schema: dict[str, Any] | None = None
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
        model_schema = obj.get("model_schema")
        views = obj.get("views")
        quality_checks = obj.get("quality_checks")
        prompt = obj.get("prompt")
        summary = obj.get("summary")
        created_at = obj.get("created_at")
        updated_at = obj.get("updated_at")

        return cls(
            description=str(description) if description is not None else None,
            model_schema=model_schema,
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
    description: str | None = None
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


@dataclass(frozen=True)
class GenerateDescriptionResponse:
    """Response payload for generating a data model description."""

    description: str

    @classmethod
    def model_validate(cls, data: str) -> GenerateDescriptionResponse:
        return cls(description=data)
