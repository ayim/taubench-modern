"""Integration tests for creating data frames from JSON data."""

import pytest


def _prepare_result_for_regression(result, exclude_fields=None):
    """Prepare a result dict for data_regression.check() by removing dynamic fields.

    Args:
        result: The result dict from the API call
        exclude_fields: Additional fields to exclude beyond default dynamic fields

    Returns:
        A cleaned dict ready for regression checking
    """
    if exclude_fields is None:
        exclude_fields = set()
    else:
        exclude_fields = set(exclude_fields)

    # Always exclude these fields as they change on each run/session
    exclude_fields.update(["data_frame_id", "created_at", "thread_id"])

    # Remove excluded fields
    result_for_check = {k: v for k, v in result.items() if k not in exclude_fields}

    # Sort column_headers for deterministic comparison
    if "column_headers" in result_for_check:
        result_for_check["column_headers"] = sorted(result_for_check["column_headers"])

    return result_for_check


@pytest.mark.integration
def test_create_data_frame_from_json(base_url_agent_server_session, data_regression):
    """Test creating a data frame from JSON data."""
    from agent_platform.orchestrator.agent_server_client import AgentServerClient

    with AgentServerClient(base_url_agent_server_session) as agent_client:
        agent_id = agent_client.create_agent_and_return_agent_id(
            action_packages=[],
            platform_configs=[
                {
                    "kind": "openai",
                    "openai_api_key": "unused",
                    "models": {"openai": ["gpt-5-low"]},
                },
            ],
        )
        thread_id = agent_client.create_thread_and_return_thread_id(agent_id)

        # Test simple flat JSON
        json_data = {
            "invoice_number": "INV-123",
            "total": 1000.50,
            "date": "2024-01-15",
        }

        result = agent_client.create_data_frame_from_json(
            thread_id=thread_id,
            json_data=json_data,
            jq_expression=".",  # Identity - convert single object to single row
            name="simple_invoice",
        )

        # Verify data_frame_id exists, then prepare for regression check
        assert result["data_frame_id"] is not None
        data_regression.check(_prepare_result_for_regression(result))


@pytest.mark.integration
def test_create_data_frame_from_json_with_array(base_url_agent_server_session, data_regression):
    """Test creating a data frame from JSON with an array."""
    from agent_platform.orchestrator.agent_server_client import AgentServerClient

    with AgentServerClient(base_url_agent_server_session) as agent_client:
        agent_id = agent_client.create_agent_and_return_agent_id(
            action_packages=[],
            platform_configs=[
                {
                    "kind": "openai",
                    "openai_api_key": "unused",
                    "models": {"openai": ["gpt-5-low"]},
                },
            ],
        )
        thread_id = agent_client.create_thread_and_return_thread_id(agent_id)

        # Test JSON with array of transactions
        json_data = {
            "invoice_number": "INV-456",
            "line_items": [
                {"product": "Widget A", "quantity": 2, "price": 10.00},
                {"product": "Widget B", "quantity": 1, "price": 20.00},
                {"product": "Widget C", "quantity": 3, "price": 15.00},
            ],
        }

        result = agent_client.create_data_frame_from_json(
            thread_id=thread_id,
            json_data=json_data,
            jq_expression=(
                ". as $root | .line_items[] | {invoice_number: $root.invoice_number, product, quantity, price}"
            ),
            name="invoice_with_items",
        )

        # Verify data_frame_id exists, then prepare for regression check
        assert result["data_frame_id"] is not None
        data_regression.check(_prepare_result_for_regression(result))


