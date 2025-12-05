import logging
from typing import Any

from sema4ai_docint.models import Mapping, MappingRow

from .transform_document_layout import TransformDocumentLayout

logger = logging.getLogger(__name__)


def transform_content(
    transform_client: TransformDocumentLayout,
    extracted_content: dict[str, Any],
    translation_schema: dict[str, Any],
) -> dict[str, Any]:
    """Transform the extracted content using the translation schema, validating the translation
    schema is a valid Mapping object."""
    if "rules" not in translation_schema:
        raise ValueError("invalid mapping: no 'rules' element")

    mapping = Mapping(rules=[MappingRow(**rule) for rule in translation_schema["rules"]])
    return _apply_mapping(transform_client, extracted_content, mapping)


def _apply_mapping(
    transform_client: TransformDocumentLayout, doc: dict[str, Any], mapping: Mapping
) -> dict[str, Any]:
    """Apply mapping rules to transform the document."""
    out: dict[str, Any] = {}

    for row in mapping.rules:
        mode = row.mode
        src_tokens = transform_client.tokens(row.source)

        if mode == "flatten":
            extras = row.extras
            flattened = transform_client.flatten(doc, src_tokens, extras)
            transform_client.set_path(out, row.target, flattened)
            continue

        val = transform_client.collect(doc, src_tokens)
        if val is None:
            pass
        elif isinstance(val, list):
            val = [transform_client.cast(v, row.transform) for v in val]
        else:
            try:
                val = transform_client.cast(val, row.transform)
            except Exception as e:
                logger.error(f"Error casting value: {e}")
                val = None

        transform_client.set_path(out, row.target, val)

    return out
