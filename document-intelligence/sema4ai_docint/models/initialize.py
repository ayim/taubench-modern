from pathlib import Path
from typing import Any

from pydantic import Json
from sema4ai.data import DataSource, get_connection

from .migration import _migrate_postgres


def initialize_database(engine: str, datasource: DataSource) -> None:
    """Initialize the database tables for document intelligence.

    Args:
        engine: The engine to use for the database
        datasource: The document intelligence data source connection
    """
    # TODO support snowflake and sqlite
    if engine != "postgres":
        raise ValueError(f"Unsupported engine: {engine}")

    script = Path(__file__).parent / "sql" / "pg_schema.sql"
    with open(script) as file:
        sql_query = file.read()

    # Create the tables and functions if they don't exist
    datasource.native_query(sql_query, params={})

    # Run migrations to avoid having to re-create the tables.
    _migrate_postgres(datasource)


def initialize_project(project_name: str) -> None:
    """Initialize the project in the data-server."""
    try:
        get_connection().execute_sql(
            sql=f"CREATE PROJECT IF NOT EXISTS {project_name}",
        )
    except Exception as e:
        raise ValueError(
            f"Failed to create the document intelligence data-server project: {e}"
        ) from e


def _is_project_initialized(project_name: str) -> bool:
    """Check if the project exists in the data-server by checking for tables."""
    try:
        result = get_connection().execute_sql(
            sql=f"SHOW TABLES FROM {project_name};",
        )
        # Return True if there are any rows in the result (tables exist)
        # Return False if no rows (no tables, project doesn't exist)
        return len(result) > 0 if result else False
    except Exception:
        return False


def _create_views(project_name: str, views: Json[list[dict[str, Any]]]) -> None:
    """
    Iterate over the views in the data server.

    Args:
        project_name: The name of the project
        views: The views to iterate over
    """

    # Re-generate the views
    for view in views:
        try:
            view_name = view["name"]
            view_sql = view["sql"]

            print(f"Info: Creating view '{view_name}' with SQL: {view_sql}")

            # Drop the view if it exists
            _drop_view(project_name, view_name)
            get_connection().execute_sql(view_sql)

            print(f"Info: Successfully created view '{view_name}'")

        except Exception as e:
            print(f"Error creating view '{view.get('name', 'unknown')}': {e!s}")
            raise Exception(f"Failed to create view '{view.get('name', 'unknown')}': {e!s}") from e


def _create_missing_views(
    project_name: str, views: Json[list[dict[str, Any]]], force: bool = False
) -> None:
    """
    Create only the missing views in the project.

    Args:
        project_name: The name of the project
        views: The views to check and create if missing
    """
    # Extract view names from the views list
    required_view_names = [view["name"] for view in views if "name" in view]

    # Get missing views
    missing_view_names = _get_missing_views(project_name, required_view_names, force=force)

    if not missing_view_names:
        print(f"Info: All required views already exist in project {project_name}")
        return

    print(f"Info: Creating missing views: {missing_view_names}")

    missing_views = [view for view in views if view["name"] in missing_view_names]
    # Create only the missing views
    _create_views(project_name, missing_views)


def _get_existing_views(project_name: str) -> list[str]:
    """Get list of existing views in the project."""
    try:
        result = get_connection().execute_sql(
            sql=f"SHOW TABLES FROM {project_name};",
        )

        if result:
            # Each row contains the view name as a string
            existing_views = []
            for row in result:
                # Handle different possible result formats
                if isinstance(row, list | tuple) and len(row) > 0:
                    view_name = str(row[0])  # First column contains the table/view name
                elif isinstance(row, dict):
                    # If result is a list of dictionaries
                    view_name = str(row.get("name", row.get("table_name", row)))
                else:
                    view_name = str(row)
                # Handle format like "{'Tables_in_document_intelligence': 'view_name'}"
                if view_name.startswith("{") and "'Tables_in_document_intelligence'" in view_name:
                    # Extract the view name from the dictionary string
                    import re

                    match = re.search(r"'Tables_in_document_intelligence':\s*'([^']+)'", view_name)
                    if match:
                        view_name = match.group(1)

                existing_views.append(
                    view_name.lower()
                )  # Convert to lowercase for case-insensitive comparison

            print(f"Info: Extracted existing views: {existing_views}")
            return existing_views
        return []
    except Exception as e:
        print(f"Warning: Could not get existing views: {e}")
        return []


def _get_missing_views(
    project_name: str, required_views: list[str], force: bool = False
) -> list[str]:
    """Get list of views that are missing from the project."""
    if force:
        return required_views

    existing_views = _get_existing_views(project_name)
    missing_views = []

    print(f"Info: Required views: {required_views}")
    print(f"Info: Existing views: {existing_views}")

    for required_view in required_views:
        # Convert to lowercase for case-insensitive comparison
        required_view_lower = required_view.lower()
        if required_view_lower not in existing_views:
            missing_views.append(required_view)
            print(f"Info: View '{required_view}' is missing")
        else:
            print(f"Info: View '{required_view}' already exists")

    print(f"Info: Missing views: {missing_views}")
    return missing_views


def _drop_view(project_name: str, view_name: str) -> None:
    """
    Drop views from the data server.

    Args:
        datasource: The document intelligence data source connection
        view_names: The names of the views to drop
    """
    get_connection().execute_sql(f"DROP VIEW IF EXISTS {project_name}.{view_name}")


def initialize_dataserver(
    project_name: str, views: Json[list[dict[str, Any]]], force: bool = False
) -> None:
    """Initialize the data server project and create views.

    Args:
        project_name: The name of the project to initialize
        views: The views to create in the project
    """
    # Initialize the objects in MindsDB (project)
    try:
        if not _is_project_initialized(project_name):
            initialize_project(project_name)
            _create_views(project_name, views)
        else:
            print(f"Info: Project {project_name} already initialized.")
            # Check if all required views exist, create missing ones
            _create_missing_views(project_name, views, force=force)
    except Exception as e:
        raise Exception(
            f"Failed to create the document intelligence data-server project: {e}"
        ) from e
