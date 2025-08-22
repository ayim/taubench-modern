from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sema4ai_docint import normalize_name
from sema4ai_docint.models import DocumentLayout

from agent_platform.core.document_intelligence.document_layout import DocumentLayoutBridge
from agent_platform.core.errors import ErrorCode, PlatformHTTPError


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
    """

    name: str
    data_model_name: str
    extraction_schema: dict[str, Any] | None = None
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

        name = normalize_name(str(obj.get("name")))
        data_model_name = normalize_name(str(obj.get("data_model_name")))
        extraction_schema = obj.get("extraction_schema")
        translation_schema_in = obj.get("translation_schema")
        summary = obj.get("summary")
        extraction_config = obj.get("extraction_config")
        prompt = obj.get("prompt")
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

        return DocumentLayout(
            name=self.name,
            data_model=self.data_model_name,
            extraction_schema=self.extraction_schema,
            translation_schema=translation_schema_wrapped,
            summary=self.summary,
            extraction_config=self.extraction_config,
            system_prompt=self.prompt,
        )

    def to_document_layout_bridge(self) -> DocumentLayoutBridge:
        translation_schema_wrapped = self.wrap_translation_schema()

        return DocumentLayoutBridge.model_validate(
            {
                "name": self.name,
                "data_model": self.data_model_name,
                "extraction_schema": self.extraction_schema,
                "translation_schema": translation_schema_wrapped,
                "summary": self.summary,
                "extraction_config": self.extraction_config,
                "system_prompt": self.prompt,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
            }
        )
