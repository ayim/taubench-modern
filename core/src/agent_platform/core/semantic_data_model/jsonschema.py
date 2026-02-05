"""
Drop-in JSON Schema Draft 2020-12 validator that supports custom *annotation*
keywords on any subschema:

  - "synonyms": ["alt_name1", "alt_name2", ...]          # array of strings
  - "sample_values": [ ... ]                             # array of values that
                                                         # must validate against
                                                         # the *same subschema*
                                                         # (minus annotations)

Instance validation semantics are unchanged: these are annotations, not constraints
on your data. But this validator enforces that the annotations are well-formed,
and that sample_values match the described attribute schema.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from jsonschema import Draft202012Validator, exceptions, validators


def _synonyms_keyword(
    validator: Draft202012Validator,
    synonyms_value: Any,
    instance: Any,
    schema: dict[str, Any],
) -> Iterator[exceptions.ValidationError]:
    # Validate the schema annotation's shape.
    if not isinstance(synonyms_value, list) or not all(isinstance(s, str) for s in synonyms_value):
        yield exceptions.ValidationError("'synonyms' must be a list of strings")


def _strip_annotations(subschema: dict[str, Any]) -> dict[str, Any]:
    """
    Return a shallow copy of a subschema with our custom annotation keywords removed,
    so we can validate sample_values against the "real" constraints without recursion.
    """
    if not isinstance(subschema, dict):
        return subschema  # type: ignore[return-value]
    out = dict(subschema)
    out.pop("synonyms", None)
    out.pop("sample_values", None)
    return out


def _sample_values_keyword(
    validator: Draft202012Validator,
    sample_values: Any,
    instance: Any,
    schema: dict[str, Any],
) -> Iterator[exceptions.ValidationError]:
    """
    Validate that sample_values is a list, and that each value validates
    against the *same* subschema (minus annotations).
    """
    if not isinstance(sample_values, list):
        yield exceptions.ValidationError("'sample_values' must be a list")
        return

    base_schema = _strip_annotations(schema)

    # Use the same resolver/context as the current validator (handles $ref, etc.)
    evolved = validator.evolve(schema=base_schema)

    for idx, value in enumerate(sample_values):
        # Validate each sample value against the base subschema.
        for err in evolved.iter_errors(value):
            # Wrap to provide a helpful path to which sample failed.
            yield exceptions.ValidationError(
                f"'sample_values'[{idx}] is invalid for this attribute schema: {err.message}",
                path=err.path,
                schema_path=err.schema_path,
            )


# Create extended validator class with our keyword handlers.
_ExtendedValidator = validators.extend(
    Draft202012Validator,
    {
        "synonyms": _synonyms_keyword,
        "sample_values": _sample_values_keyword,
    },
)


# ----------------------------
# Annotation checking utilities
# ----------------------------


@dataclass(frozen=True)
class SchemaAnnotationError(Exception):
    """
    Raised by check_schema() when custom annotation keywords
    are invalid somewhere in the schema.
    """

    message: str
    errors: tuple[exceptions.ValidationError, ...]

    def __str__(self) -> str:
        return self.message


def _walk_schema_nodes(schema: Any, path: tuple[Any, ...] = ()) -> Iterator[tuple[tuple[Any, ...], Any]]:
    """
    Walk the schema JSON structure. Yields (path, node) for dict nodes.
    """
    if isinstance(schema, dict):
        yield path, schema
        for k, v in schema.items():
            yield from _walk_schema_nodes(v, (*path, k))
    elif isinstance(schema, list):
        for i, item in enumerate(schema):
            yield from _walk_schema_nodes(item, (*path, i))


def _validate_custom_annotations(
    root_validator: Draft202012Validator,
) -> list[exceptions.ValidationError]:
    """
    Validate all occurrences of our custom annotation keywords across the schema tree,
    using a validator instance rooted at the full schema (for $ref resolution).
    """
    errors: list[exceptions.ValidationError] = []
    root_schema = root_validator.schema

    for path, node in _walk_schema_nodes(root_schema):
        if not isinstance(node, dict):
            continue

        # synonyms
        if "synonyms" in node:
            v = node["synonyms"]
            if not isinstance(v, list) or not all(isinstance(s, str) for s in v):
                e = exceptions.ValidationError("'synonyms' must be a list of strings")
                e.schema_path = deque((*list(path), "synonyms"))
                errors.append(e)

        # sample_values (validate with resolver-aware evolve)
        if "sample_values" in node:
            sv = node["sample_values"]
            # sample_values not allowed on object types
            if node.get("type") == "object":
                e = exceptions.ValidationError("'sample_values' is not allowed on object types")
                e.schema_path = deque((*list(path), "sample_values"))
                errors.append(e)
            elif not isinstance(sv, list):
                e = exceptions.ValidationError("'sample_values' must be a list")
                e.schema_path = deque((*list(path), "sample_values"))
                errors.append(e)
            else:
                base_schema = _strip_annotations(node)
                evolved = root_validator.evolve(schema=base_schema)
                for idx, value in enumerate(sv):
                    for err in evolved.iter_errors(value):
                        e = exceptions.ValidationError(
                            f"'sample_values'[{idx}] is invalid for this attribute schema: {err.message}"
                        )
                        e.schema_path = deque((*list(path), "sample_values", idx))
                        errors.append(e)

    return errors


# ----------------------------
# Public validator
# ----------------------------


class CustomDraft202012Validator:
    """
    Draft 2020-12 validator that understands and validates these custom schema annotations:
      - synonyms: list[str]
      - sample_values: list[values validating against the same subschema]

    Uses composition rather than inheritance to avoid jsonschema deprecation warnings.
    """

    def __init__(self, schema: dict[str, Any]) -> None:
        self._schema = schema
        self._validator = _ExtendedValidator(schema)

    @property
    def schema(self) -> dict[str, Any]:
        return self._schema

    def validate(self, instance: Any) -> None:
        """Validate an instance against the schema."""
        self._validator.validate(instance)

    def is_valid(self, instance: Any) -> bool:
        """Check if an instance is valid against the schema."""
        return self._validator.is_valid(instance)

    def iter_errors(self, instance: Any) -> Iterator[exceptions.ValidationError]:
        """Iterate over validation errors for an instance."""
        return self._validator.iter_errors(instance)

    def evolve(self, **kwargs: Any) -> CustomDraft202012Validator:
        """Create a new validator with updated arguments."""
        new_schema = kwargs.get("schema", self._schema)
        return CustomDraft202012Validator(new_schema)

    @classmethod
    def check_schema(cls, schema: dict[str, Any]) -> None:
        """
        Run Draft 2020-12 meta-schema checks AND our custom annotation checks.
        Raises jsonschema.exceptions.SchemaError or SchemaAnnotationError.
        """
        Draft202012Validator.check_schema(schema)

        root_validator = _ExtendedValidator(schema)
        errors = _validate_custom_annotations(root_validator)
        if errors:
            raise SchemaAnnotationError(
                message=f"Schema contains invalid annotation keywords ({len(errors)} issue(s))",
                errors=tuple(errors),
            )
