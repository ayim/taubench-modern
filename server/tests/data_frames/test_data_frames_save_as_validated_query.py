# ruff: noqa: PLR0912, PLR0913, PLR0915, C901, E501
import time
import typing
from datetime import datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_platform.core.semantic_data_model.types import ResultType

if typing.TYPE_CHECKING:
    from agent_platform.server.storage.sqlite import SQLiteStorage


def fix_sql_query(sql_query: str) -> str:
    """Normalize SQL query by collapsing whitespace for comparison."""
    return sql_query.replace("\n", " ").strip().replace("  ", " ").replace("  ", " ")


@pytest.fixture
async def test_user(sqlite_storage: "SQLiteStorage"):
    """Create a test user for API calls."""

    user, _ = await sqlite_storage.get_or_create_user(sub="tenant:testing:user:system")
    return user


@pytest.fixture
async def fastapi_app(sqlite_storage: "SQLiteStorage", test_user) -> FastAPI:
    """Create FastAPI test app with router and storage dependency."""
    from agent_platform.server.api.private_v2 import threads_data_frames
    from agent_platform.server.auth.handlers import auth_user
    from agent_platform.server.storage.option import StorageService

    StorageService.reset()
    StorageService.set_for_testing(sqlite_storage)

    app = FastAPI()
    app.include_router(threads_data_frames.router, prefix="/api/v2/threads")

    async def override_auth_user():
        return test_user

    app.dependency_overrides[auth_user] = override_auth_user

    return app


@pytest.fixture
def client(fastapi_app: FastAPI) -> TestClient:
    """Create test client."""
    return TestClient(fastapi_app)


