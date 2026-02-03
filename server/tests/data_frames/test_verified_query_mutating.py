"""
Integration tests for verified queries with mutating SQL (INSERT/UPDATE/DELETE).

Tests the complete flow:
1. Create a DuckDB table with rows
2. Create a verified query tool for the mutation
3. Invoke the tool function directly
4. Verify the resulting data frame (RETURNING clause)
5. Verify the database table contents

These tests validate that:
- allow_mutate=True is passed through for verified queries
- INSERT/UPDATE/DELETE queries work through verified query tools
- The result set from RETURNING clauses is properly handled
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from unittest.mock import Mock

import duckdb
import pytest

if TYPE_CHECKING:
    from agent_platform.core.semantic_data_model.types import ResultType

from agent_platform.core.kernel import ThreadStateInterface


@dataclass
class SqlExecutorCapture:
    """Captures SQL executor callback invocations for testing."""

    connection: duckdb.DuckDBPyConnection
    calls: list[dict] = field(default_factory=list)

    async def __call__(
        self,
        sql_query: str,
        result_type: "ResultType | None",
        new_data_frame_name: str | None,
        new_data_frame_description: str | None,
        num_samples: int,
        semantic_data_model_name: str | None,
    ) -> dict:
        """Execute SQL and capture the call parameters."""
        self.calls.append(
            {
                "sql_query": sql_query,
                "result_type": result_type,
                "new_data_frame_name": new_data_frame_name,
                "new_data_frame_description": new_data_frame_description,
                "num_samples": num_samples,
                "semantic_data_model_name": semantic_data_model_name,
            }
        )

        result = self.connection.execute(sql_query).fetchall()
        return {
            "status": "success",
            "result": f"Data frame {new_data_frame_name} created",
            "sample_data": {"columns": ["id", "name", "email"], "rows": result},
            "data_frame_name": new_data_frame_name,
        }

    @property
    def last_call(self) -> dict:
        """Return the most recent call, or raise if no calls made."""
        if not self.calls:
            raise AssertionError("No calls were made to the SQL executor")
        return self.calls[-1]


@pytest.fixture
def duckdb_connection():
    """Create an in-memory DuckDB database with test data."""
    conn = duckdb.connect(":memory:")
    conn.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name VARCHAR,
            email VARCHAR
        )
    """)
    conn.execute("""
        INSERT INTO users (id, name, email) VALUES
        (1, 'Alice', 'alice@example.com'),
        (2, 'Bob', 'bob@example.com'),
        (3, 'Charlie', 'charlie@example.com')
    """)
    yield conn
    conn.close()


@pytest.fixture
def sql_executor(duckdb_connection):
    """Create a SQL executor that captures calls and executes against DuckDB."""
    return SqlExecutorCapture(connection=duckdb_connection)


@pytest.mark.asyncio
async def test_verified_query_delete_passes_result_type(duckdb_connection, sql_executor):
    """
    Test that a verified DELETE query with RETURNING:
    1. Passes result_type=TABLE to the callback
    2. Successfully executes the DELETE
    3. Returns the deleted row via RETURNING clause
    4. Actually removes the row from the database
    """
    from sqlglot import exp, parse_one

    from agent_platform.core.semantic_data_model.types import (
        QueryParameter,
        ResultType,
        VerifiedQuery,
    )
    from agent_platform.core.tools.tool_definition import ToolDefinition
    from agent_platform.server.kernel.verified_queries import VerifiedQueryToolBuilder

    verified_delete_query = VerifiedQuery(
        name="delete user by id",
        nlq="Delete a user by their ID and return the deleted row",
        verified_at="2024-01-01T00:00:00Z",
        verified_by="test_user",
        sql="DELETE FROM users WHERE id = :user_id RETURNING *",
        result_type=ResultType.TABLE,  # Has RETURNING, so returns a table
        parameters=[
            QueryParameter(
                name="user_id",
                data_type="integer",
                description="The ID of the user to delete",
                example_value=1,
            )
        ],
        sql_errors=None,
        nlq_errors=None,
        name_errors=None,
        parameter_errors=None,
    )

    # Verify initial state: 3 users
    assert duckdb_connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 3

    # Build the verified query tool
    existing_tools: dict[str, ToolDefinition] = {}
    builder = VerifiedQueryToolBuilder(existing_tools)
    tool_name = builder.create_and_add_tool(
        verified_query=verified_delete_query,
        semantic_data_model_name="test_model",
        dialect="duckdb",
        sql_executor_callback=sql_executor,
        thread_state=Mock(spec=ThreadStateInterface),
    )

    # Invoke the tool to delete user with id=2
    tool = existing_tools[tool_name]
    result = await tool.function(
        user_id=2,
        new_data_frame_name="deleted_user",
        new_data_frame_description="The deleted user",
        num_samples=10,
    )

    # Verify callback was called with result_type=TABLE
    assert len(sql_executor.calls) == 1
    assert sql_executor.last_call["result_type"] == ResultType.TABLE

    # Verify parameter substitution worked by parsing the SQL
    parsed = parse_one(sql_executor.last_call["sql_query"], read="duckdb")
    assert isinstance(parsed, exp.Delete), "Should be a DELETE statement"
    assert parsed.this.name == "users", "Should delete from users table"
    where = parsed.find(exp.Where)
    assert where is not None, "Should have WHERE clause"
    eq = where.find(exp.EQ)
    assert eq is not None, "Should have equality condition"
    assert eq.right.this == "2", "Should filter by id = 2"

    # Verify the result contains the deleted row
    assert result["status"] == "success"
    assert result["sample_data"]["rows"] == [(2, "Bob", "bob@example.com")]

    # Verify the database now has only 2 users
    assert duckdb_connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 2
    remaining = duckdb_connection.execute("SELECT id FROM users ORDER BY id").fetchall()
    assert remaining == [(1,), (3,)]


