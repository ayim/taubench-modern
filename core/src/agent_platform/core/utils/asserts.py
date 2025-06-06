from dataclasses import is_dataclass
from typing import Any, Literal, get_args, get_origin


def assert_literal_value_valid(class_instance: Any, value_name: str) -> None:
    """Validates that a value in a dataclass matches its Literal type annotation.

    Arguments:
        class_instance: Instance of a dataclass to validate.
        value_name: Name of the attribute to validate.

    Raises:
        ValueError: If validation fails.

        There are several failure scenarios:
            - The class instance is not a dataclass.
            - The attribute is not found in the dataclass.
            - The attribute has no type annotation.
            - The attribute's type annotation is not a Literal.
            - The value does not match any of the valid values for the Literal.
    """
    # Check if instance is a dataclass
    if not is_dataclass(class_instance):
        raise ValueError(
            f"Expected a dataclass instance, got {type(class_instance).__name__}",
        )

    # Get the value from the class instance
    try:
        value = getattr(class_instance, value_name)
    except AttributeError as e:
        raise ValueError(
            f"Attribute '{value_name}' not found in dataclass {type(class_instance).__name__}",
        ) from e

    # Get the type annotation
    try:
        type_annotation = class_instance.__annotations__[value_name]
    except KeyError as e:
        raise ValueError(
            f"Attribute '{value_name}' has no type annotation in "
            f"dataclass {type(class_instance).__name__}",
        ) from e

    # Verify it's a Literal type
    if get_origin(type_annotation) is not Literal:
        raise ValueError(
            f"Attribute '{value_name}' must have a Literal type annotation, got {type_annotation}",
        )

    # Get the valid values from the Literal
    valid_values = get_args(type_annotation)

    # Assert that the value is in the valid values
    if value not in valid_values:
        raise ValueError(
            f"Invalid value for '{value_name}': {value!r}. "
            f"Must be one of: {', '.join(repr(v) for v in valid_values)}",
        )
