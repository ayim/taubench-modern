from dataclasses import is_dataclass
from enum import Enum
from types import UnionType
from typing import (
    Annotated,
    Any,
    Union,
    cast,
    get_args,
    get_origin,
)

################################################
# Helper: detect whether a type is an Enum
################################################


def _is_enum_type(t: Any) -> bool:
    """Return True if 't' is an enum.Enum subclass."""
    return isinstance(t, type) and issubclass(t, Enum)


################################################
# Helper: find a description from Annotated metadata
################################################


def _find_annotated_description(
    metadata: tuple[Any, ...],
    param_name: str,
) -> str | None:
    """
    Searches the Annotated metadata tuple for a string (or a sentinel)
    that you use to store a description. Adjust logic to suit your usage.
    """
    for m in metadata:
        if isinstance(m, str):
            return m  # treat plain string as description
        # else check if m is a custom descriptor type, etc.
    return None


################################################
# Helper: require a description or raise
################################################


def _require_description(param_name: str, hint: Any) -> str:
    """Raise ValueError if no explicit description is present."""
    raise ValueError(
        f"Parameter '{param_name}' (type {hint}) is missing a description.",
    )


################################################
# Helper: apply a description to a schema
# or raise if it's missing (unless allowed)
################################################


def _apply_description(
    schema: dict[str, Any],
    annotated_description: str | None,
    param_name: str,
    allow_omitted_description: bool,
) -> None:
    """
    If annotated_description is present, set schema['description'] = it.
    Otherwise, if not allow_omitted_description, raise.
    """
    if annotated_description is not None:
        schema["description"] = annotated_description
    elif not allow_omitted_description:
        _require_description(param_name, schema.get("type", "Unknown"))


################################################
# Helper: unwrap Annotated & Optional until stable
################################################


def unwrap_annotated_and_optional(
    hint: Any,
    param_name: str,
) -> tuple[Any, bool, str | None]:
    """
    Repeatedly unwrap:
      - Annotated[...] (collecting description from metadata)
      - Optional[...] (Union[..., None]) => is_nullable = True
    Return (unwrapped_type, is_nullable, annotated_description).
    """
    is_nullable = False
    annotated_description = None

    # -- 1) Repeatedly unwrap Annotated --
    while True:
        origin = get_origin(hint)
        if origin is Annotated:
            meta = get_args(hint)
            real_type = meta[0]
            # extract a description if present
            desc = _find_annotated_description(meta[1:], param_name)
            if desc:
                annotated_description = desc
            hint = real_type
        else:
            break

    # -- 2) Check if it's a Union containing None (aka Optional)
    origin = get_origin(hint)
    args = get_args(hint)
    if origin in [Union, UnionType] and type(None) in args:
        non_none_types = [t for t in args if t is not type(None)]
        if len(non_none_types) > 1:
            # we reject multi-non-None unions
            raise ValueError(
                f"Parameter '{param_name}' has a Union with multiple non-None types "
                f"{non_none_types}; this is not supported.",
            )
        elif len(non_none_types) == 1:
            # exactly one real type + None
            hint = non_none_types[0]
            is_nullable = True
            # We might want to unwrap Annotated again, if that single type is Annotated
            # E.g. Optional[Annotated[X, ...]]
            while True:
                origin = get_origin(hint)
                if origin is Annotated:
                    meta = get_args(hint)
                    real_type = meta[0]
                    desc = _find_annotated_description(meta[1:], param_name)
                    if desc:
                        annotated_description = desc
                    hint = real_type
                else:
                    break
        else:
            # edge case: Union[None] only
            # you might treat this as "type": "null"
            hint = type(None)
            is_nullable = True

    return hint, is_nullable, annotated_description


################################################
# Stub: build dataclass schema
# (you'd recursively inspect fields, etc.)
################################################


