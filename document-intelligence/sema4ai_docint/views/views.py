"""
Core functionality for generating database views from business schemas.
"""

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from sema4ai.data import DataSource

from sema4ai_docint.logging import logger

from .adapters import DBAdapter, PostgresAdapter
from .schema import BusinessSchema, DataFormat, SchemaField


@dataclass
class ArrayPath:
    """Represents an array path in the JSON document with its alias."""

    path: str
    alias: str


@dataclass
class SelectExpression:
    """Represents a field expression in the SELECT clause."""

    field_name: str
    json_path: str
    field_type: str
    attributes: dict[str, Any] | None = None


@dataclass
class Column:
    """Represents a database column in a view. Includes the column name and datatype."""

    name: str
    type: str


@dataclass
class View:
    """Represents a view in the database."""

    name: str
    sql: str
    columns: list[Column]


def transform_business_schema(business_schema: dict[str, Any]) -> BusinessSchema:
    """
    Transform a JSON Schema to BusinessSchema format.

    Args:
        business_schema: A JSON Schema object

    Returns:
        A BusinessSchema object
    """
    # The BusinessSchema is a JSON Schema for an "object". Do some basic sanity checks.
    if "type" not in business_schema:
        raise ValueError("Business schema must have a type")
    if business_schema["type"] != "object":
        raise ValueError("Business schema must be an object")
    if "properties" not in business_schema:
        raise ValueError("Business schema must have properties")

    fields = []

    def process_properties(properties: dict[str, Any], current_path: str = "") -> None:
        for prop_name, prop_schema in properties.items():
            new_path = f"{current_path}.{prop_name}" if current_path else prop_name

            if prop_schema.get("type") == "array":
                # Handle array items
                items = prop_schema.get("items", {})
                if items.get("type") == "object":
                    # Process nested object properties
                    process_properties(items.get("properties", {}), f"{new_path}[]")
                else:
                    # Handle primitive array items
                    # Remove [] from path for name generation but keep it in the path
                    name_path = new_path.replace("[]", "")
                    field_name = name_path.upper().replace(".", "_")
                    fields.append(
                        SchemaField(
                            path=new_path,
                            name=field_name,
                            format=DataFormat(type=items.get("type", "string")),
                        )
                    )
            elif prop_schema.get("type") == "object":
                # Process nested object properties
                process_properties(prop_schema.get("properties", {}), new_path)
            else:
                # Handle primitive types
                # Remove [] from path for name generation but keep it in the path
                name_path = new_path.replace("[]", "")
                field_name = name_path.upper().replace(".", "_")
                format_attrs = {}

                # Handle enum types
                if "enum" in prop_schema:
                    format_attrs["enum"] = prop_schema["enum"]

                fields.append(
                    SchemaField(
                        path=new_path,
                        name=field_name,
                        format=DataFormat(
                            type=prop_schema.get("type", "string"),
                            attributes=format_attrs if format_attrs else None,
                        ),
                    )
                )

    # Recursively process the properties, filling out `fields`
    process_properties(business_schema["properties"])

    return BusinessSchema(fields=fields)