@pytest.mark.asyncio
async def test_save_data_frame_as_validated_query(
    sqlite_storage: "SQLiteStorage",
    tmpdir: Path,
    client: TestClient,
    test_user,
    fastapi_app,
):
    """Test saving a data frame as a validated query in a semantic data model."""

    from agent_platform.architectures.experimental.exp_1 import Exp1State
    from server.tests.storage.sample_model_creator import SampleModelCreator

    # Setup model creator
    model_creator = SampleModelCreator(sqlite_storage, tmpdir)
    await model_creator.setup()

    # Create thread
    thread = await model_creator.obtain_sample_thread()

    # Create a CSV file
    csv_content = b"Category,Value\nA,100\nB,200\nC,300"
    csv_file = await model_creator.obtain_sample_file(
        file_content=csv_content,
        file_name="test_data.csv",
        mime_type="text/csv",
    )

    # Create a semantic data model with file reference
    semantic_model = {
        "name": "test_semantic_model",
        "description": "Test semantic model with file reference",
        "tables": [
            {
                "name": "file_data",
                "base_table": {
                    "table": "data_frame_file",
                    "file_reference": {
                        "thread_id": thread.thread_id,
                        "file_ref": csv_file.file_ref,
                        "sheet_name": None,
                    },
                },
                "dimensions": [
                    {"name": "category", "expr": "Category", "data_type": "TEXT"},
                ],
                "facts": [
                    {"name": "value", "expr": "Value", "data_type": "INTEGER"},
                ],
            }
        ],
    }

    semantic_data_model_id = await sqlite_storage.set_semantic_data_model(
        semantic_data_model_id=None,
        semantic_model=semantic_model,
        data_connection_ids=[],
        file_references=[(thread.thread_id, csv_file.file_ref)],
    )

    # Associate model to thread
    await sqlite_storage.set_thread_semantic_data_models(
        thread_id=thread.thread_id, semantic_data_model_ids=[semantic_data_model_id]
    )

    # Create a data frame from the semantic data model using SQL
    from tests.data_frames.fixtures import KernelStub, UserStub

    from agent_platform.core.kernel import Kernel
    from agent_platform.server.kernel.data_frames import AgentServerDataFramesInterface

    state = Exp1State()
    user_stub = UserStub(user_id=await model_creator.get_user_id())
    kernel_stub = KernelStub(thread, user_stub)

    # Initialize interface and create data frame via SQL
    interface = AgentServerDataFramesInterface()
    interface.attach_kernel(typing.cast(Kernel, kernel_stub))

    await interface.step_initialize(storage=sqlite_storage, state=state)

    # Create a data frame via SQL referencing the semantic model logical table
    tools = interface.get_data_frame_tools()
    create_sql_tool = next(tool for tool in tools if tool.name == "data_frames_create_from_sql")

    data_frame_name = "test_validated_query_df"
    data_frame_description = "Test data frame description for validated query"

    result = await create_sql_tool.function(
        sql_query="SELECT * FROM file_data",
        new_data_frame_name=data_frame_name,
        new_data_frame_description=data_frame_description,
    )
    assert "result" in result

    # Verify the semantic data model doesn't have verified_queries yet
    retrieved_model_before = await sqlite_storage.get_semantic_data_model(semantic_data_model_id)
    assert "verified_queries" not in retrieved_model_before or retrieved_model_before.get("verified_queries") is None

    # Step 1: Get the data frame as a validated query
    get_response = client.post(
        f"/api/v2/threads/{thread.thread_id}/data-frames/as-validated-query",
        json={"data_frame_name": data_frame_name},
    )

    assert get_response.status_code == 200
    response_data = get_response.json()

    # Verify the response contains both the verified query and semantic data model name
    assert "verified_query" in response_data
    assert "semantic_data_model_name" in response_data

    # Get the semantic data model to verify the name
    semantic_data_model = await sqlite_storage.get_semantic_data_model(semantic_data_model_id)
    expected_sdm_name = semantic_data_model["name"]

    # Verify the semantic data model name matches the one we created
    assert response_data["semantic_data_model_name"] == expected_sdm_name

    validated_query = response_data["verified_query"]

    # The verified query name is converted to human-readable format (spaces + title case)
    from agent_platform.core.data_frames.data_frame_utils import (
        data_frame_name_to_verified_query_name,
    )

    expected_verified_query_name = data_frame_name_to_verified_query_name(data_frame_name)
    assert validated_query["name"] == expected_verified_query_name
    assert validated_query["nlq"] == data_frame_description
    assert validated_query["verified_by"] == test_user.user_id
    assert "verified_at" in validated_query

    assert fix_sql_query(validated_query["sql"]) == "SELECT * FROM file_data"

    # Step 2: Save the validated query
    response = client.post(
        f"/api/v2/threads/{thread.thread_id}/data-frames/save-as-validated-query",
        json={
            "verified_query": validated_query,
            "semantic_data_model_id": semantic_data_model_id,
        },
    )

    assert response.status_code == 200
    response_data = response.json()
    assert "message" in response_data
    assert "Successfully saved" in response_data["message"]
    assert validated_query["name"] in response_data["message"]

    # Verify the semantic data model was updated with the verified query
    retrieved_model_after = await sqlite_storage.get_semantic_data_model(semantic_data_model_id)
    assert "verified_queries" in retrieved_model_after
    assert retrieved_model_after["verified_queries"] is not None
    assert len(retrieved_model_after["verified_queries"]) == 1

    verified_query = retrieved_model_after["verified_queries"][0]
    assert verified_query.name == expected_verified_query_name
    assert verified_query.nlq == data_frame_description
    assert verified_query.verified_by == test_user.user_id

    assert fix_sql_query(verified_query.sql) == "SELECT * FROM file_data"
    assert verified_query.verified_at is not None
    # Verify verified_at is a valid ISO format string
    datetime.fromisoformat(verified_query.verified_at)
    # Verify result_type is set correctly for SELECT query
    assert verified_query.result_type == ResultType.TABLE, "SELECT query should have result_type='table'"

    # Test updating an existing verified query by calling the endpoint again
    # This should update the verified_at timestamp
    time.sleep(0.02)  # Small delay to ensure different timestamp

    # Step 1: Get the validated query again
    get_response_updated = client.post(
        f"/api/v2/threads/{thread.thread_id}/data-frames/as-validated-query",
        json={"data_frame_name": data_frame_name},
    )
    assert get_response_updated.status_code == 200
    updated_response_data = get_response_updated.json()

    # Verify auto-detection still works on subsequent calls
    assert updated_response_data["semantic_data_model_name"] == expected_sdm_name

    updated_validated_query = updated_response_data["verified_query"]

    # Step 2: Save the updated validated query
    response = client.post(
        f"/api/v2/threads/{thread.thread_id}/data-frames/save-as-validated-query",
        json={
            "verified_query": updated_validated_query,
            "semantic_data_model_id": semantic_data_model_id,
        },
    )

    assert response.status_code == 200

    # Verify the semantic data model still has only one verified query (updated)
    retrieved_model_updated = await sqlite_storage.get_semantic_data_model(semantic_data_model_id)
    assert len(retrieved_model_updated["verified_queries"]) == 1

    updated_query = retrieved_model_updated["verified_queries"][0]
    assert updated_query.name == expected_verified_query_name
    assert updated_query.nlq == data_frame_description
    assert fix_sql_query(updated_query.sql) == "SELECT * FROM file_data"
    # Verify verified_at was updated (should be different timestamp)
    assert updated_query.verified_at != verified_query.verified_at
    # Verify result_type is still set correctly after update
    assert updated_query.result_type == ResultType.TABLE, "Updated SELECT query should have result_type='table'"