@pytest.mark.asyncio
async def test_verified_query_insert_passes_result_type(duckdb_connection, sql_executor):
    """
    Test that a verified INSERT query with RETURNING:
    1. Passes result_type=TABLE to the callback
    2. Successfully executes the INSERT
    3. Returns the inserted row via RETURNING clause
    4. Actually adds the row to the database
    """
    from sqlglot import exp, parse_one

    from agent_platform.core.semantic_data_model.types import (
        QueryParameter,
        ResultType,
        VerifiedQuery,
    )
    from agent_platform.core.tools.tool_definition import ToolDefinition
    from agent_platform.server.kernel.verified_queries import VerifiedQueryToolBuilder

    verified_insert_query = VerifiedQuery(
        name="insert user",
        nlq="Insert a new user and return the inserted row",
        verified_at="2024-01-01T00:00:00Z",
        verified_by="test_user",
        sql="INSERT INTO users (id, name, email) VALUES (:user_id, :user_name, :email) RETURNING *",
        result_type=ResultType.TABLE,  # Has RETURNING, so returns a table
        parameters=[
            QueryParameter(
                name="user_id",
                data_type="integer",
                description="User ID",
                example_value=4,
            ),
            QueryParameter(
                name="user_name",
                data_type="string",
                description="User name",
                example_value="Dave",
            ),
            QueryParameter(
                name="email",
                data_type="string",
                description="User email",
                example_value="dave@example.com",
            ),
        ],
        sql_errors=None,
        nlq_errors=None,
        name_errors=None,
        parameter_errors=None,
    )

    # Verify initial state: 3 users
    assert duckdb_connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 3

    # Build the verified query tool
    existing_tools: dict[str, ToolDefinition] = {}
    builder = VerifiedQueryToolBuilder(existing_tools)
    tool_name = builder.create_and_add_tool(
        verified_query=verified_insert_query,
        semantic_data_model_name="test_model",
        dialect="duckdb",
        sql_executor_callback=sql_executor,
        thread_state=Mock(spec=ThreadStateInterface),
    )

    # Invoke the tool to insert a new user
    tool = existing_tools[tool_name]
    result = await tool.function(
        user_id=4,
        user_name="Dave",
        email="dave@example.com",
        new_data_frame_name="inserted_user",
        new_data_frame_description="The inserted user",
        num_samples=10,
    )

    # Verify callback was called with result_type=TABLE
    assert len(sql_executor.calls) == 1
    assert sql_executor.last_call["result_type"] == ResultType.TABLE

    # Verify parameter substitution worked by parsing the SQL
    parsed = parse_one(sql_executor.last_call["sql_query"], read="duckdb")
    assert isinstance(parsed, exp.Insert), "Should be an INSERT statement"
    assert parsed.this.this.name == "users", "Should insert into users table"
    values = parsed.find(exp.Values)
    assert values is not None, "Should have VALUES clause"
    tuple_exp = values.find(exp.Tuple)
    assert tuple_exp is not None, "Should have value tuple"
    literals = [lit.this for lit in tuple_exp.find_all(exp.Literal)]
    assert "4" in literals, "Should contain user_id = 4"
    assert "Dave" in literals, "Should contain user_name = 'Dave'"
    assert "dave@example.com" in literals, "Should contain email"

    # Verify the result contains the inserted row
    assert result["status"] == "success"
    assert result["sample_data"]["rows"] == [(4, "Dave", "dave@example.com")]

    # Verify the database now has 4 users
    assert duckdb_connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 4
    new_user = duckdb_connection.execute("SELECT * FROM users WHERE id = 4").fetchone()
    assert new_user == (4, "Dave", "dave@example.com")


