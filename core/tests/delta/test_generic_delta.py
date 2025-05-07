import json
import os
from typing import Any

import pytest

from agent_platform.core.delta import GenericDelta
from agent_platform.core.delta.base import NO_VALUE, DeltaOpType
from agent_platform.core.delta.combine_delta import combine_generic_deltas
from agent_platform.core.delta.compute_delta import compute_generic_deltas
from agent_platform.core.delta.errors import InvalidPathError
from agent_platform.core.delta.utils import validate_delta_path

########################################
# Fixtures for tests
########################################


@pytest.fixture
def json_patch_tests_data():
    """
    Data for testing JSON Patch operations obtained from json-patch-tests
    (https://github.com/json-patch/json-patch-tests).
    """
    path = os.path.join(
        os.path.dirname(__file__),
        "json-patch-tests.json",
    )

    test_cases = []
    with open(path) as f:
        test_cases.extend(json.load(f))

    # Filter out test cases that are marked as disabled or have error expectations
    # We're only interested in valid test cases for now
    valid_test_cases = [
        case
        for case in test_cases
        if not case.get("disabled", False) and "error" not in case
    ]

    return valid_test_cases


########################################
# Tests for GenericDelta
########################################


class TestGenericDelta:
    def test_generic_delta_init_and_dict(self):
        """
        Basic test to ensure GenericDelta can be constructed and
        converted to a JSON-compatible dictionary.
        """
        delta = GenericDelta(op="replace", path="/foo/bar", value="new_value")
        assert delta.op == "replace"
        assert delta.path == "/foo/bar"
        assert delta.value == "new_value"

        as_dict = delta.model_dump()
        assert as_dict == {
            "op": "replace",
            "path": "/foo/bar",
            "value": "new_value",
        }

    @pytest.mark.parametrize(
        ("op", "path", "value", "from_", "expected_error", "error_match"),
        [
            # Valid paths
            # 1. Simple path
            ("add", "/test", "test", None, None, None),
            # 2. Empty path
            ("add", "", "test", None, None, None),
            # 3. Nested path
            ("add", "/a/b/c", "test", None, None, None),
            # 4. Move operation
            ("move", "/dest", NO_VALUE, "/src", None, None),
            # Invalid paths
            # 5. Invalid character sequence
            (
                "remove",
                "invalid",
                NO_VALUE,
                None,
                InvalidPathError,
                "Invalid target path",
            ),
            # 6. Move/copy operations with invalid paths
            (
                "move",
                "/valid",
                NO_VALUE,
                "invalid",
                InvalidPathError,
                "Invalid source path",
            ),
        ],
        ids=[
            "01_simple_path",
            "02_empty_path",
            "03_nested_path",
            "04_move_operation",
            "05_invalid_char_sequence",
            "06_move_invalid_source",
        ],
    )
    def test_generic_delta_path_validation(  # noqa: PLR0913
        self,
        op: DeltaOpType,
        path: str,
        value: Any,
        from_: str | None,
        expected_error: type[Exception] | None,
        error_match: str | None,
    ) -> None:
        """Test path validation in GenericDelta.

        Args:
            path: The path to validate
            op: The operation type
            from_: The from_ path for move/copy operations
            expected_error: Expected exception type, if any
            error_match: Expected error message pattern, if any
        """
        if expected_error is None:
            # Should succeed
            GenericDelta(op=op, path=path, value=value, from_=from_)
        else:
            # Should raise expected error
            with pytest.raises(expected_error, match=error_match):
                GenericDelta(op=op, path=path, value=value, from_=from_)

    @pytest.mark.parametrize(
        ("op", "path", "value", "from_", "expected_error", "error_match"),
        [
            # Valid array operations
            # 1. Append to array
            ("add", "/array/-", "test", None, None, None),
            # 2. Insert at start of array
            ("add", "/array/0", "test", None, None, None),
            # 3. Insert at end of array
            ("add", "/array/3", "test", None, None, None),
            # 4. Nested array operation
            ("add", "/nested/array/1", "test", None, None, None),
            # 5. Add to object in array
            ("add", "/obj_array/0/newkey", "test", None, None, None),
            # 6. Add to array in array
            ("add", "/arr_array/0/0/newkey", "test", None, None, None),
            # 7. Add to existing object
            ("add", "/nested/newkey", "test", None, None, None),
            # 8. Add deep in nested structure
            ("add", "/nested/deep/new", "test", None, None, None),
            # 9. Replace existing value
            ("replace", "/array/0", "test", None, None, None),
            # 10. Replace nested value
            ("replace", "/nested/array/0", "test", None, None, None),
            # 11. Replace whole document
            ("replace", "", {"new": "doc"}, None, None, None),
            # 12. Valid move operation
            ("move", "/array/0", NO_VALUE, "/array/1", None, None),
            # 13. Valid copy operation
            ("copy", "/array/-", NO_VALUE, "/array/0", None, None),
            # Invalid array operations
            # 14. Array index out of bounds
            (
                "remove",
                "/array/4",
                NO_VALUE,
                None,
                InvalidPathError,
                "Invalid target path",
            ),
            # 15. Invalid array index (leading zero)
            (
                "remove",
                "/array/01",
                NO_VALUE,
                None,
                InvalidPathError,
                "Invalid array index",
            ),
            # 16. Invalid array index (double zero)
            (
                "remove",
                "/array/00",
                NO_VALUE,
                None,
                InvalidPathError,
                "Invalid array index",
            ),
            # 17. Invalid array index (float)
            (
                "remove",
                "/array/1.5",
                NO_VALUE,
                None,
                InvalidPathError,
                "Invalid array index",
            ),
            # 18. Invalid array index (invalid character)
            (
                "remove",
                "/array/1a",
                NO_VALUE,
                None,
                InvalidPathError,
                "Invalid array index",
            ),
            # 19. Invalid target path in nested array
            (
                "remove",
                "/nested/array/3",
                NO_VALUE,
                None,
                InvalidPathError,
                "Invalid target path",
            ),
            # 20. Non-existent parent for add
            (
                "add",
                "/nonexistent/key",
                "test",
                None,
                InvalidPathError,
                "Invalid target path",
            ),
            # 21. Parent exists but wrong type (trying to add to non-object)
            (
                "add",
                "/array/0/invalid",
                "test",
                None,
                InvalidPathError,
                "Invalid target path",
            ),
            # 22. Invalid move from path (leading zero)
            (
                "move",
                "/array/0",
                NO_VALUE,
                "/array/01",
                InvalidPathError,
                "Invalid array index",
            ),
            # 23. Invalid copy from path (out of bounds)
            (
                "copy",
                "/array/-",
                NO_VALUE,
                "/array/4",
                InvalidPathError,
                "Invalid source path.*out of bounds",
            ),
            # 24. Replace non-existent path
            (
                "replace",
                "/nonexistent",
                "test",
                None,
                InvalidPathError,
                "Invalid target path",
            ),
            # 25. Replace with invalid array index
            (
                "replace",
                "/array/5",
                "test",
                None,
                InvalidPathError,
                "Invalid target path",
            ),
            # 26. Replace with wrong type path
            (
                "replace",
                "/array/0/invalid",
                "test",
                None,
                InvalidPathError,
                "Invalid target path",
            ),
            # 27. Invalid array index during add operation
            (
                "add",
                "/array/01",
                "test",
                None,
                InvalidPathError,
                "Invalid array index",
            ),
            # 28. Invalid array index during add operation (double zero)
            (
                "add",
                "/array/00",
                "test",
                None,
                InvalidPathError,
                "Invalid array index",
            ),
            # 29. Invalid object path on array element
            (
                "add",
                "/array/0/key",
                "test",
                None,
                InvalidPathError,
                "Invalid target path",
            ),
            # 30. Invalid object path on nested array element
            (
                "add",
                "/nested/array/0/key",
                "test",
                None,
                InvalidPathError,
                "Invalid target path",
            ),
        ],
        ids=[
            "01_append_array",
            "02_insert_start",
            "03_insert_end",
            "04_nested_array",
            "05_add_to_object_in_array",
            "06_add_to_array_in_array",
            "07_add_to_nested_structure",
            "08_add_to_deep_structure",
            "09_replace_existing",
            "10_replace_nested",
            "11_replace_whole_doc",
            "12_valid_move",
            "13_valid_copy",
            "14_array_out_of_bounds",
            "15_invalid_array_index_leading_zero",
            "16_invalid_array_index_double_zero",
            "17_invalid_array_index_float",
            "18_invalid_array_index_invalid_char",
            "19_invalid_nested_path",
            "20_nonexistent_parent",
            "21_wrong_parent_type",
            "22_invalid_move_from_leading_zero",
            "23_invalid_copy_from_out_of_bounds",
            "24_replace_nonexistent",
            "25_replace_invalid_index",
            "26_replace_wrong_type",
            "27_invalid_array_index_add",
            "28_invalid_array_index_add_double_zero",
            "29_invalid_object_path_on_array",
            "30_invalid_object_path_on_nested_array",
        ],
    )
    def test_generic_delta_path_validation_with_initial_value(  # noqa: PLR0913
        self,
        op: DeltaOpType,
        path: str,
        value: Any,
        from_: str | None,
        expected_error: type[Exception] | None,
        error_match: str | None,
    ) -> None:
        """Test path validation with initial values.

        Tests validation of paths against actual data structures, including:
        - Array operations (append, insert, replace)
        - Object operations (add, replace)
        - Nested structure operations
        - Empty path operations (whole document)
        - Parent path validation for add operations
        - Type validation
        - Move/copy operations
        - Invalid path scenarios

        Args:
            path: The path to validate
            op: The operation type
            from_: The from_ path for move/copy operations
            expected_error: Expected exception type, if any
            error_match: Expected error message pattern, if any
        """
        initial = {
            "array": [1, 2, 3],
            "obj_array": [{"key": "value"}],
            "arr_array": [[{"key": "value"}]],
            "nested": {
                "array": [4, 5, 6],
                "deep": {"value": True},
            },
            "": {
                "": [1, 2, 3],
            },
        }

        delta = GenericDelta(op=op, path=path, value=value, from_=from_)

        if expected_error is None:
            # Should succeed
            validate_delta_path(initial, delta)
        else:
            # Should raise expected error
            with pytest.raises(expected_error, match=error_match):
                validate_delta_path(initial, delta)