@pytest.mark.asyncio
async def test_get_validated_query_with_multiple_sdms(
    sqlite_storage: "SQLiteStorage",
    tmpdir: Path,
    client: TestClient,
):
    """Test that validated query correctly identifies SDM name when multiple SDMs exist."""

    from agent_platform.architectures.experimental.exp_1 import Exp1State
    from server.tests.storage.sample_model_creator import SampleModelCreator

    # Setup model creator
    model_creator = SampleModelCreator(sqlite_storage, tmpdir)
    await model_creator.setup()

    # Create thread
    thread = await model_creator.obtain_sample_thread()

    # Create two CSV files
    csv_content_1 = b"Category,Value\nA,100\nB,200"
    csv_file_1 = await model_creator.obtain_sample_file(
        file_content=csv_content_1,
        file_name="test_data_1.csv",
        mime_type="text/csv",
    )

    csv_content_2 = b"Product,Price\nX,50\nY,75"
    csv_file_2 = await model_creator.obtain_sample_file(
        file_content=csv_content_2,
        file_name="test_data_2.csv",
        mime_type="text/csv",
    )

    # Create first semantic data model
    semantic_model_1 = {
        "name": "sales_semantic_model",
        "description": "Sales semantic model",
        "tables": [
            {
                "name": "sales_data",
                "base_table": {
                    "table": "data_frame_file",
                    "file_reference": {
                        "thread_id": thread.thread_id,
                        "file_ref": csv_file_1.file_ref,
                        "sheet_name": None,
                    },
                },
                "dimensions": [
                    {"name": "category", "expr": "Category", "data_type": "TEXT"},
                ],
                "facts": [
                    {"name": "value", "expr": "Value", "data_type": "INTEGER"},
                ],
            }
        ],
    }

    semantic_data_model_id_1 = await sqlite_storage.set_semantic_data_model(
        semantic_data_model_id=None,
        semantic_model=semantic_model_1,
        data_connection_ids=[],
        file_references=[(thread.thread_id, csv_file_1.file_ref)],
    )

    # Create second semantic data model
    semantic_model_2 = {
        "name": "products_semantic_model",
        "description": "Products semantic model",
        "tables": [
            {
                "name": "products_data",
                "base_table": {
                    "table": "data_frame_file",
                    "file_reference": {
                        "thread_id": thread.thread_id,
                        "file_ref": csv_file_2.file_ref,
                        "sheet_name": None,
                    },
                },
                "dimensions": [
                    {"name": "product", "expr": "Product", "data_type": "TEXT"},
                ],
                "facts": [
                    {"name": "price", "expr": "Price", "data_type": "INTEGER"},
                ],
            }
        ],
    }

    semantic_data_model_id_2 = await sqlite_storage.set_semantic_data_model(
        semantic_data_model_id=None,
        semantic_model=semantic_model_2,
        data_connection_ids=[],
        file_references=[(thread.thread_id, csv_file_2.file_ref)],
    )

    # Associate both models to thread
    await sqlite_storage.set_thread_semantic_data_models(
        thread_id=thread.thread_id,
        semantic_data_model_ids=[semantic_data_model_id_1, semantic_data_model_id_2],
    )

    # Create data frames from each semantic data model using SQL
    from tests.data_frames.fixtures import KernelStub, UserStub

    from agent_platform.core.kernel import Kernel
    from agent_platform.server.kernel.data_frames import AgentServerDataFramesInterface

    state = Exp1State()
    user_stub = UserStub(user_id=await model_creator.get_user_id())
    kernel_stub = KernelStub(thread, user_stub)

    # Initialize interface and create data frames via SQL
    interface = AgentServerDataFramesInterface()
    interface.attach_kernel(typing.cast(Kernel, kernel_stub))

    await interface.step_initialize(storage=sqlite_storage, state=state)

    # Create data frames via SQL referencing each semantic model logical table
    tools = interface.get_data_frame_tools()
    create_sql_tool = next(tool for tool in tools if tool.name == "data_frames_create_from_sql")

    # Create first data frame from first SDM
    data_frame_name_1 = "test_sales_df"
    result_1 = await create_sql_tool.function(
        sql_query="SELECT * FROM sales_data",
        new_data_frame_name=data_frame_name_1,
        new_data_frame_description="Sales data frame",
        semantic_data_model_name="sales_semantic_model",
    )
    assert "result" in result_1

    # Create second data frame from second SDM
    data_frame_name_2 = "test_products_df"
    result_2 = await create_sql_tool.function(
        sql_query="SELECT * FROM products_data",
        new_data_frame_name=data_frame_name_2,
        new_data_frame_description="Products data frame",
        semantic_data_model_name="products_semantic_model",
    )
    assert "result" in result_2

    # Get validated query for first data frame
    get_response_1 = client.post(
        f"/api/v2/threads/{thread.thread_id}/data-frames/as-validated-query",
        json={"data_frame_name": data_frame_name_1},
    )

    assert get_response_1.status_code == 200
    response_data_1 = get_response_1.json()

    # Verify the response contains the correct SDM name for first data frame
    assert "semantic_data_model_name" in response_data_1
    assert response_data_1["semantic_data_model_name"] == "sales_semantic_model"

    # Get validated query for second data frame
    get_response_2 = client.post(
        f"/api/v2/threads/{thread.thread_id}/data-frames/as-validated-query",
        json={"data_frame_name": data_frame_name_2},
    )

    assert get_response_2.status_code == 200
    response_data_2 = get_response_2.json()

    # Verify the response contains the correct SDM name for second data frame
    assert "semantic_data_model_name" in response_data_2
    assert response_data_2["semantic_data_model_name"] == "products_semantic_model"

    # Verify both responses have verified queries
    assert "verified_query" in response_data_1
    assert "verified_query" in response_data_2

    # Verify the SQL queries are correct
    assert fix_sql_query(response_data_1["verified_query"]["sql"]) == "SELECT * FROM sales_data"
    assert fix_sql_query(response_data_2["verified_query"]["sql"]) == "SELECT * FROM products_data"


