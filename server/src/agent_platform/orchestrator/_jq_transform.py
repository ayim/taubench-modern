from pydantic.types import JsonValue


def apply_jq_transform(data: JsonValue, jq_expression: str) -> JsonValue:
    """
    Apply a JQ expression to transform JSON data.

    Args:
        data: The JSON data to transform
        jq_expression: The JQ expression to apply

    Returns:
        A list of results produced by the JQ expression. This matches jq's behavior
        where expressions can produce zero, one, or multiple results.

    Raises:
        ValueError: If the JQ expression is invalid or cannot be applied

    Examples:
        >>> apply_jq_transform({"items": [{"x": 1}, {"x": 2}]}, ".items[]")
        [{"x": 1}, {"x": 2}]

        >>> apply_jq_transform([{"name": "A", "price": 10}], ".[0].name")
        ["A"]

        >>> apply_jq_transform({"a": 1, "b": 2}, "{a, b}")
        [{"a": 1, "b": 2}]
    """
    from pyjaq import run_filter

    try:
        return run_filter(jq_expression, [data])
    except Exception as e:
        raise ValueError(f"Error applying JQ expression '{jq_expression}': {e!s}") from e