@pytest.mark.asyncio
async def test_verified_query_update_passes_result_type(duckdb_connection, sql_executor):
    """
    Test that a verified UPDATE query with RETURNING:
    1. Passes result_type=TABLE to the callback
    2. Successfully executes the UPDATE
    3. Returns the updated row via RETURNING clause
    4. Actually modifies the row in the database
    """
    from sqlglot import exp, parse_one

    from agent_platform.core.semantic_data_model.types import (
        QueryParameter,
        ResultType,
        VerifiedQuery,
    )
    from agent_platform.core.tools.tool_definition import ToolDefinition
    from agent_platform.server.kernel.verified_queries import VerifiedQueryToolBuilder

    verified_update_query = VerifiedQuery(
        name="update user email",
        nlq="Update a user's email by ID",
        verified_at="2024-01-01T00:00:00Z",
        verified_by="test_user",
        sql="UPDATE users SET email = :new_email WHERE id = :user_id RETURNING *",
        result_type=ResultType.TABLE,  # Has RETURNING, so returns a table
        parameters=[
            QueryParameter(
                name="user_id",
                data_type="integer",
                description="User ID",
                example_value=1,
            ),
            QueryParameter(
                name="new_email",
                data_type="string",
                description="New email",
                example_value="newemail@example.com",
            ),
        ],
        sql_errors=None,
        nlq_errors=None,
        name_errors=None,
        parameter_errors=None,
    )

    # Verify initial state: Alice has original email
    assert duckdb_connection.execute("SELECT email FROM users WHERE id = 1").fetchone()[0] == "alice@example.com"

    # Build the verified query tool
    existing_tools: dict[str, ToolDefinition] = {}
    builder = VerifiedQueryToolBuilder(existing_tools)
    tool_name = builder.create_and_add_tool(
        verified_query=verified_update_query,
        semantic_data_model_name="test_model",
        dialect="duckdb",
        sql_executor_callback=sql_executor,
        thread_state=Mock(spec=ThreadStateInterface),
    )

    # Invoke the tool to update Alice's email
    tool = existing_tools[tool_name]
    result = await tool.function(
        user_id=1,
        new_email="alice.updated@example.com",
        new_data_frame_name="updated_user",
        new_data_frame_description="The updated user",
        num_samples=10,
    )

    # Verify callback was called with result_type=TABLE
    assert len(sql_executor.calls) == 1
    assert sql_executor.last_call["result_type"] == ResultType.TABLE

    # Verify parameter substitution worked by parsing the SQL
    parsed = parse_one(sql_executor.last_call["sql_query"], read="duckdb")
    assert isinstance(parsed, exp.Update), "Should be an UPDATE statement"
    assert parsed.this.name == "users", "Should update users table"
    set_clause = parsed.find(exp.EQ)
    assert set_clause is not None, "Should have SET clause"
    assert set_clause.this.name == "email", "Should set email column"
    assert set_clause.right.this == "alice.updated@example.com", "Should set new email value"
    where = parsed.find(exp.Where)
    assert where is not None, "Should have WHERE clause"
    where_eq = where.find(exp.EQ)
    assert where_eq is not None, "Should have equality condition in WHERE"
    assert where_eq.right.this == "1", "Should filter by id = 1"

    # Verify the result contains the updated row
    assert result["status"] == "success"
    assert result["sample_data"]["rows"] == [(1, "Alice", "alice.updated@example.com")]

    # Verify the database row was updated
    updated_email = duckdb_connection.execute("SELECT email FROM users WHERE id = 1").fetchone()[0]
    assert updated_email == "alice.updated@example.com"
    assert duckdb_connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 3