@pytest.mark.asyncio
async def test_validated_query_with_parameterization(
    sqlite_storage: "SQLiteStorage",
    tmpdir: Path,
    client: TestClient,
    test_user,
):
    """Test that validated query returns parameterized SQL with extracted parameters."""

    from agent_platform.architectures.experimental.exp_1 import Exp1State
    from server.tests.storage.sample_model_creator import SampleModelCreator

    # Setup model creator
    model_creator = SampleModelCreator(sqlite_storage, tmpdir)
    await model_creator.setup()

    # Create thread
    thread = await model_creator.obtain_sample_thread()

    # Create a CSV file
    csv_content = b"Country,Sales,Year\nUSA,1000,2021\nCanada,500,2021\nFrance,750,2022"
    csv_file = await model_creator.obtain_sample_file(
        file_content=csv_content,
        file_name="sales_data.csv",
        mime_type="text/csv",
    )

    # Create a semantic data model
    semantic_model = {
        "name": "sales_model",
        "description": "Sales semantic model",
        "tables": [
            {
                "name": "sales",
                "base_table": {
                    "table": "data_frame_file",
                    "file_reference": {
                        "thread_id": thread.thread_id,
                        "file_ref": csv_file.file_ref,
                        "sheet_name": None,
                    },
                },
                "dimensions": [
                    {"name": "country", "expr": "Country", "data_type": "TEXT"},
                    {"name": "year", "expr": "Year", "data_type": "INTEGER"},
                ],
                "facts": [
                    {"name": "sales", "expr": "Sales", "data_type": "INTEGER"},
                ],
            }
        ],
    }

    semantic_data_model_id = await sqlite_storage.set_semantic_data_model(
        semantic_data_model_id=None,
        semantic_model=semantic_model,
        data_connection_ids=[],
        file_references=[(thread.thread_id, csv_file.file_ref)],
    )

    # Associate model to thread
    await sqlite_storage.set_thread_semantic_data_models(
        thread_id=thread.thread_id, semantic_data_model_ids=[semantic_data_model_id]
    )

    # Create a data frame with a SQL query containing literals
    from tests.data_frames.fixtures import KernelStub, UserStub

    from agent_platform.core.kernel import Kernel
    from agent_platform.server.kernel.data_frames import AgentServerDataFramesInterface

    state = Exp1State()
    user_stub = UserStub(user_id=await model_creator.get_user_id())
    kernel_stub = KernelStub(thread, user_stub)

    # Initialize interface and create data frame via SQL with literals
    interface = AgentServerDataFramesInterface()
    interface.attach_kernel(typing.cast(Kernel, kernel_stub))

    await interface.step_initialize(storage=sqlite_storage, state=state)

    # Create a data frame with a SQL query that has literals
    # This query should have parameters extracted: 'USA' and 2021
    tools = interface.get_data_frame_tools()
    create_sql_tool = next(tool for tool in tools if tool.name == "data_frames_create_from_sql")

    data_frame_name = "usa_sales_2021"
    data_frame_description = "USA sales for 2021"

    result = await create_sql_tool.function(
        sql_query="SELECT * FROM sales WHERE country = 'USA' AND year = 2021",
        new_data_frame_name=data_frame_name,
        new_data_frame_description=data_frame_description,
    )
    assert "result" in result

    # Get the data frame as a validated query
    get_response = client.post(
        f"/api/v2/threads/{thread.thread_id}/data-frames/as-validated-query",
        json={"data_frame_name": data_frame_name},
    )

    assert get_response.status_code == 200
    response_data = get_response.json()

    # Verify the response contains the verified query
    assert "verified_query" in response_data
    validated_query = response_data["verified_query"]

    # Verify the SQL was parameterized
    assert "sql" in validated_query
    parameterized_sql = validated_query["sql"]

    # Verify full parameterized SQL matches expected output
    assert fix_sql_query(parameterized_sql) == "SELECT * FROM sales WHERE country = :country AND year = :year"

    # Verify parameters were extracted
    assert "parameters" in validated_query
    parameters = validated_query["parameters"]
    assert parameters is not None
    assert len(parameters) == 2

    # Check for country parameter
    country_param = next((p for p in parameters if p["name"] == "country"), None)
    assert country_param is not None
    assert country_param["data_type"] == "string"
    assert country_param["example_value"] == "USA"
    assert "description" in country_param

    # Check for year parameter
    year_param = next((p for p in parameters if p["name"] == "year"), None)
    assert year_param is not None
    assert year_param["data_type"] == "integer"
    assert year_param["example_value"] == 2021
    assert "description" in year_param