@pytest.mark.integration
def test_create_data_frame_from_json_with_schema_fields(base_url_agent_server_session, data_regression):
    """Test creating a data frame from JSON with schema fields."""
    from agent_platform.orchestrator.agent_server_client import AgentServerClient

    with AgentServerClient(base_url_agent_server_session) as agent_client:
        agent_id = agent_client.create_agent_and_return_agent_id(
            action_packages=[],
            platform_configs=[
                {
                    "kind": "openai",
                    "openai_api_key": "unused",
                    "models": {"openai": ["gpt-5-low"]},
                },
            ],
        )
        thread_id = agent_client.create_thread_and_return_thread_id(agent_id)

        # Test JSON with multiple arrays, use schema to choose which one
        json_data = {
            "metadata": {"doc_id": "DOC-789"},
            "items": [
                {"name": "Item 1", "value": 100},
                {"name": "Item 2", "value": 200},
            ],
            "other_data": [
                {"x": 1, "y": 2, "z": 3},
                {"x": 4, "y": 5, "z": 6},
                {"x": 7, "y": 8, "z": 9},
            ],
        }

        # Use JQ expression to select items and include metadata
        result = agent_client.create_data_frame_from_json(
            thread_id=thread_id,
            json_data=json_data,
            jq_expression=". as $root | .items[] | {name, value, doc_id: $root.metadata.doc_id}",
            name="selected_items",
        )

        # Verify data_frame_id exists, then prepare for regression check
        assert result["data_frame_id"] is not None
        data_regression.check(_prepare_result_for_regression(result))


@pytest.mark.integration
def test_create_data_frame_from_json_complex_nested(base_url_agent_server_session, data_regression):
    """Test creating a data frame from complex nested JSON."""
    from agent_platform.orchestrator.agent_server_client import AgentServerClient

    with AgentServerClient(base_url_agent_server_session) as agent_client:
        agent_id = agent_client.create_agent_and_return_agent_id(
            action_packages=[],
            platform_configs=[
                {
                    "kind": "openai",
                    "openai_api_key": "unused",
                    "models": {"openai": ["gpt-5-low"]},
                },
            ],
        )
        thread_id = agent_client.create_thread_and_return_thread_id(agent_id)

        # Complex invoice-like structure
        json_data = {
            "company_info": {
                "name": "ACME Corp",
                "address": "123 Business St",
                "phone": "555-0123",
            },
            "invoice_details": {
                "number": "INV-2024-001",
                "date": "2024-01-15",
                "due_date": "2024-02-15",
            },
            "items": [
                {
                    "product": "Professional Services",
                    "hours": 40,
                    "rate": 150.00,
                    "total": 6000.00,
                },
                {
                    "product": "Software License",
                    "hours": None,
                    "rate": 500.00,
                    "total": 500.00,
                },
            ],
            "summary": {"subtotal": 6500.00, "tax": 520.00, "grand_total": 7020.00},
        }

        result = agent_client.create_data_frame_from_json(
            thread_id=thread_id,
            json_data=json_data,
            jq_expression=(
                ". as $root | .items[] | "
                "{company_name: $root.company_info.name, "
                "invoice_number: $root.invoice_details.number, "
                "product, hours, rate, total}"
            ),
            name="complex_invoice",
        )

        # Verify that None values are properly preserved (not NaN)
        hours_idx = result["column_headers"].index("hours")
        sample_rows = result["sample_rows"]
        assert sample_rows[1][hours_idx] is None  # Critical check for None preservation

        # Verify data_frame_id exists, then prepare for regression check
        assert result["data_frame_id"] is not None
        data_regression.check(_prepare_result_for_regression(result))

        # Now verify we can query the data frame
        data_frames = agent_client.get_data_frames(thread_id, num_samples=5)
        assert len(data_frames) == 1
        df = data_frames[0]

        # Verify None is preserved when querying
        df_hours_idx = df["column_headers"].index("hours")
        assert df["sample_rows"][1][df_hours_idx] is None


