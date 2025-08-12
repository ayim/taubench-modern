from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sema4ai_docint import normalize_name
from sema4ai_docint.models import DocumentLayout


@dataclass(frozen=True)
class TranslationRulePayload:
    mode: str | None = None
    extras: dict[str, Any] | None = None
    source: str | None = None
    target: str | None = None
    transform: str | None = None

    @classmethod
    def model_validate(cls, data: Any) -> TranslationRulePayload:
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
class UpsertDocumentLayoutPayload:
    """Payload matching the OpenAPI reference for the Layout object.

    Field names use the reference spec (camelCase) but are normalized here to
    snake_case and converted to the underlying `DocumentLayout` model as needed.
    """

    name: str
    data_model_name: str
    extraction_schema: dict[str, Any] | None = None
    translation_schema: list[TranslationRulePayload] | None = None
    summary: str | None = None
    extraction_config: dict[str, Any] | None = None
    prompt: str | None = None
    # Read-only in practice; accepted but ignored for persistence
    created_at: str | None = None
    updated_at: str | None = None

    @classmethod
    def model_validate(cls, data: Any) -> UpsertDocumentLayoutPayload:
        # Defensive copy
        if isinstance(data, dict):
            obj = dict(data)
        else:
            obj = dict(getattr(data, "__dict__", {}))

        # Accept both camelCase (spec) and snake_case (internal) keys
        name = normalize_name(str(obj.get("name")))
        data_model_name = normalize_name(str(obj.get("dataModelName", obj.get("data_model_name"))))
        extraction_schema = obj.get("extractionSchema", obj.get("extraction_schema"))
        translation_schema_in = obj.get("translationSchema", obj.get("translation_schema"))
        summary = obj.get("summary")
        extraction_config = obj.get("extractionConfig", obj.get("extraction_config"))
        prompt = obj.get("prompt", obj.get("system_prompt"))
        created_at = obj.get("createdAt", obj.get("created_at"))
        updated_at = obj.get("updatedAt", obj.get("updated_at"))

        # Normalize translation rules
        rules: list[TranslationRulePayload] | None = None
        if translation_schema_in:
            rules = [TranslationRulePayload.model_validate(item) for item in translation_schema_in]

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

    def to_document_layout(self) -> DocumentLayout:
        # The underlying library expects `translation_schema` to be a JSON-like
        # dict. The OpenAPI spec models it as an array of rules, so we wrap
        # them into a dictionary under the `rules` key.
        translation_schema_wrapped: dict[str, Any] | None = None
        if self.translation_schema is not None:
            translation_schema_wrapped = {
                "rules": [rule.to_compact_dict() for rule in self.translation_schema]
            }

        return DocumentLayout(
            name=self.name,
            data_model=self.data_model_name,
            extraction_schema=self.extraction_schema,
            translation_schema=translation_schema_wrapped,
            summary=self.summary,
            extraction_config=self.extraction_config,
            system_prompt=self.prompt,
        )
