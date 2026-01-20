"""Test that PlatformDataFrame.columns is properly populated with type information."""

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.postgresql


@pytest.mark.asyncio
async def test_data_frame_columns_populated_from_sql(postgres_storage, postgres_model_creator, postgres_testing):
    """Test that PlatformDataFrame.columns is populated with actual types after SQL query."""
    from uuid import uuid4

    from agent_platform.core.data_connections.data_connections import DataConnection
    from agent_platform.core.payloads.data_connection import PostgresDataConnectionConfiguration
    from agent_platform.core.user import User
    from agent_platform.server.data_frames.data_frames_from_computation import (
        create_data_frame_from_sql_computation_api,
    )
    from agent_platform.server.data_frames.data_frames_kernel import DataFramesKernel

    # Step 1: Create a simple Postgres table with known schema directly in the test DB
    async with postgres_storage._write_connection() as conn:
        await conn.execute(
            text("""
            CREATE TABLE test_simple_table (
                id INTEGER,
                name VARCHAR(100),
                price NUMERIC(10,2),
                active BOOLEAN
            )
        """)
        )
        await conn.execute(
            text("""
            INSERT INTO test_simple_table VALUES
            (1, 'Item A', 19.99, true),
            (2, 'Item B', 29.99, false)
        """)
        )
        await conn.commit()

    # Step 2: Create sample models
    await postgres_model_creator.setup()
    thread = await postgres_model_creator.obtain_sample_thread()
    agent = await postgres_model_creator.obtain_sample_agent()

    # Step 3: Create a data connection pointing to the Postgres test database
    # Parse the connection URL to extract components
    from urllib.parse import urlparse

    parsed_url = urlparse(postgres_testing.url())
    data_connection = DataConnection(
        id=str(uuid4()),
        name="test_postgres_connection",
        description="Test Postgres connection",
        engine="postgres",
        configuration=PostgresDataConnectionConfiguration(
            host=parsed_url.hostname or "localhost",
            port=parsed_url.port or 5432,
            database=parsed_url.path.lstrip("/"),
            user=parsed_url.username or "postgres",
            password=parsed_url.password or "postgres",
            schema="public",
        ),
        external_id=None,
        created_at=None,
        updated_at=None,
    )

    await postgres_storage.set_data_connection(data_connection)

    # Step 4: Create a semantic data model that exposes test_simple_table
    semantic_model = {
        "name": "test_semantic_model",
        "description": "Test semantic model for test_simple_table",
        "tables": [
            {
                "name": "test_simple_table",
                "base_table": {
                    "database": parsed_url.path.lstrip("/"),
                    "schema": "public",
                    "table": "test_simple_table",
                    "data_connection_id": data_connection.id,
                },
            }
        ],
    }

    semantic_data_model_id = await postgres_storage.set_semantic_data_model(
        semantic_data_model_id=None,
        semantic_model=semantic_model,
        data_connection_ids=[data_connection.id],
        file_references=[],
    )

    # Step 5: Associate the semantic data model with the agent and thread
    await postgres_storage.set_agent_semantic_data_models(
        agent_id=agent.agent_id,
        semantic_data_model_ids=[semantic_data_model_id],
    )
    await postgres_storage.set_thread_semantic_data_models(
        thread_id=thread.thread_id,
        semantic_data_model_ids=[semantic_data_model_id],
    )

    # Step 6: Create the kernel and run the SQL computation
    authed_user = User(
        user_id=thread.user_id,
        sub="test_sub",
    )

    kernel = DataFramesKernel(postgres_storage, authed_user, thread.thread_id)

    # Create a new data frame with SQL computation
    resolved_df, table = await create_data_frame_from_sql_computation_api(
        data_frames_kernel=kernel,
        storage=postgres_storage,
        new_data_frame_name="test_df",
        sql_query="SELECT * FROM test_simple_table",
        dialect="postgres",
        num_samples=10,
    )

    # Fetch the saved PlatformDataFrame
    saved_df = await postgres_storage.get_data_frame(thread.thread_id, data_frame_name="test_df")

    # Assert columns field is populated
    assert saved_df.columns != {}, "columns should not be empty"
    assert "id" in saved_df.columns, "id column should be in columns dict"
    assert "name" in saved_df.columns, "name column should be in columns dict"
    assert "price" in saved_df.columns, "price column should be in columns dict"
    assert "active" in saved_df.columns, "active column should be in columns dict"

    # Verify extract_actual_shape works correctly
    from agent_platform.server.kernel.sql_gen.verify import extract_actual_shape

    shape = extract_actual_shape(saved_df)
    assert shape.row_count == 2, f"Expected 2 rows, got {shape.row_count}"
    assert len(shape.columns) == 4, f"Expected 4 columns, got {len(shape.columns)}"

    # Verify column names and types are present
    column_names = [col.name for col in shape.columns]
    assert "id" in column_names, "id should be in column names"
    assert "name" in column_names, "name should be in column names"
    assert "price" in column_names, "price should be in column names"
    assert "active" in column_names, "active should be in column names"

    # All columns should have type information (not empty strings)
    for col in shape.columns:
        assert col.type != "", f"Column {col.name} should have non-empty type"
        assert col.type is not None, f"Column {col.name} should have non-null type"

    # Verify the actual types from resolved_df match what's saved
    assert saved_df.columns == resolved_df.columns, "Saved columns should match resolved columns"
