import json

from agent_platform.core.utils.partial_json import clean_json_string


class TestCleanJsonString:
    # ---------------------------
    # Fast path (valid JSON)
    # ---------------------------

    def test_complete_top_level_string(self) -> None:
        content = '{"markdown": "Hello\\nWorld"}'
        assert clean_json_string(content, "markdown") == "Hello\nWorld"

    def test_complete_missing_field_returns_original(self) -> None:
        content = '{"other": "value"}'
        assert clean_json_string(content, "markdown") == content

    def test_complete_non_string_value_returns_original(self) -> None:
        # New behavior: do NOT stringify non-string values; return original content.
        content = '{"markdown": 123}'
        assert clean_json_string(content, "markdown") == content

    def test_complete_nested_same_field_not_returned(self) -> None:
        content = '{"meta": {"markdown": "inside"}}'
        assert clean_json_string(content, "markdown") == content

    def test_complete_top_level_not_dict_returns_original(self) -> None:
        content = '["markdown", "value"]'
        assert clean_json_string(content, "markdown") == content

    # ---------------------------
    # Partial path (incremental)
    # ---------------------------

    def test_partial_basic_with_newlines(self) -> None:
        partial = '{"markdown":  "This is ' + "\\n\\n" + " text"
        assert clean_json_string(partial, "markdown") == "This is \n\n text"

    def test_partial_handles_escaped_quotes(self) -> None:
        partial = '{"markdown": "He said: \\"Hello\\" and"'
        assert clean_json_string(partial, "markdown") == 'He said: "Hello" and'

    def test_partial_stops_at_unescaped_quote(self) -> None:
        partial = '{"markdown": "Hello " and more'
        assert clean_json_string(partial, "markdown") == "Hello "

    def test_partial_trailing_backslash_is_dropped(self) -> None:
        partial = '{"markdown": "abc' + "\\"
        assert clean_json_string(partial, "markdown") == "abc"

    def test_partial_incomplete_unicode_escape_is_dropped(self) -> None:
        partial = '{"markdown": "Hello ' + "\\u00" + '"'
        assert clean_json_string(partial, "markdown") == "Hello "

    def test_partial_unicode_surrogate_pair_combined(self) -> None:
        # pair is fully valid → 😀 even without closing quote
        partial = '{"markdown": ' + '"\\uD83D\\uDE00'
        assert clean_json_string(partial, "markdown") == "\U0001f600"

    def test_partial_high_surrogate_without_low_stops_before_escape(self) -> None:
        partial = '{"markdown": ' + '"X ' + "\\uD83D" + ' end"'
        assert clean_json_string(partial, "markdown") == "X "

    def test_partial_low_surrogate_without_high_stops_before_escape(self) -> None:
        partial = '{"markdown": ' + '"X ' + "\\uDE00" + ' end"'
        assert clean_json_string(partial, "markdown") == "X "

    def test_partial_unknown_escape_stops_before_escape(self) -> None:
        partial = '{"markdown": ' + '"A ' + "\\q" + ' B"'
        assert clean_json_string(partial, "markdown") == "A "

    def test_partial_forward_slash_escape(self) -> None:
        partial = '{"markdown": ' + '"\\/path\\/to\\/file"'
        assert clean_json_string(partial, "markdown") == "/path/to/file"

    def test_partial_whitespace_variants_around_colon(self) -> None:
        partial = '{  "markdown"   :\t"ok'
        assert clean_json_string(partial, "markdown") == "ok"

    def test_partial_value_not_a_string_returns_original(self) -> None:
        partial = '{"markdown": { "x": 1 }'
        assert clean_json_string(partial, "markdown") == partial

    def test_partial_colon_missing_returns_original(self) -> None:
        partial = '{"markdown" "value'
        assert clean_json_string(partial, "markdown") == partial

    def test_partial_prefix_garbage_before_top_level_object(self) -> None:
        partial = 'INFO 12:00 something happened\n{"markdown":"A' + "\\n" + "B"
        assert clean_json_string(partial, "markdown") == "A\nB"

    def test_partial_field_name_inside_a_string_is_ignored(self) -> None:
        # The sequence '"markdown":' appears inside the *value* string for the "msg" key.
        # Scanner must ignore it and return the real top-level "markdown" later.
        partial = '{"msg":"prefix \\"markdown\\": \\"fake\\"", "markdown": "real value'
        assert clean_json_string(partial, "markdown") == "real value"

    def test_partial_duplicate_keys_uses_first_encountered(self) -> None:
        # In partial scan we return the first encountered top-level key occurrence.
        partial = '{"markdown": "first", "markdown": "second'
        assert clean_json_string(partial, "markdown") == "first"

    def test_partial_nested_then_top_level_works(self) -> None:
        partial = '{"nested":{"markdown":"inner"}, "markdown":"outer'
        assert clean_json_string(partial, "markdown") == "outer"

    def test_partial_incomplete_key_string_means_not_found(self) -> None:
        partial = '{"mark'
        assert clean_json_string(partial, "markdown") == partial

    def test_partial_key_with_unicode_escape_matches(self) -> None:
        # Key is "mark\u0064own" -> "markdown"
        partial = '{"mark\\u0064own": "ok'
        assert clean_json_string(partial, "markdown") == "ok"

    # ---------------------------
    # Misc completeness
    # ---------------------------

    def test_decodes_all_common_escapes_complete(self) -> None:
        expected = 'a\nb\rc\td\be\ff/g\\h"i'
        content = json.dumps({"markdown": expected})
        assert clean_json_string(content, "markdown") == expected

    def test_decodes_all_common_escapes_partial(self) -> None:
        expected = 'a\nb\rc\td\be\ff/g\\h"i'
        encoded = json.dumps(expected)
        partial_value_without_final_quote = encoded[:-1]  # drop final '"'
        partial = '{"markdown": ' + partial_value_without_final_quote
        assert clean_json_string(partial, "markdown") == expected
