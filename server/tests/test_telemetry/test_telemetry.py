def test_format_variables(monkeypatch) -> None:
    """Test formatting variables with various scenarios."""
    from agent_platform.server.telemetry import pretty_print as pretty_print_module
    from agent_platform.server.telemetry.pretty_print import pretty_print

    monkeypatch.setattr(pretty_print_module, "MAX_CHARS_TO_CONSIDER_SMALL_LINE", 0)

    indent = "  "
    assert pretty_print('{"name": "John", "age": 30}') == (f'{{\n{indent}"name": "John",\n{indent}"age": 30\n}}')

    # Not ideal (we could remove the last \n${indent})
    assert pretty_print('{"name": "John", "age": 30,}') == (
        f'{{\n{indent}"name": "John",\n{indent}"age": 30,\n{indent}\n}}'
    )

    # Unclosed
    assert pretty_print('{"name": "John') == '{"name": "John'

    # Decode \r\n from string reprs.
    assert pretty_print('"Some\\nmulti\\nline\\n"') == '"""Some\nmulti\nline\n"""'

    monkeypatch.setattr(pretty_print_module, "MAX_CHARS_TO_CONSIDER_SMALL_LINE", 13)
    assert pretty_print("[1,2,3]") == "[1, 2, 3]"
    assert pretty_print("[1,2,3,4,5,6,7,8,9,10]") == (
        f"[\n{indent}1,\n{indent}2,\n{indent}3,\n{indent}4,\n{indent}5,\n{indent}6,\n{indent}7,\n{indent}8,\n{indent}9,\n{indent}10\n]"
    )
    assert pretty_print("(['a', 'b'],)") == "(['a', 'b'], )"


def test_format_variables_bad() -> None:
    """Test formatting with bad/unclosed strings."""
    from agent_platform.server.telemetry.pretty_print import pretty_print

    assert pretty_print('"unclosed str') == '"unclosed str'
    assert pretty_print('["unclosed str') == '["unclosed str'
    assert pretty_print("] ) } unmatched") == "] ) } unmatched"
