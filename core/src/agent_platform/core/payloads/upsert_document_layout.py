from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator
from sema4ai_docint import normalize_name
from sema4ai_docint.models import DocumentLayout
from sema4ai_docint.utils import validate_extraction_schema

from agent_platform.core.errors import ErrorCode, PlatformHTTPError


class _ExtractionSchema(BaseModel):
    """Extraction schema that requires 'type': 'object' and 'properties' but allows extra fields."""

    # Design note: we used a Pydantic model here because of the need to gracefully handle
    # extra fields that may be present in the extraction schema. Rebuilding this logic ourselves
    # would have required a lot of boilerplate with minimal value.

    model_config = ConfigDict(extra="allow")

    type: Literal["object"] = "object"
    properties: dict[str, Any]
    required: list[str] | None = None

    @model_validator(mode="after")
    def validate_schema_structure(self) -> _ExtractionSchema:
        """Validates a JSON schema for use with Reducto as an extraction schema."""
        validate_extraction_schema(self.model_dump(mode="json", exclude_none=True))
        return self


@dataclass(frozen=True)
class _TranslationRule:
    mode: str | None = None
    extras: dict[str, Any] | None = None
    source: str | None = None
    target: str | None = None
    transform: str | None = None

    @classmethod
    def model_validate(cls, data: Any) -> _TranslationRule:
        if isinstance(data, dict):
            obj = dict(data)
        else:
            obj = dict(getattr(data, "__dict__", {}))

        return cls(
            mode=obj.get("mode"),
            extras=obj.get("extras"),
            source=obj.get("source"),
            target=obj.get("target"),
            transform=obj.get("transform"),
        )

    def to_compact_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if self.mode is not None:
            result["mode"] = self.mode
        if self.extras is not None:
            result["extras"] = self.extras
        if self.source is not None:
            result["source"] = self.source
        if self.target is not None:
            result["target"] = self.target
        if self.transform is not None:
            result["transform"] = self.transform
        return result


@dataclass(frozen=True)
class _TranslationSchema:
    rules: list[_TranslationRule]

    @classmethod
    def model_validate(cls, data: Any) -> _TranslationSchema:
        # defensive copy
        if isinstance(data, dict):
            obj = dict(data)
        else:
            obj = dict(getattr(data, "__dict__", {}))

        if isinstance(obj, dict) and "rules" in obj:
            return cls(rules=[_TranslationRule.model_validate(item) for item in obj["rules"]])
        else:
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST,
                message="Translation schema must be an object with a `rules` key made of "
                "an array of rules.",
            )

    def to_compact_dict(self) -> dict[str, Any]:
        return {"rules": [rule.to_compact_dict() for rule in self.rules]}


@dataclass(frozen=True)
class DocumentLayoutPayload:
    """Payload matching the OpenAPI reference for the Layout object except our fields
    will use snake_case.

    Note: name and data_model_name are made optional to support partial payloads
    for extraction requests. When used as a complete layout payload, these should
    be provided and validated at the usage site.
    """

    name: str | None = None
    data_model_name: str | None = None
    extraction_schema: _ExtractionSchema | None = None
    translation_schema: _TranslationSchema | list[_TranslationRule] | None = None
    summary: str | None = None
    extraction_config: dict[str, Any] | None = None
    prompt: str | None = None
    # Read-only in practice; accepted but ignored for persistence
    created_at: str | None = None
    updated_at: str | None = None

    @classmethod
    def model_validate(cls, data: Any) -> DocumentLayoutPayload:
        # Defensive copy
        if isinstance(data, dict):
            obj = dict(data)
        else:
            obj = dict(getattr(data, "__dict__", {}))

        name: str | None = None
        data_model_name: str | None = None
        if isinstance(data, DocumentLayout):
            name = data.name
            data_model_name = data.data_model
        else:
            if obj.get("name") is not None:
                name = normalize_name(str(obj.get("name")))
            if obj.get("data_model_name") is not None:
                data_model_name = normalize_name(str(obj.get("data_model_name")))

        extraction_schema_raw = obj.get("extraction_schema")
        extraction_schema: _ExtractionSchema | None = None
        if extraction_schema_raw is not None:
            extraction_schema = _ExtractionSchema.model_validate(extraction_schema_raw)

        translation_schema_in = obj.get("translation_schema")
        summary = obj.get("summary")
        extraction_config = obj.get("extraction_config")
        prompt = obj.get("prompt") or obj.get("system_prompt")
        created_at = obj.get("created_at")
        updated_at = obj.get("updated_at")

        # Normalize translation rules to the _TranslationSchema type
        rules: _TranslationSchema | list[_TranslationRule] | None = None
        if translation_schema_in:
            if isinstance(translation_schema_in, list):
                rules = _TranslationSchema.model_validate({"rules": translation_schema_in})
            else:
                rules = _TranslationSchema.model_validate(translation_schema_in)

        return cls(
            name=name,
            data_model_name=data_model_name,
            extraction_schema=extraction_schema,
            translation_schema=rules,
            summary=summary,
            extraction_config=extraction_config,
            prompt=prompt,
            created_at=created_at,
            updated_at=updated_at,
        )

    def wrap_translation_schema(self) -> dict[str, Any] | None:
        """We wrap the translation schema into a dictionary for the underlying
        library to properly validate it.
        """
        if self.translation_schema is None:
            return None
        if isinstance(self.translation_schema, _TranslationSchema):
            return self.translation_schema.to_compact_dict()
        return {"rules": [rule.to_compact_dict() for rule in self.translation_schema]}

    def to_document_layout(self) -> DocumentLayout:
        translation_schema_wrapped = self.wrap_translation_schema()

        # Ensure name and data_model_name are provided when converting to DocumentLayout
        if self.name is None:
            raise ValueError("name is required when converting to DocumentLayout")
        if self.data_model_name is None:
            raise ValueError("data_model_name is required when converting to DocumentLayout")

        extraction_schema_dict = None
        if self.extraction_schema is not None:
            extraction_schema_dict = self.extraction_schema.model_dump(
                mode="json", exclude_none=True
            )

        return DocumentLayout(
            name=self.name,
            data_model=self.data_model_name,
            extraction_schema=extraction_schema_dict,
            translation_schema=translation_schema_wrapped,
            summary=self.summary,
            extraction_config=self.extraction_config,
            system_prompt=self.prompt,
        )

    def model_dump(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "data_model_name": self.data_model_name,
            "extraction_schema": self.extraction_schema.model_dump(mode="json", exclude_none=True)
            if self.extraction_schema
            else None,
            "translation_schema": self.wrap_translation_schema(),
            "summary": self.summary,
            "extraction_config": self.extraction_config,
            "prompt": self.prompt,
        }