def build_dataclass_schema(
    cls: type[Any],
    annotated_description: str | None = None,
    is_nullable: bool = False,
) -> dict[str, Any]:
    """
    Example stub for building a dataclass schema.
    In practice, you'd:
      - iterate over fields
      - call build_param_schema for each
      - mark 'required' if field has no default
    """
    from dataclasses import fields

    properties: dict[str, Any] = {}
    required: list[str] = []

    for field in fields(cls):
        field_name = field.name
        field_type = field.type
        # is_required if no default
        if field.default is field.default_factory or field.default is None:
            # This logic might need refinement for your use case
            required.append(field_name)

        sub_schema = build_param_schema(
            field_name,
            field_type,
            # typically dataclass fields can skip an explicit description
            allow_omitted_description=True,
        )
        properties[field_name] = sub_schema

    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "required": required,
    }
    if is_nullable:
        schema["type"] = ["object", "null"]
    if annotated_description:
        schema["description"] = annotated_description
    return schema


################################################
# Build param schema - main entry
################################################


def build_param_schema(
    param_name: str,
    hint: Any,
    allow_omitted_description: bool = False,
) -> dict[str, Any]:
    """
    Construct the JSON schema for a single parameter (potentially nested).
    Raises ValueError if required metadata (like 'description') is missing,
    unless allow_omitted_description=True.
    """

    # 1) Unwrap Annotated & Optional
    unwrapped_type, is_nullable, annotated_description = (
        unwrap_annotated_and_optional(hint, param_name)
    )

    # 2) If it's a dataclass
    if is_dataclass(unwrapped_type):
        return build_dataclass_schema(
            cls=cast(type[Any], unwrapped_type),
            annotated_description=annotated_description,
            is_nullable=is_nullable,
        )

    # 3) If it's an enum
    if _is_enum_type(unwrapped_type):
        # Build an enum schema
        possible_values = [m.value for m in unwrapped_type]
        # Decide string or integer type if all values are ints or all are strings
        # For a typical enum, they're often strings, but could be int
        # if it's an IntEnum
        schema_type = (
            "integer"
            if all(isinstance(v, int) for v in possible_values)
            else "string"
        )
        schema_type = [schema_type, "null"] if is_nullable else schema_type

        schema = {
            "type": schema_type,
            "enum": possible_values,
        }
        _apply_description(
            schema,
            annotated_description,
            param_name,
            allow_omitted_description,
        )
        return schema

    # 4) Check if it's list[...] or tuple[...]
    origin = get_origin(unwrapped_type)
    args = get_args(unwrapped_type)
    if origin in (list, tuple):
        max_tuple_args = 2
        # We reject multi-type tuples, so we check if it has exactly 2
        # and the second is Ellipsis
        if origin is tuple and len(args) == max_tuple_args and args[1] is Ellipsis:
            # e.g. Tuple[str, ...]
            item_type = args[0]
        elif origin is list and len(args) == 1:
            # e.g. list[str]
            item_type = args[0]
        else:
            # If it doesn't match the above patterns, we either have no args
            # or multi-typed. We explicitly reject multi-typed tuples like
            # tuple[X, Y]
            raise ValueError(
                f"Parameter '{param_name}' uses a multi-type or zero-type "
                f"tuple/list '{unwrapped_type}'. Only list[X], tuple[X, ...], "
                "or no-arg list/tuple are supported.",
            )
        # Build the items schema recursively
        items_schema = build_param_schema(f"{param_name}_item", item_type, True)
        schema = {
            "type": ["array", "null"] if is_nullable else "array",
            "items": items_schema,
        }
        _apply_description(
            schema,
            annotated_description,
            param_name,
            allow_omitted_description,
        )
        return schema

    # 5) If it's a primitive builtin: str, int, float, bool, or None
    if unwrapped_type in (str, int, float, bool):
        # map python type to JSON Schema type
        types_to_schema_type = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
        }
        base_type = types_to_schema_type[unwrapped_type]
        schema = {"type": [base_type, "null"] if is_nullable else base_type}
        _apply_description(
            schema,
            annotated_description,
            param_name,
            allow_omitted_description,
        )
        return schema

    if unwrapped_type is type(None):
        # pure None type
        schema = {"type": "null"}
        _apply_description(
            schema,
            annotated_description,
            param_name,
            allow_omitted_description,
        )
        return schema

    # 6) Otherwise, reject
    raise ValueError(
        f"Parameter '{param_name}' has an unsupported type '{unwrapped_type}'. "
        "Please use a dataclass, enum, list/tuple, str/int/float/bool, or None.",
    )