########################################
# Tests for compute_generic_delta
########################################


class TestComputeGenericDeltas:
    @pytest.mark.parametrize(
        ("old_val", "new_val", "expected_ops"),
        [
            # 1) Same string => no delta
            ("hello", "hello", []),
            # 2) String replaced entirely
            ("hello", "world", [GenericDelta(op="replace", path="", value="world")]),
            # 3) String extended
            (
                "hello",
                "hello world",
                [GenericDelta(op="concat_string", path="", value=" world")],
            ),
            # 4) Same int => no delta
            (42, 42, []),
            # 5) int new > old => inc
            (10, 15, [GenericDelta(op="inc", path="", value=5)]),
            # 6) int new < old => replace
            (15, 10, [GenericDelta(op="replace", path="", value=10)]),
            # 7) Different types => replace
            ("123", 123, [GenericDelta(op="replace", path="", value=123)]),
            # 8) None to something => replace
            (None, True, [GenericDelta(op="replace", path="", value=True)]),
            # 9) Lists are same
            ([1, 2, 3], [1, 2, 3], []),
            # 10) List with new items
            (
                [1, 2, 3],
                [1, 2, 3, 4, 5],
                [
                    GenericDelta(op="add", path="/3", value=4),
                    GenericDelta(op="add", path="/4", value=5),
                ],
            ),
            # 11) List last item is a string extended
            (
                ["hello"],
                ["hello world"],
                [GenericDelta(op="concat_string", path="/0", value=" world")],
            ),
            # 12) Dict: same
            ({"a": 1}, {"a": 1}, []),
            # 13) Dict: remove key
            (
                {"a": 1, "b": 2},
                {"a": 1},
                [GenericDelta(op="remove", path="/b")],
            ),
            # 14) Dict: add key
            (
                {"a": 1},
                {"a": 1, "b": 2},
                [GenericDelta(op="add", path="/b", value=2)],
            ),
            # 15) Dict: changed key
            (
                {"a": 1},
                {"a": 2},
                [
                    GenericDelta(op="inc", path="/a", value=1),
                ],  # since int changed from 1 -> 2
            ),
            # 16) Boolean False to True => replace
            (False, True, [GenericDelta(op="replace", path="", value=True)]),
            # 17) Boolean True to False => replace
            (True, False, [GenericDelta(op="replace", path="", value=False)]),
            # 18) Boolean False to False => no delta
            (False, False, []),
            # 19) Boolean True to True => no delta
            (True, True, []),
            # 20) Boolean False to True (nested structure)
            (
                {"a": False},
                {"a": True},
                [GenericDelta(op="replace", path="/a", value=True)],
            ),
            # 21) Boolean True to False (nested structure)
            (
                {"a": True},
                {"a": False},
                [GenericDelta(op="replace", path="/a", value=False)],
            ),
        ],
        ids=[
            "01_same_string",
            "02_string_replaced",
            "03_string_extended",
            "04_same_int",
            "05_int_new_gt_old",
            "06_int_new_lt_old",
            "07_different_types",
            "08_none_to_something",
            "09_lists_same",
            "10_list_with_new_items",
            "11_list_last_item_extended",
            "12_dict_same",
            "13_dict_remove_key",
            "14_dict_add_key",
            "15_dict_changed_key",
            "16_bool_false_to_true",
            "17_bool_true_to_false",
            "18_bool_false_to_false",
            "19_bool_true_to_true",
            "20_bool_false_to_true_nested",
            "21_bool_true_to_false_nested",
        ],
    )
    def test_compute_generic_delta(self, old_val, new_val, expected_ops):
        ops = compute_generic_deltas(old_val, new_val, path="")
        # Compare lists of GenericDelta objects
        # Because we can't directly compare dataclasses with lists unless you
        # explicitly handle them, do a length and then field-by-field check:
        assert len(ops) == len(expected_ops), f"Expected {expected_ops} got {ops}"
        for o, e in zip(ops, expected_ops, strict=False):
            assert o.op == e.op
            assert o.path == e.path
            assert o.value == e.value

    def test_compute_generic_delta_nested_lists_and_dicts(self):
        """
        Tests a more complex structure with nested lists and dicts.
        """
        old = {
            "name": "Alice",
            "scores": [10, 20],
            "details": {
                "hobbies": ["reading"],
            },
        }
        new = {
            "name": "Alice B",  # string extended
            "scores": [10, 20, 30],  # add to array
            "details": {
                "hobbies": ["reading", "chess"],  # add to array
                "age": 30,  # new key
            },
        }

        ops = compute_generic_deltas(old, new)
        # We expect:
        # 1) "name" => "concat_string" with " B"
        # 2) "scores" => add with value 30 at index 2
        # 3) "details/hobbies" => add with value "chess" at index 1
        # 4) "details" => add with value 30 at path "/details/age"

        # Let's break down the expected ops:
        expected = [
            GenericDelta(op="concat_string", path="/name", value=" B"),
            GenericDelta(op="add", path="/scores/2", value=30),
            GenericDelta(op="add", path="/details/hobbies/1", value="chess"),
            GenericDelta(op="add", path="/details/age", value=30),
        ]

        # Sort them on ops and path, before zip
        expected = sorted(expected, key=lambda x: (x.op, x.path))
        ops = sorted(ops, key=lambda x: (x.op, x.path))

        assert len(ops) == len(expected), f"Got ops: {ops}"
        for actual, exp in zip(ops, expected, strict=False):
            assert actual.op == exp.op
            assert actual.path == exp.path
            assert actual.value == exp.value