class ViewGenerator:
    """
    Class for generating SQL views from business schemas.
    """

    def __init__(
        self,
        source_table_name: str = "docs",
        document_column_name: str = "doc",
        datasource_name: str | None = "local_datasource",
        project_name: str | None = "mindsdb",
        db_adapter: DBAdapter | None = None,
    ):
        """
        Initialize the ViewGenerator.

        Args:
            source_table_name: The name of the table containing the documents
            document_column_name: The column name in `source_table_name` that contains the
                extracted JSON object from the document
            datasource_name: The name of the datasource in MindsDB (None for Postgres-native views)
            project_name: The name of the project schema where views will be created
                (None for Postgres-native views)
            db_adapter: Database adapter to use, defaults to PostgresAdapter if None
        """
        self.source_table_name = source_table_name
        self.document_column_name = document_column_name
        self.datasource_name = datasource_name
        self.project_name = project_name
        self.db_adapter = db_adapter or PostgresAdapter()
        logger.info(
            f"Initialized ViewGenerator with source_table_name={source_table_name}, "
            f"document_column_name={document_column_name}, "
            f"datasource_name={datasource_name}, "
            f"project_name={project_name}"
        )

    def generate_views(self, business_schema: BusinessSchema, use_case_name: str) -> list[View]:
        """
        Generate SQL views based on the business schema.

        Args:
            business_schema: A BusinessSchema object defining the schema fields
            use_case_name: The name of the use case
        Returns:
            A dictionary mapping view names to SQL CREATE VIEW statements
        """
        logger.info(
            f"Generating views from business schema with {len(business_schema.fields)} paths"
        )
        if not use_case_name or use_case_name.isspace():
            raise ValueError("use_case_name is required")

        # Group paths by their top-level array components
        path_groups = self._group_paths_by_arrays(business_schema)
        logger.info(f"Grouped paths into {len(path_groups)} view groups")

        # Generate a view for each group
        views = []
        for group_name, paths in path_groups.items():
            logger.debug(f"Generating view for group '{group_name}' with {len(paths)} paths")
            view_name = f"{use_case_name.strip()}_{group_name.strip()}"
            view_name = view_name.upper()
            view_sql, columns = self._generate_view_for_group(view_name, paths, use_case_name)
            views.append(
                View(
                    name=view_name,
                    sql=view_sql,
                    columns=columns,
                )
            )

        logger.info(f"Successfully generated {len(views)} views")
        return views

    def _group_paths_by_arrays(
        self, business_schema: BusinessSchema
    ) -> dict[str, list[SchemaField]]:
        """
        Group paths by their top-level array components.
        Paths without arrays go into a 'base' group.
        Paths with different top-level arrays go into separate groups.
        """
        groups = defaultdict(list)
        base_paths = []

        # First pass: identify all top-level arrays and group paths
        for field in business_schema.fields:
            path = field.path

            # Find all array components in the path using split
            array_components: list[str] = []
            parts = path.split(".")
            for part in parts:
                if part.endswith("[]"):
                    array_components.append(part[:-2])  # Remove the '[]' to get the component name

            if not array_components:
                # No arrays in this path, add to base group
                base_paths.append(field)
                logger.debug(f"Added path '{path}' to base paths (no arrays)")
            else:
                # Get the first (top-level) array component
                top_array = array_components[0]

                # Create a generic group name based on the top-level array,
                # normalizing the view name
                group_name = top_array.upper().replace("-", "_").replace(" ", "_")

                groups[group_name].append(field)
                logger.debug(
                    f"Added path '{path}' to group '{group_name}' (top array: {top_array})"
                )

        # Add base paths to all groups
        for group_name in groups:
            groups[group_name] = base_paths + groups[group_name]
            logger.debug(f"Added {len(base_paths)} base paths to group '{group_name}'")

        # If we only have base paths, create a single view
        if not groups and base_paths:
            groups["base_view"] = base_paths
            logger.debug(
                f"Created 'base_view' group with {len(base_paths)} paths (no arrays found)"
            )

        return groups

    def _generate_view_for_group(
        self, view_name: str, paths: list[SchemaField], use_case_name: str
    ) -> tuple[str, list[Column]]:
        """
        Generate a SQL view for a group of paths.

        Args:
            view_name: The name of the view to create
            paths: A list of SchemaField objects
            use_case_name: The name of the use case
        Returns:
            A SQL CREATE VIEW statement
        """
        # Parse paths to extract array paths and field paths
        array_paths, select_expressions = self._parse_paths(paths)
        logger.debug(
            f"Parsed {len(array_paths)} array paths and {len(select_expressions)} select "
            f"expressions for view '{view_name}'"
        )

        # Build the SELECT clause
        select_clause = (
            f"SELECT\n    {self.source_table_name}.id AS DOCUMENT_ID, "
            f"{self.source_table_name}.document_name AS DOCUMENT_NAME, "
            f"{self.source_table_name}.document_layout AS DOCUMENT_LAYOUT "
        )

        columns = []
        for expr in select_expressions:
            # Apply type casting using the adapter
            typed_path = self.db_adapter.apply_type_cast(
                expr.json_path, expr.field_type, expr.attributes
            )
            select_clause += f",\n    {typed_path} AS {expr.field_name}"
            columns.append(Column(name=expr.field_name, type=expr.field_type))

        # Build the FROM clause conditionally
        if self.datasource_name:
            # MindsDB syntax with datasource reference
            from_clause = (
                f"FROM\n    `{self.datasource_name}`.{self.source_table_name} AS "
                f"{self.source_table_name}"
            )
        else:
            # Postgres-native syntax (direct table reference)
            from_clause = f"FROM\n    {self.source_table_name}"

        where_clause = f"WHERE\n    {self.source_table_name}.data_model = '{use_case_name}'"

        # Build CREATE VIEW clause conditionally
        if self.project_name:
            # MindsDB syntax with project namespace
            create_view = f"CREATE VIEW {self.project_name}.{view_name} AS"
        else:
            # Postgres-native syntax (no namespace)
            create_view = f"CREATE VIEW {view_name} AS"

        # Combine everything into a CREATE VIEW statement
        view_sql = f"{create_view} (\n{select_clause}\n{from_clause}\n{where_clause}\n);"
        logger.debug(f"Generated SQL for view '{view_name}':\n{view_sql}")

        return view_sql, columns

    def _parse_paths(
        self, paths: list[SchemaField]
    ) -> tuple[list[ArrayPath], list[SelectExpression]]:
        """
        Parse paths to extract array paths and field expressions.

        Returns:
            A tuple containing:
            - A list of ArrayPath objects for array elements
            - A list of SelectExpression objects for SELECT expressions
        """
        array_paths: list[ArrayPath] = []  # List of ArrayPath objects for arrays
        select_expressions: list[SelectExpression] = []

        for field in paths:
            path = field.path
            name = field.name
            field_type = field.format.type
            attributes = field.format.attributes

            logger.debug(f"Processing path '{path}' with name '{name}'")
            logger.debug(
                f"Field '{name}' has type '{field_type}'"
                + (f" with attributes {attributes}" if attributes else "")
            )

            # Parse the path into components using split instead of regex
            components = []
            for part in path.split("."):
                if part.endswith("[]"):
                    component = part[:-2]  # Remove the '[]'
                    is_array = True
                else:
                    component = part
                    is_array = False
                components.append((component, is_array))

            # Track the current JSON path as we build it
            current_path = self.document_column_name

            # Process each component
            for i, (component, is_array) in enumerate(components):
                if is_array:
                    # This is an array component
                    # Build array path using json_array_elements
                    current_path = f"json_array_elements({current_path}->'{component}')"
                else:
                    # This is a regular object property
                    is_last = i == len(components) - 1

                    # Build JSON path using the adapter
                    json_path = self.db_adapter.build_json_path(component, is_last, current_path)

                    if is_last:
                        # This is the last component (the actual field we want)
                        select_expressions.append(
                            SelectExpression(
                                field_name=name,
                                json_path=json_path,
                                field_type=field_type,
                                attributes=attributes,
                            )
                        )
                        logger.debug(
                            f"Added select expression '{json_path}' as '{name}'"
                            + (f" with type '{field_type}'" if field_type else "")
                        )
                    else:
                        # This is an intermediate object
                        current_path = json_path
                        logger.debug(f"Updated current path to '{current_path}'")

        return array_paths, select_expressions

    def _get_parent_path(self, array_path: str, previous_arrays: list[ArrayPath]) -> str:
        """
        Get the parent path for a nested array, considering previous array aliases.

        Args:
            array_path: The original array path
            previous_arrays: List of previously processed ArrayPath objects

        Returns:
            The updated array path using aliases for parent arrays
        """
        # If there are no previous arrays, return the original path
        if not previous_arrays:
            return array_path

        # Check if this array path contains any previous array paths
        original_path = array_path
        for prev_array in previous_arrays:
            # If this array path starts with a previous path, replace it with the alias
            if array_path.startswith(prev_array.path[:-1]):  # Remove the trailing quote
                # Replace the previous path with its alias
                array_path = array_path.replace(prev_array.path, prev_array.alias)
                logger.debug(
                    f"Updated array path from '{original_path}' to '{array_path}' "
                    f"using alias '{prev_array.alias}'"
                )
                break

        # If no replacements were made, return the original path
        return array_path

    def drop_mindsdb_view(self, view_name: str) -> None:
        """
        Drop a MindsDB view from the data server.

        This method drops views that were created in MindsDB with project namespace.
        Uses the sema4ai.data connection to execute the DROP VIEW statement.

        Args:
            view_name: The name of the view to drop (without project prefix)

        Raises:
            Exception: If the view cannot be dropped
        """
        from sema4ai.data import get_connection

        if not self.project_name:
            raise ValueError(
                "Cannot drop MindsDB view without project_name. "
                "Use drop_postgres_view() for Postgres-native views."
            )

        try:
            get_connection().execute_sql(f"DROP VIEW IF EXISTS {self.project_name}.{view_name}")
            logger.info(f"Dropped MindsDB view: {self.project_name}.{view_name}")
        except Exception as e:
            logger.error(f"Failed to drop MindsDB view {view_name}: {e}")
            raise

    @classmethod
    def drop_postgres_view(
        cls, view_name: str, datasource: DataSource, cascade: bool = True
    ) -> None:
        """
        Drop a Postgres-native view directly from the database.

        This method drops views that were created directly in Postgres without MindsDB.
        Uses the datasource's native_query method to execute the DROP VIEW statement.

        Args:
            view_name: The name of the view to drop
            datasource: The datasource connection to execute the drop statement
            cascade: Whether to use CASCADE option (default: True)

        Raises:
            Exception: If the view cannot be dropped
        """
        cascade_clause = " CASCADE" if cascade else ""
        drop_sql = f"DROP VIEW IF EXISTS {view_name}{cascade_clause}"

        try:
            datasource.native_query(drop_sql, {})
            logger.info(f"Dropped Postgres view: {view_name}")
        except Exception as e:
            logger.error(f"Failed to drop Postgres view {view_name}: {e}")
            raise

    @classmethod
    def create_postgres_views(cls, views: list[View], datasource: DataSource) -> None:
        """
        Create a Postgres-native view directly in the database.

        This method creates views directly in Postgres without MindsDB.
        Uses the datasource's native_query method to execute the CREATE VIEW statement.

        Args:
            views: The list of views to create
            datasource: The datasource connection to execute the create statement

        Raises:
            Exception: If the view cannot be created
        """
        for view in views:
            # view.sql already contains the full CREATE VIEW statement, so use it directly
            try:
                datasource.native_query(view.sql, {})
                logger.info(f"Created Postgres view: {view.name}")
            except Exception as e:
                logger.error(f"Failed to create Postgres view {view.name}: {e}")
                raise
