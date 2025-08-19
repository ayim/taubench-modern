from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sema4ai_docint.models import Mapping, MappingRow

if TYPE_CHECKING:
    from sema4ai_docint.models import DocumentLayout


@dataclass(frozen=True)
class DocumentLayoutSummary:
    name: str
    data_model: str
    summary: str | None = None


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            # Leave unparsed strings as None to avoid raising hard errors
            return None
    return None


@dataclass(frozen=True)
class DocumentLayoutBridge:
    """This is an internal bridge class that provides for an agent server controlled type
    to represent document layout data.
    """

    name: str
    data_model: str
    summary: str | None = None
    extraction_schema: dict[str, Any] | None = None
    translation_schema: Mapping | None = None
    extraction_config: dict[str, Any] | None = None
    system_prompt: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def model_validate(cls, data: Any) -> DocumentLayoutBridge:
        """Create a DocumentLayout from a dict-like input using snake_case keys.

        Parses ISO 8601 datetimes. `translation_schema` may be provided as:
        - a Mapping instance
        - a dict with a `rules` list of rule dicts
        - a list of rule dicts (will be wrapped into a Mapping)
        """

        # Fast path: already an instance
        if isinstance(data, cls):
            return data

        # Normalize to a plain dict copy
        if isinstance(data, dict):
            obj = dict(data)
        else:
            obj = dict(getattr(data, "__dict__", {}))

        name = obj.get("name")
        data_model = obj.get("data_model")
        if not isinstance(name, str) or not isinstance(data_model, str):
            raise ValueError("'name' and 'data_model' are required fields for DocumentLayout")

        summary = obj.get("summary")
        extraction_schema = obj.get("extraction_schema")
        extraction_config = obj.get("extraction_config")
        system_prompt = obj.get("system_prompt")

        # translation_schema normalization using pydantic v2 model_validate
        translation_schema_in = obj.get("translation_schema")
        translation_schema: Mapping | None
        if translation_schema_in is None:
            translation_schema = None
        elif isinstance(translation_schema_in, Mapping):
            translation_schema = translation_schema_in
        elif isinstance(translation_schema_in, list):
            rules: list[MappingRow] = [
                r if isinstance(r, MappingRow) else MappingRow.model_validate(r)
                for r in translation_schema_in
            ]
            translation_schema = Mapping.model_validate({"rules": rules})
        elif isinstance(translation_schema_in, dict):
            translation_schema = Mapping.model_validate(translation_schema_in)
        else:
            translation_schema = None

        created_at = _parse_dt(obj.get("created_at"))
        updated_at = _parse_dt(obj.get("updated_at"))

        return cls(
            name=name,
            data_model=data_model,
            summary=summary,
            extraction_schema=extraction_schema,
            translation_schema=translation_schema,
            extraction_config=extraction_config,
            system_prompt=system_prompt,
            created_at=created_at,
            updated_at=updated_at,
        )

    @classmethod
    def from_document_layout(cls, document_layout: DocumentLayout) -> DocumentLayoutBridge:
        """Convert a DocumentLayout database model to a DocumentLayoutBridge.

        The DocumentLayout model uses pydantic Json fields for some complex data,
        while DocumentLayoutBridge expects the parsed objects.
        """
        # Handle translation_schema conversion
        translation_schema = None
        if document_layout.translation_schema is not None:
            if isinstance(document_layout.translation_schema, dict):
                # Convert dict with rules to Mapping object
                translation_schema = Mapping.model_validate(document_layout.translation_schema)
            else:
                # Already a Mapping object
                translation_schema = document_layout.translation_schema

        return cls.model_validate(
            {
                "name": document_layout.name,
                "data_model": document_layout.data_model,
                "summary": document_layout.summary,
                "extraction_schema": document_layout.extraction_schema,
                "translation_schema": translation_schema,
                "extraction_config": document_layout.extraction_config,
                "system_prompt": document_layout.system_prompt,
                "created_at": _parse_dt(document_layout.created_at),
                "updated_at": _parse_dt(document_layout.updated_at),
            }
        )
