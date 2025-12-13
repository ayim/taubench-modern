"""Unit tests for transform_json and create_data_frame_from_json functions.

These tests focus on the individual functions and their error handling,
without duplicating the integration tests which test the full flow.
"""

import json
from unittest.mock import MagicMock, patch

import pytest


class TestTransformJson:
    """Unit tests for the transform_json function."""

    @pytest.mark.asyncio
    async def test_transform_with_direct_json_identity(self):
        """Test transform_json with direct JSON input and identity expression."""
        from agent_platform.server.auth.handlers import AuthedUser
        from agent_platform.server.kernel.data_frames import _DataFrameTools

        # Setup
        user = MagicMock(spec=AuthedUser)
        storage = MagicMock()
        tools = _DataFrameTools(
            user=user,
            tid="test_thread",
            name_to_data_frame={},
            storage=storage,
            thread_state=None,
        )

        # Test with simple JSON object
        json_input = json.dumps({"name": "Alice", "age": 30})
        result = await tools._transform_json(json_input, ".")

        assert "result" in result
        # JQ always returns a list of results
        assert result["result"] == [{"name": "Alice", "age": 30}]
        assert "error_code" not in result

    @pytest.mark.asyncio
    async def test_transform_with_direct_json_array_extract(self):
        """Test transform_json extracting array elements."""
        from agent_platform.server.auth.handlers import AuthedUser
        from agent_platform.server.kernel.data_frames import _DataFrameTools

        user = MagicMock(spec=AuthedUser)
        storage = MagicMock()
        tools = _DataFrameTools(
            user=user,
            tid="test_thread",
            name_to_data_frame={},
            storage=storage,
            thread_state=None,
        )

        json_input = json.dumps({"items": [{"x": 1}, {"x": 2}, {"x": 3}]})
        result = await tools._transform_json(json_input, ".items[]")

        assert "result" in result
        # JQ expression ".items[]" produces multiple results
        assert isinstance(result["result"], list)
        assert len(result["result"]) == 3
        assert result["result"] == [{"x": 1}, {"x": 2}, {"x": 3}]

    @pytest.mark.asyncio
    async def test_transform_with_direct_json_filter(self):
        """Test transform_json with filtering expression."""
        from agent_platform.server.auth.handlers import AuthedUser
        from agent_platform.server.kernel.data_frames import _DataFrameTools

        user = MagicMock(spec=AuthedUser)
        storage = MagicMock()
        tools = _DataFrameTools(
            user=user,
            tid="test_thread",
            name_to_data_frame={},
            storage=storage,
            thread_state=None,
        )

        json_input = json.dumps({"products": [{"name": "A", "price": 10}, {"name": "B", "price": 25}]})
        result = await tools._transform_json(json_input, ".products[] | select(.price > 15)")

        assert "result" in result
        # JQ always returns a list of results
        assert result["result"] == [{"name": "B", "price": 25}]

    @pytest.mark.asyncio
    async def test_transform_with_direct_json_map_transform(self):
        """Test transform_json with mapping/transformation."""
        from agent_platform.server.auth.handlers import AuthedUser
        from agent_platform.server.kernel.data_frames import _DataFrameTools

        user = MagicMock(spec=AuthedUser)
        storage = MagicMock()
        tools = _DataFrameTools(
            user=user,
            tid="test_thread",
            name_to_data_frame={},
            storage=storage,
            thread_state=None,
        )

        json_input = json.dumps({"items": [{"qty": 2, "price": 10}, {"qty": 3, "price": 5}]})
        result = await tools._transform_json(json_input, ".items[] | {qty, total: (.qty * .price)}")

        assert "result" in result
        assert isinstance(result["result"], list)
        assert len(result["result"]) == 2
        assert result["result"][0] == {"qty": 2, "total": 20}
        assert result["result"][1] == {"qty": 3, "total": 15}

    @pytest.mark.asyncio
    async def test_transform_with_invalid_jq_expression(self):
        """Test transform_json with invalid JQ expression."""
        from agent_platform.server.auth.handlers import AuthedUser
        from agent_platform.server.kernel.data_frames import _DataFrameTools

        user = MagicMock(spec=AuthedUser)
        storage = MagicMock()
        tools = _DataFrameTools(
            user=user,
            tid="test_thread",
            name_to_data_frame={},
            storage=storage,
            thread_state=None,
        )

        json_input = json.dumps({"name": "test"})
        # Invalid JQ syntax
        result = await tools._transform_json(json_input, ".[[[invalid")

        assert "error_code" in result
        assert result["error_code"] == "jq_error"
        assert "message" in result

    @pytest.mark.asyncio
    async def test_transform_with_message_reference(self):
        """Test transform_json with message reference (out.tool_name[index])."""
        from agent_platform.core.kernel_interfaces.thread_state import ThreadStateInterface
        from agent_platform.server.auth.handlers import AuthedUser
        from agent_platform.server.kernel.data_frames import _DataFrameTools

        user = MagicMock(spec=AuthedUser)
        storage = MagicMock()

        # Mock thread_state with get_tool_result_by_ref
        mock_thread_state = MagicMock(spec=ThreadStateInterface)

        tools = _DataFrameTools(
            user=user,
            tid="test_thread",
            name_to_data_frame={},
            storage=storage,
            thread_state=mock_thread_state,
        )

        # Mock the get_tool_result_by_ref function
        mock_data = {"items": [{"name": "Product A"}, {"name": "Product B"}]}

        with patch("agent_platform.server.kernel.thread_utils.get_tool_result_by_ref") as mock_get_result:
            mock_get_result.return_value = mock_data

            result = await tools._transform_json("out.extract_document[1]", ".items[]")

            # Verify the function was called with correct args
            mock_get_result.assert_called_once_with(mock_thread_state, "out.extract_document[1]")

            # Verify the result
            assert "result" in result
            assert isinstance(result["result"], list)
            assert len(result["result"]) == 2

    @pytest.mark.asyncio
    async def test_transform_with_message_reference_functions_prefix(self):
        """Test transform_json with message reference using .functions prefix.

        LLMs often generate references like out.functions.tool_name[index] because
        tools are exposed under /functions path. This should be normalized to
        out.tool_name[index] format automatically.
        """
        from agent_platform.core.kernel_interfaces.thread_state import ThreadStateInterface
        from agent_platform.server.auth.handlers import AuthedUser
        from agent_platform.server.kernel.data_frames import _DataFrameTools

        user = MagicMock(spec=AuthedUser)
        storage = MagicMock()

        # Mock thread_state with get_tool_result_by_ref
        mock_thread_state = MagicMock(spec=ThreadStateInterface)

        tools = _DataFrameTools(
            user=user,
            tid="test_thread",
            name_to_data_frame={},
            storage=storage,
            thread_state=mock_thread_state,
        )

        # Mock the get_tool_result_by_ref function
        mock_data = {"items": [{"name": "Product A"}, {"name": "Product B"}]}

        with patch("agent_platform.server.kernel.thread_utils.get_tool_result_by_ref") as mock_get_result:
            mock_get_result.return_value = mock_data

            # Use the .functions prefix format that LLMs often generate
            result = await tools._transform_json("out.functions.extract_document[1]", ".items[]")

            # Verify the function was called with the same reference (normalization happens inside)
            mock_get_result.assert_called_once_with(mock_thread_state, "out.functions.extract_document[1]")

            # Verify the result
            assert "result" in result
            assert isinstance(result["result"], list)
            assert len(result["result"]) == 2

    @pytest.mark.asyncio
    async def test_transform_with_message_reference_error(self):
        """Test transform_json when message reference lookup fails."""
        from agent_platform.core.kernel_interfaces.thread_state import ThreadStateInterface
        from agent_platform.server.auth.handlers import AuthedUser
        from agent_platform.server.kernel.data_frames import _DataFrameTools

        user = MagicMock(spec=AuthedUser)
        storage = MagicMock()
        mock_thread_state = MagicMock(spec=ThreadStateInterface)

        tools = _DataFrameTools(
            user=user,
            tid="test_thread",
            name_to_data_frame={},
            storage=storage,
            thread_state=mock_thread_state,
        )

        # Mock get_tool_result_by_ref to return an error
        with patch("agent_platform.server.kernel.thread_utils.get_tool_result_by_ref") as mock_get_result:
            mock_get_result.return_value = {
                "error_code": "tool_not_found",
                "message": "No completed tool results found for tool 'nonexistent'",
            }

            result = await tools._transform_json("out.nonexistent[1]", ".")

            # Should propagate the error from get_tool_result_by_ref
            assert "error_code" in result
            assert result["error_code"] == "tool_not_found"

    @pytest.mark.asyncio
    async def test_transform_without_thread_state_for_reference(self):
        """Test that transform_json returns error when trying to use reference without
        thread_state."""
        from agent_platform.server.auth.handlers import AuthedUser
        from agent_platform.server.kernel.data_frames import _DataFrameTools

        user = MagicMock(spec=AuthedUser)
        storage = MagicMock()

        # No thread_state provided
        tools = _DataFrameTools(
            user=user,
            tid="test_thread",
            name_to_data_frame={},
            storage=storage,
            thread_state=None,
        )

        # Try to use a message reference (not valid JSON)
        result = await tools._transform_json("out.some_tool[1]", ".")

        assert "error_code" in result
        assert result["error_code"] == "thread_state_not_available"
        assert "message" in result

    @pytest.mark.asyncio
    async def test_transform_with_nested_json(self):
        """Test transform_json with deeply nested JSON."""
        from agent_platform.server.auth.handlers import AuthedUser
        from agent_platform.server.kernel.data_frames import _DataFrameTools

        user = MagicMock(spec=AuthedUser)
        storage = MagicMock()
        tools = _DataFrameTools(
            user=user,
            tid="test_thread",
            name_to_data_frame={},
            storage=storage,
            thread_state=None,
        )

        json_input = json.dumps(
            {
                "invoice": {
                    "number": "INV-123",
                    "customer": {"name": "Acme Corp", "id": "C-456"},
                    "line_items": [{"product": "Widget", "qty": 5}],
                }
            }
        )

        # Navigate deep and include parent data
        jq_expr = ". as $root | .invoice.line_items[] | {product, qty, invoice_number: $root.invoice.number}"
        result = await tools._transform_json(json_input, jq_expr)

        assert "result" in result
        # JQ always returns a list of results
        assert result["result"] == [{"product": "Widget", "qty": 5, "invoice_number": "INV-123"}]