########################################
# Tests for combine_generic_deltas
########################################


class TestCombineGenericDeltas:
    @pytest.mark.parametrize(
        ("initial_value", "deltas", "expected_result"),
        [
            # 1) String concatenation
            (
                "hello",
                [GenericDelta(op="concat_string", path="", value=" world")],
                "hello world",
            ),
            # 2) Integer increment
            (10, [GenericDelta(op="inc", path="", value=5)], 15),
            # 3) List add
            (
                [1, 2, 3],
                [GenericDelta(op="add", path="/3", value=4)],
                [1, 2, 3, 4],
            ),
            # 4) Dict add
            (
                {"a": 1},
                [GenericDelta(op="add", path="/b", value=2)],
                {"a": 1, "b": 2},
            ),
            # 5) Add object to array
            (
                {"a": [1, 2, 3]},
                [GenericDelta(op="add", path="/a/0", value={"b": "test"})],
                {"a": [{"b": "test"}, 1, 2, 3]},
            ),
            # 6) Add object to object in array
            (
                {"a": [{"c": "foo"}]},
                [GenericDelta(op="add", path="/a/0/b", value="test")],
                {"a": [{"b": "test", "c": "foo"}]},
            ),
            # 7) Add object to object in array in array
            (
                {"a": [[{"c": "foo"}]]},
                [GenericDelta(op="add", path="/a/0/0/b", value="test")],
                {"a": [[{"b": "test", "c": "foo"}]]},
            ),
            # 8) Multiple operations on nested structure
            (
                {"name": "Alice", "scores": [10]},
                [
                    GenericDelta(op="concat_string", path="/name", value=" B"),
                    GenericDelta(op="add", path="/scores/-", value=20),
                    GenericDelta(op="add", path="/scores/-", value=30),
                ],
                {"name": "Alice B", "scores": [10, 20, 30]},
            ),
            # 9) Remove operation
            (
                {"a": 1, "b": 2},
                [GenericDelta(op="remove", path="/b")],
                {"a": 1},
            ),
            # 10) Replace operation
            (
                {"value": "old"},
                [GenericDelta(op="replace", path="/value", value="new")],
                {"value": "new"},
            ),
            # 11) Complex nested operations
            (
                {
                    "name": "Alice",
                    "details": {
                        "hobbies": ["reading"],
                        "age": 25,
                    },
                },
                [
                    GenericDelta(op="concat_string", path="/name", value=" B"),
                    GenericDelta(op="add", path="/details/hobbies/1", value="chess"),
                    GenericDelta(op="inc", path="/details/age", value=5),
                ],
                {
                    "name": "Alice B",
                    "details": {
                        "hobbies": ["reading", "chess"],
                        "age": 30,
                    },
                },
            ),
            # 12) Operations with None initial value
            (
                None,
                [
                    GenericDelta(op="add", path="/a", value=1),
                    GenericDelta(op="add", path="/b", value=2),
                ],
                {"a": 1, "b": 2},
            ),
            # 13) Empty deltas list
            ({"a": 1}, [], {"a": 1}),
            # 14) Move operation
            (
                {"foo": "bar", "baz": "qux"},
                [GenericDelta(op="move", path="/target", from_="/foo")],
                {"baz": "qux", "target": "bar"},
            ),
            # 15) Copy operation
            (
                {"foo": "bar"},
                [GenericDelta(op="copy", path="/baz", from_="/foo")],
                {"foo": "bar", "baz": "bar"},
            ),
            # 16) Test operation (should not modify the document)
            (
                {"foo": "bar"},
                [GenericDelta(op="test", path="/foo", value="bar")],
                {"foo": "bar"},
            ),
        ],
        ids=[
            "01_concat_string",
            "02_inc",
            "03_list_add",
            "04_dict_add",
            "05_add_obj_to_arr",
            "06_add_obj_to_obj_in_arr",
            "07_add_obj_to_obj_in_arr_in_arr",
            "08_nested_ops",
            "09_remove",
            "10_replace",
            "11_complex_nested",
            "12_none_initial",
            "13_empty_deltas",
            "14_move",
            "15_copy",
            "16_test",
        ],
    )
    def test_combine_generic_deltas(self, initial_value, deltas, expected_result):
        """Test combining GenericDelta objects back into a single object."""
        result = combine_generic_deltas(deltas, initial_value)
        assert result == expected_result

    def test_combine_generic_deltas_complex_nested(self):
        """Test a more complex scenario with nested structures and
        multiple operations."""
        initial = {
            "user": {
                "name": "Alice",
                "scores": [10, 20],
                "metadata": {
                    "tags": ["beginner"],
                    "level": 1,
                },
            },
        }

        deltas = [
            GenericDelta(op="concat_string", path="/user/name", value=" Smith"),
            GenericDelta(op="add", path="/user/scores/-", value=30),
            GenericDelta(op="add", path="/user/metadata/status", value="active"),
            GenericDelta(op="add", path="/user/metadata/tags/-", value="intermediate"),
            GenericDelta(op="inc", path="/user/metadata/level", value=2),
        ]

        expected = {
            "user": {
                "name": "Alice Smith",
                "scores": [10, 20, 30],
                "metadata": {
                    "tags": ["beginner", "intermediate"],
                    "level": 3,
                    "status": "active",
                },
            },
        }

        result = combine_generic_deltas(deltas, initial)
        assert result == expected

    def test_combine_generic_deltas_invalid_path(self):
        """Test error case where path is invalid."""
        invalid_path_delta = GenericDelta(
            op="remove",
            path="/invalid/path",
        )
        with pytest.raises(
            InvalidPathError,
            match="Invalid target path '/invalid/path'",
        ) as exc_info:
            combine_generic_deltas(
                [invalid_path_delta],
                {"valid": "path"},
            )
        assert exc_info.value.path == "/invalid/path"
        assert exc_info.value.delta_object == invalid_path_delta

    def test_combine_generic_deltas_invalid_operation(self):
        """Test error case where operation is invalid."""
        # Test with an invalid operation type
        with pytest.raises(
            ValueError,
            match="Invalid value for 'op': 'invalid_op'",
        ) as exc_info:
            GenericDelta(op="invalid_op", path="/test", value="test")  # type: ignore

        # Verify the error message
        assert "Invalid value for 'op': 'invalid_op'" in str(exc_info.value)

    def test_combine_generic_deltas_rfc6901_paths(self):
        """Test JSON Pointer paths according to RFC 6901 examples."""
        # Initial document matching RFC 6901 example
        initial = {
            "foo": ["bar", "baz"],
            "": 0,
            "a/b": 1,
            "c%d": 2,
            "e^f": 3,
            "g|h": 4,
            "i\\j": 5,
            'k"l': 6,
            " ": 7,
            "m~n": 8,
        }

        # Test various RFC 6901 path scenarios
        deltas = [
            # Test empty string key (not empty path)
            GenericDelta(op="inc", path="/", value=1),  # Refers to the empty string key
            # Test array access
            GenericDelta(op="replace", path="/foo/0", value="qux"),
            # Test escaped forward slash
            GenericDelta(op="inc", path="/a~1b", value=1),
            # Test escaped tilde
            GenericDelta(op="inc", path="/m~0n", value=1),
            # Test special characters
            GenericDelta(op="inc", path="/c%d", value=1),
            GenericDelta(op="inc", path="/e^f", value=1),
            GenericDelta(op="inc", path="/g|h", value=1),
            GenericDelta(op="inc", path="/i\\j", value=1),
            GenericDelta(op="inc", path='/k"l', value=1),
            GenericDelta(op="inc", path="/ ", value=1),  # Space character as key
        ]

        expected = {
            "foo": ["qux", "baz"],
            "": 1,
            "a/b": 2,
            "c%d": 3,
            "e^f": 4,
            "g|h": 5,
            "i\\j": 6,
            'k"l': 7,
            " ": 8,
            "m~n": 9,
        }

        result = combine_generic_deltas(deltas, initial)
        assert result == expected

    # Add a new test specifically for empty string path (whole document)
    def test_combine_generic_deltas_empty_path(self):
        """Test empty string path referring to whole document according to RFC 6901."""
        initial = {"foo": "bar"}

        deltas = [
            # Empty string path refers to the whole document
            GenericDelta(op="replace", path="", value={"completely": "new"}),
        ]

        expected = {"completely": "new"}

        result = combine_generic_deltas(deltas, initial)
        assert result == expected

    @pytest.mark.parametrize(
        ("initial_value", "delta", "expected_result"),
        [
            # Replace at specific index
            (
                {"foo": ["bar", "baz"]},
                GenericDelta(op="replace", path="/foo/0", value="qux"),
                {"foo": ["qux", "baz"]},
            ),
            # Append using "-" index
            (
                {"foo": ["bar", "baz"]},
                GenericDelta(op="add", path="/foo/-", value="last"),
                {"foo": ["bar", "baz", "last"]},
            ),
            # Add at next sequential index
            (
                {"numbers": [1, 2, 3]},
                GenericDelta(op="add", path="/numbers/3", value=4),
                {"numbers": [1, 2, 3, 4]},
            ),
        ],
    )
    def test_combine_generic_deltas_array_operations(
        self,
        initial_value: dict,
        delta: GenericDelta,
        expected_result: dict,
    ) -> None:
        """Test array operations according to RFC 6901."""
        result = combine_generic_deltas([delta], initial_value)
        assert result == expected_result

    # Add a test for multiple array operations in sequence
    def test_combine_generic_deltas_array_operations_sequence(self):
        """Test multiple array operations in sequence."""
        initial = {
            "foo": ["bar", "baz"],
            "numbers": [1, 2, 3],
        }

        deltas = [
            # First modify foo array
            GenericDelta(op="replace", path="/foo/0", value="qux"),
            GenericDelta(op="add", path="/foo/-", value="last"),
            # Then modify numbers array
            GenericDelta(op="add", path="/numbers/-", value=4),
        ]

        expected = {
            "foo": ["qux", "baz", "last"],
            "numbers": [1, 2, 3, 4],
        }

        result = combine_generic_deltas(deltas, initial)
        assert result == expected

    @pytest.mark.parametrize(
        ("initial_value", "delta", "expected_result"),
        [
            # 1. Nested array in object in array
            (
                {"users": [{"name": "Alice", "scores": [10, 20]}]},
                GenericDelta(op="add", path="/users/0/scores/-", value=30),
                {"users": [{"name": "Alice", "scores": [10, 20, 30]}]},
            ),
            # 2. Replace in nested array
            (
                {
                    "users": [
                        {"name": "Alice", "scores": [10, 20]},
                        {"name": "Bob", "scores": [15, 25]},
                    ],
                },
                GenericDelta(op="replace", path="/users/1/scores/0", value=16),
                {
                    "users": [
                        {"name": "Alice", "scores": [10, 20]},
                        {"name": "Bob", "scores": [16, 25]},
                    ],
                },
            ),
            # 3. Path with escaped characters
            (
                {"metadata": {"tags/special": ["test~1", "test~0"]}},
                GenericDelta(
                    op="add",
                    path="/metadata/tags~1special/-",
                    value="test/2",
                ),
                {"metadata": {"tags/special": ["test~1", "test~0", "test/2"]}},
            ),
            # 4. Complex nested path with escapes
            (
                {"metadata": {"complex~1path": {"a/b": [1, 2]}}},
                GenericDelta(
                    op="add",
                    path="/metadata/complex~01path/a~1b/-",
                    value=3,
                ),
                {"metadata": {"complex~1path": {"a/b": [1, 2, 3]}}},
            ),
        ],
        ids=[
            "01_append_to_nested_array",
            "02_replace_in_nested_array",
            "03_append_with_escaped_path",
            "04_append_with_complex_escaped_path",
        ],
    )
    def test_combine_generic_deltas_nested_array_dict(
        self,
        initial_value: dict,
        delta: GenericDelta,
        expected_result: dict,
    ):
        """Test complex nested array and dictionary paths."""
        result = combine_generic_deltas([delta], initial_value)
        assert result == expected_result