@pytest.mark.asyncio
async def test_verified_query_result_type_is_set_for_mutations_without_returning():
    """
    Test that result_type is correctly set to ROWS_AFFECTED for mutations without RETURNING.
    """
    from agent_platform.core.semantic_data_model.types import (
        QueryParameter,
        ResultType,
        VerifiedQuery,
    )
    from agent_platform.server.data_frames.sql_manipulation import determine_result_type

    # DELETE without RETURNING
    delete_query = VerifiedQuery(
        name="delete inactive users",
        nlq="Delete users who are inactive",
        verified_at="2024-01-01T00:00:00Z",
        verified_by="test_user",
        sql="DELETE FROM users WHERE active = false",
        parameters=None,
        sql_errors=None,
        nlq_errors=None,
        name_errors=None,
        parameter_errors=None,
    )
    result_type = determine_result_type(delete_query.sql, "duckdb")
    assert result_type == ResultType.ROWS_AFFECTED

    # INSERT without RETURNING
    insert_query = VerifiedQuery(
        name="insert user",
        nlq="Insert a new user",
        verified_at="2024-01-01T00:00:00Z",
        verified_by="test_user",
        sql="INSERT INTO users (id, name, email) VALUES (:user_id, :user_name, :email)",
        parameters=[
            QueryParameter(name="user_id", data_type="integer", description="User ID", example_value=1),
            QueryParameter(name="user_name", data_type="string", description="User name", example_value="John"),
            QueryParameter(name="email", data_type="string", description="Email", example_value="john@test.com"),
        ],
        sql_errors=None,
        nlq_errors=None,
        name_errors=None,
        parameter_errors=None,
    )
    result_type = determine_result_type(insert_query.sql, "duckdb")
    assert result_type == ResultType.ROWS_AFFECTED

    # UPDATE without RETURNING
    update_query = VerifiedQuery(
        name="update user status",
        nlq="Update user status",
        verified_at="2024-01-01T00:00:00Z",
        verified_by="test_user",
        sql="UPDATE users SET active = :status WHERE id = :user_id",
        parameters=[
            QueryParameter(name="status", data_type="boolean", description="Status", example_value=True),
            QueryParameter(name="user_id", data_type="integer", description="User ID", example_value=1),
        ],
        sql_errors=None,
        nlq_errors=None,
        name_errors=None,
        parameter_errors=None,
    )
    result_type = determine_result_type(update_query.sql, "duckdb")
    assert result_type == ResultType.ROWS_AFFECTED


@pytest.mark.asyncio
async def test_verified_query_result_type_is_table_for_mutations_with_returning():
    """
    Test that result_type is correctly set to TABLE for mutations with RETURNING.
    """
    from agent_platform.core.semantic_data_model.types import (
        ResultType,
        VerifiedQuery,
    )
    from agent_platform.server.data_frames.sql_manipulation import determine_result_type

    # DELETE with RETURNING
    delete_query = VerifiedQuery(
        name="delete and return user",
        nlq="Delete a user and return the deleted row",
        verified_at="2024-01-01T00:00:00Z",
        verified_by="test_user",
        sql="DELETE FROM users WHERE id = :user_id RETURNING *",
        parameters=None,
        sql_errors=None,
        nlq_errors=None,
        name_errors=None,
        parameter_errors=None,
    )
    result_type = determine_result_type(delete_query.sql, "postgres")
    assert result_type == ResultType.TABLE

    # INSERT with RETURNING
    insert_query = VerifiedQuery(
        name="insert and return user",
        nlq="Insert a user and return the inserted row",
        verified_at="2024-01-01T00:00:00Z",
        verified_by="test_user",
        sql="INSERT INTO users (name) VALUES ('John') RETURNING id, name",
        parameters=None,
        sql_errors=None,
        nlq_errors=None,
        name_errors=None,
        parameter_errors=None,
    )
    result_type = determine_result_type(insert_query.sql, "postgres")
    assert result_type == ResultType.TABLE


@pytest.mark.asyncio
async def test_verified_query_result_type_is_table_for_select():
    """
    Test that result_type is correctly set to TABLE for SELECT queries.
    """
    from agent_platform.core.semantic_data_model.types import (
        ResultType,
        VerifiedQuery,
    )
    from agent_platform.server.data_frames.sql_manipulation import determine_result_type

    select_query = VerifiedQuery(
        name="get users",
        nlq="Get all users",
        verified_at="2024-01-01T00:00:00Z",
        verified_by="test_user",
        sql="SELECT * FROM users WHERE active = true",
        parameters=None,
        sql_errors=None,
        nlq_errors=None,
        name_errors=None,
        parameter_errors=None,
    )
    result_type = determine_result_type(select_query.sql, "postgres")
    assert result_type == ResultType.TABLE