@pytest.mark.asyncio
async def test_validated_query_insert_has_rows_affected_result_type(
    sqlite_storage: "SQLiteStorage",
    tmpdir: Path,
    client: TestClient,
    test_user,
):
    """Test that INSERT query gets result_type='rows_affected' when saved."""

    from server.tests.storage.sample_model_creator import SampleModelCreator

    # Setup model creator
    model_creator = SampleModelCreator(sqlite_storage, tmpdir)
    await model_creator.setup()

    # Create thread
    thread = await model_creator.obtain_sample_thread()

    # Create a CSV file
    csv_content = b"id,name,value\n1,Alice,100\n2,Bob,200"
    csv_file = await model_creator.obtain_sample_file(
        file_content=csv_content,
        file_name="test_data.csv",
        mime_type="text/csv",
    )

    # Create a semantic data model with file reference
    semantic_model = {
        "name": "test_insert_model",
        "description": "Test semantic model for INSERT query",
        "tables": [
            {
                "name": "test_table",
                "base_table": {
                    "table": "data_frame_file",
                    "file_reference": {
                        "thread_id": thread.thread_id,
                        "file_ref": csv_file.file_ref,
                        "sheet_name": None,
                    },
                },
                "dimensions": [
                    {"name": "id", "expr": "id", "data_type": "INTEGER"},
                    {"name": "name", "expr": "name", "data_type": "TEXT"},
                ],
                "facts": [
                    {"name": "value", "expr": "value", "data_type": "INTEGER"},
                ],
            }
        ],
    }

    semantic_data_model_id = await sqlite_storage.set_semantic_data_model(
        semantic_data_model_id=None,
        semantic_model=semantic_model,
        data_connection_ids=[],
        file_references=[(thread.thread_id, csv_file.file_ref)],
    )

    # Associate model to thread
    await sqlite_storage.set_thread_semantic_data_models(
        thread_id=thread.thread_id, semantic_data_model_ids=[semantic_data_model_id]
    )

    # Create a verified query with INSERT statement (no RETURNING clause)
    insert_verified_query = {
        "name": "insert new record",
        "nlq": "Insert a new record into test_table",
        "sql": "INSERT INTO test_table (id, name, value) VALUES (:id, :name, :value)",
        "verified_at": "2024-01-01T00:00:00Z",
        "verified_by": test_user.user_id,
        "parameters": [
            {"name": "id", "data_type": "integer", "example_value": 3, "description": "Record ID"},
            {"name": "name", "data_type": "string", "example_value": "Charlie", "description": "Name"},
            {"name": "value", "data_type": "integer", "example_value": 300, "description": "Value"},
        ],
    }

    # Save the INSERT verified query
    response = client.post(
        f"/api/v2/threads/{thread.thread_id}/data-frames/save-as-validated-query",
        json={
            "verified_query": insert_verified_query,
            "semantic_data_model_id": semantic_data_model_id,
        },
    )

    assert response.status_code == 200

    # Retrieve the saved verified query and check result_type
    retrieved_model = await sqlite_storage.get_semantic_data_model(semantic_data_model_id)
    assert "verified_queries" in retrieved_model
    assert len(retrieved_model["verified_queries"]) == 1

    saved_query = retrieved_model["verified_queries"][0]
    assert saved_query.name == "insert new record"
    # INSERT without RETURNING should have result_type='rows_affected'
    assert saved_query.result_type == "rows_affected", (
        "INSERT query without RETURNING should have result_type='rows_affected'"
    )