########################################
# Test data for JSON Patch compliance
########################################


def load_json_patch_test_cases() -> list[dict]:
    """
    Load test cases from the official JSON Patch test suite.
    """
    urls = [
        "https://raw.githubusercontent.com/json-patch/json-patch-tests/refs/heads/master/tests.json",
        "https://raw.githubusercontent.com/json-patch/json-patch-tests/refs/heads/master/spec_tests.json",
    ]

    import json

    import requests

    test_cases = []
    for url in urls:
        response = requests.get(url)
        response.raise_for_status()
        test_cases.extend(json.loads(response.text))

    # Filter out test cases that are marked as disabled or have error expectations
    # We're only interested in valid test cases for now
    valid_test_cases = [
        case
        for case in test_cases
        if not case.get("disabled", False) and "error" not in case
    ]

    return valid_test_cases


# Load test cases at module level
JSON_PATCH_TEST_CASES = load_json_patch_test_cases()


class TestStandardsTestSuiteCompliance:
    @pytest.mark.parametrize(
        "test_case",
        JSON_PATCH_TEST_CASES,
        ids=lambda x: x.get("comment", "no_comment"),
    )
    def test_json_patch_compliance(self, test_case):
        """
        Test our GenericDelta implementation against the official JSON Patch test suite.
        """
        doc = test_case["doc"]
        expected = test_case["expected"]
        patches = [
            GenericDelta(
                op=patch.get("op", ""),
                path=patch.get("path", ""),
                value=patch.get("value", NO_VALUE) if "value" in patch else NO_VALUE,
                from_=patch.get("from", None) if "from" in patch else None,
            )
            for patch in test_case["patch"]
        ]

        # Apply the patches in sequence
        result = doc
        for i, patch in enumerate(patches):
            try:
                result = combine_generic_deltas([patch], result)
            except Exception as e:
                # Add detailed logging for failures
                print("\nTest case details:")
                print(f"Comment: {test_case.get('comment', 'No comment')}")
                print(f"Initial document: {doc}")
                print(f"Expected result: {expected}")
                print(f"Patches: {test_case['patch']}")
                print(f"Failed at patch {i}: {patch}")
                print(f"Current result before failure: {result}")
                print(f"Error: {e!s}")
                raise

        # Compare the result with expected
        try:
            assert result == expected
        except AssertionError:
            # Add detailed logging for assertion failures
            print("\nTest case details:")
            print(f"Comment: {test_case.get('comment', 'No comment')}")
            print(f"Initial document: {doc}")
            print(f"Expected result: {expected}")
            print(f"Patches: {test_case['patch']}")
            print(f"Actual result: {result}")
            raise