@pytest.mark.integration
def test_create_multiple_data_frames_from_json(base_url_agent_server_session, data_regression):
    """Test creating multiple data frames from JSON in the same thread."""
    from agent_platform.orchestrator.agent_server_client import AgentServerClient

    with AgentServerClient(base_url_agent_server_session) as agent_client:
        agent_id = agent_client.create_agent_and_return_agent_id(
            action_packages=[],
            platform_configs=[
                {
                    "kind": "openai",
                    "openai_api_key": "unused",
                    "models": {"openai": ["gpt-5-low"]},
                },
            ],
        )
        thread_id = agent_client.create_thread_and_return_thread_id(agent_id)

        # Create first data frame
        json_data_1 = {
            "customers": [
                {"name": "Alice", "age": 30, "city": "NYC"},
                {"name": "Bob", "age": 25, "city": "LA"},
            ]
        }

        result_1 = agent_client.create_data_frame_from_json(
            thread_id=thread_id,
            json_data=json_data_1,
            jq_expression=".customers[]",
            name="customers",
        )

        # Create second data frame
        json_data_2 = {
            "products": [
                {"id": "P1", "name": "Widget", "price": 19.99},
                {"id": "P2", "name": "Gadget", "price": 29.99},
                {"id": "P3", "name": "Tool", "price": 39.99},
            ]
        }

        result_2 = agent_client.create_data_frame_from_json(
            thread_id=thread_id,
            json_data=json_data_2,
            jq_expression=".products[]",
            name="products",
        )

        # Verify both data frames exist
        data_frames = agent_client.get_data_frames(thread_id)
        assert len(data_frames) == 2
        assert result_1["data_frame_id"] is not None
        assert result_2["data_frame_id"] is not None

        # Prepare results for regression check
        data_frames_for_check = [_prepare_result_for_regression(df) for df in data_frames]
        # Sort by name for deterministic ordering
        data_frames_for_check = sorted(data_frames_for_check, key=lambda x: x["name"])

        data_regression.check(
            {
                "result_1": _prepare_result_for_regression(result_1),
                "result_2": _prepare_result_for_regression(result_2),
                "data_frames": data_frames_for_check,
            }
        )


@pytest.mark.integration
def test_create_data_frame_from_json_auto_name_generation(base_url_agent_server_session, data_regression):
    """Test automatic name generation when no name is provided."""
    from agent_platform.orchestrator.agent_server_client import AgentServerClient

    with AgentServerClient(base_url_agent_server_session) as agent_client:
        agent_id = agent_client.create_agent_and_return_agent_id(
            action_packages=[],
            platform_configs=[
                {
                    "kind": "openai",
                    "openai_api_key": "unused",
                    "models": {"openai": ["gpt-5-low"]},
                },
            ],
        )
        thread_id = agent_client.create_thread_and_return_thread_id(agent_id)

        json_data = {
            "data": [
                {"x": 1, "y": 2},
                {"x": 3, "y": 4},
            ]
        }

        result = agent_client.create_data_frame_from_json(
            thread_id=thread_id,
            json_data=json_data,
            jq_expression=".data[]",
            # No name provided
        )

        # Should have auto-generated a name
        assert result["name"].startswith("data_frame_")
        assert result["data_frame_id"] is not None

        # Exclude name field since it's auto-generated and will vary
        data_regression.check(_prepare_result_for_regression(result, exclude_fields=["name"]))


@pytest.mark.integration
def test_create_data_frame_from_json_with_sql_computation(base_url_agent_server_session, data_regression):
    """Test creating a data frame from JSON and then using it in SQL computation."""
    from agent_platform.orchestrator.agent_server_client import AgentServerClient

    with AgentServerClient(base_url_agent_server_session) as agent_client:
        agent_id = agent_client.create_agent_and_return_agent_id(
            action_packages=[],
            platform_configs=[
                {
                    "kind": "openai",
                    "openai_api_key": "unused",
                    "models": {"openai": ["gpt-5-low"]},
                },
            ],
        )
        thread_id = agent_client.create_thread_and_return_thread_id(agent_id)

        # Create a data frame from JSON
        json_data = {
            "sales": [
                {"product": "Widget", "quantity": 10, "price": 5.0},
                {"product": "Gadget", "quantity": 5, "price": 15.0},
                {"product": "Tool", "quantity": 3, "price": 25.0},
            ]
        }

        agent_client.create_data_frame_from_json(
            thread_id=thread_id,
            json_data=json_data,
            jq_expression=".sales[]",
            name="sales_data",
        )

        # Now create a computed data frame using SQL
        computed_result = agent_client.create_data_frame_from_sql_computation(
            thread_id=thread_id,
            name="high_value_sales",
            sql_query="""
                SELECT
                    product,
                    quantity * price as total_value
                FROM sales_data
                WHERE quantity * price > 50
                ORDER BY total_value DESC
            """,
        )

        # Verify data_frame_id exists, then prepare for regression check
        assert computed_result["data_frame_id"] is not None
        data_regression.check(_prepare_result_for_regression(computed_result))
