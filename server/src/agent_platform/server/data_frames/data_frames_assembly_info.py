# ruff: noqa: PLR0912, PLR0915, C901, E501
import typing
from typing import Required, TypedDict

from structlog.stdlib import get_logger

from agent_platform.core.data_frames.semantic_data_model_types import FileReference

if typing.TYPE_CHECKING:
    from agent_platform.core.data_frames.data_frames import PlatformDataFrame
    from agent_platform.server.data_frames.data_frames_kernel import Dependencies
    from agent_platform.server.data_frames.data_node import DataNodeResult
    from agent_platform.server.storage.base import BaseStorage

logger = get_logger(__name__)

NodeKind = typing.Literal["assembly_info", "data_frame", "semantic_data_model", "data_frame_source"]


def _extract_connection_details_for_assembly_info(engine: str, config: typing.Any) -> dict[str, str | None]:
    """Extract connection details from a data connection configuration for assembly info display.

    Args:
        engine: The database engine type (e.g., "postgres", "snowflake")
        config: The connection configuration object

    Returns:
        Dictionary with connection details keys: connection_hostname, connection_accountname,
        connection_user, connection_database. Values are None if not applicable for the engine.
    """
    details: dict[str, str | None] = {
        "connection_hostname": None,
        "connection_accountname": None,
        "connection_user": None,
        "connection_database": None,
    }

    if engine in ("postgres", "pgvector", "redshift", "mysql", "mssql", "timescaledb"):
        details["connection_hostname"] = getattr(config, "host", None)
        details["connection_user"] = getattr(config, "user", None)
        details["connection_database"] = getattr(config, "database", None)
    elif engine == "oracle":
        details["connection_hostname"] = getattr(config, "host", None)
        details["connection_user"] = getattr(config, "user", None)
    elif engine == "snowflake":
        details["connection_accountname"] = getattr(config, "account", None)
        details["connection_user"] = getattr(config, "user", None)
        details["connection_database"] = getattr(config, "database", None)
    elif engine == "databricks":
        details["connection_hostname"] = getattr(config, "server_hostname", None)
    elif engine == "bigquery":
        details["connection_database"] = getattr(config, "project_id", None)
    # Note: Other engines (sqlite)
    # don't have connection details we want to display

    return details


# TypedDict definitions for each node kind
class AssemblyInfoNode(TypedDict):
    """Node data for assembly_info kind."""

    error: str


class DataFrameNodeBase(TypedDict):
    """Base fields for data_frame nodes."""

    name: str
    input_id_type: str
    description: str | None


class DataFrameNodeSqlComputation(DataFrameNodeBase):
    """Node data for data_frame with sql_computation input_id_type."""

    sql_query: str | None
    sql_dialect: str | None
    full_sql_query_logical_str: str | None


class DataFrameNodeFile(DataFrameNodeBase):
    """Node data for data_frame with file input_id_type."""

    file_id: str | None
    file_ref: str | None
    sheet_name: str | None


class DataFrameNodeInMemory(DataFrameNodeBase):
    """Node data for data_frame with in_memory input_id_type."""


# Union type for all DataFrame node variants
DataFrameNode = DataFrameNodeSqlComputation | DataFrameNodeFile | DataFrameNodeInMemory


class SemanticDataModelNodeDatabase(TypedDict, total=False):
    """Node data for semantic_data_model with database source."""

    logical_table_name: Required[str]
    source: Required[typing.Literal["database"]]
    data_connection_id: str | None
    database: str | None
    schema: str | None
    table: str | None
    connection_hostname: str | None
    connection_accountname: str | None
    connection_user: str | None
    connection_database: str | None


class SemanticDataModelNodeFile(TypedDict):
    """Node data for semantic_data_model with file source."""

    logical_table_name: str
    source: typing.Literal["file"]
    file_reference: dict[str, str] | FileReference | None
    table: str | None


class SemanticDataModelNodeDataFrame(TypedDict):
    """Node data for semantic_data_model with data frame source."""

    logical_table_name: str
    source: typing.Literal["data_frame"]
    data_frame_name: str | None


class SemanticDataModelNodeError(TypedDict):
    """Node data for semantic_data_model with error."""

    logical_table_name: str
    error: str


# Union type for all SemanticDataModel node variants
SemanticDataModelNode = (
    SemanticDataModelNodeDatabase
    | SemanticDataModelNodeFile
    | SemanticDataModelNodeDataFrame
    | SemanticDataModelNodeError
)


class DataFrameSourceNode(TypedDict, total=False):
    """Node data for data_frame_source kind."""

    name: str
    source_type: str
    source_id: str | None


# Union type for all node data
NodeData = AssemblyInfoNode | DataFrameNode | SemanticDataModelNode | DataFrameSourceNode


class _Node:
    def __init__(self, kind: NodeKind, data: NodeData | None):
        self.kind = kind
        self.data = data
        self.children: dict[str, _Node] = {}

    def to_dict(self) -> dict[str, typing.Any]:
        result = {
            "kind": self.kind,
            "data": self.data,
        }
        result["children"] = {k: v.to_dict() for k, v in self.children.items()}
        return result

    async def enrich_connection_details(self, storage: "BaseStorage") -> None:
        """Enrich nodes with connection details by fetching data connections."""
        if self.kind == "semantic_data_model" and self.data:
            data = typing.cast(SemanticDataModelNode, self.data)
            if data.get("source") == "database":
                db_data = typing.cast(SemanticDataModelNodeDatabase, data)
                data_connection_id = db_data.get("data_connection_id")
                if data_connection_id:
                    try:
                        from agent_platform.server.storage.errors import DataConnectionNotFoundError

                        connection = await storage.get_data_connection(data_connection_id)
                        config = connection.configuration

                        # Extract connection details based on engine type
                        connection_details = _extract_connection_details_for_assembly_info(connection.engine, config)
                        db_data["connection_hostname"] = connection_details["connection_hostname"]
                        db_data["connection_accountname"] = connection_details["connection_accountname"]
                        db_data["connection_user"] = connection_details["connection_user"]
                        db_data["connection_database"] = connection_details["connection_database"]
                    except DataConnectionNotFoundError:
                        # Connection was deleted or doesn't exist - log and continue without details
                        logger.warning(
                            "Data connection not found when enriching assembly info",
                            data_connection_id=data_connection_id,
                        )
                    except Exception as e:
                        # Other errors (e.g., decryption failures) - log and continue without details
                        logger.warning(
                            "Failed to enrich connection details",
                            data_connection_id=data_connection_id,
                            error=str(e),
                            exc_info=True,
                        )

        # Recursively enrich children
        for child_node in self.children.values():
            await child_node.enrich_connection_details(storage)

    def _extract_dependency_summary(self, indent: int = 0) -> str:
        """
        Here we just want to extract something to be considered a simple summary of the dependencies:
        - `test_data_frame`
          - `file_data` (file `test_data.csv`)
          - `another_data_frame` (data frame)
            - `test_data_frame` (data frame)
        """
        if not self.children:
            return ""

        lines: list[str] = []
        indent_str = "    " * indent

        for child_name, child_node in sorted(self.children.items()):
            if not child_node.data:
                continue

            source_desc = ""
            if child_node.kind == "data_frame":
                child_data = typing.cast(DataFrameNode, child_node.data)
                input_id_type = child_data.get("input_id_type", "unknown")
                if input_id_type == "file":
                    file_data = typing.cast(DataFrameNodeFile, child_data)
                    file_ref = file_data.get("file_ref")
                    if file_ref:
                        source_desc = f" (file `{file_ref}`)"
                    else:
                        source_desc = " (file)"
                elif input_id_type == "in_memory":
                    source_desc = " (in-memory data frame)"
                elif input_id_type == "sql_computation":
                    source_desc = " (data frame)"
                else:
                    source_desc = " (data frame)"
            elif child_node.kind == "semantic_data_model":
                semantic_data = typing.cast(SemanticDataModelNode, child_node.data)
                logical_table_name = semantic_data.get("logical_table_name", "unknown")
                source = semantic_data.get("source")
                if source == "file":
                    file_data = typing.cast(SemanticDataModelNodeFile, semantic_data)
                    file_reference = file_data.get("file_reference")
                    if file_reference and isinstance(file_reference, dict):
                        file_ref = file_reference.get("file_ref")
                        if file_ref:
                            source_desc = f" (file `{file_ref}`)"
                        else:
                            source_desc = " (semantic data model file)"
                    else:
                        source_desc = f" (semantic data model logical table `{logical_table_name}`)"
                elif source == "database":
                    source_desc = f" (semantic data model logical table `{logical_table_name}`)"
                else:
                    source_desc = f" (semantic data model logical table `{logical_table_name}`)"
            elif child_node.kind == "data_frame_source":
                source_data = typing.cast(DataFrameSourceNode, child_node.data)
                source_type = source_data.get("source_type", "unknown")
                source_desc = f" ({source_type})"

            lines.append(f"{indent_str}- `{child_name}`{source_desc}")

            # Recursively add nested dependencies
            child_summary = child_node._extract_dependency_summary(indent + 1)
            if child_summary:
                lines.append(child_summary)

        return "\n".join(lines)

    def as_markdown(self, level: int = 0) -> str:
        """Convert the node tree to a markdown format."""
        import textwrap

        lines: list[str] = []
        indent_str = ""

        if not self.data:
            return ""

        if self.kind == "data_frame":
            data = typing.cast(DataFrameNode, self.data)
            name = data.get("name", "unknown")
            input_id_type = data.get("input_id_type", "unknown")

            lines.append(f"{indent_str}## Data Frame: `{name}`")
            lines.append(f"{indent_str}")
            description = data.get("description")
            if description:
                lines.append(f"{indent_str}#### Description:")
                lines.append(f"{indent_str}")
                lines.append(f"{indent_str}{description}")
                lines.append(f"{indent_str}")

            dependency_summary = self._extract_dependency_summary()
            if dependency_summary:
                lines.append(f"{indent_str}#### Dependency Summary:")
                lines.append("")
                lines.append(textwrap.indent(dependency_summary, indent_str))
            else:
                lines.append(f"{indent_str}#### Dependency Summary:")
                lines.append("")
                lines.append(f"{indent_str}No dependencies")
                lines.append("")
            lines.append(f"{indent_str}")
            lines.append(f"{indent_str}#### Type: {input_id_type}")
            lines.append(f"{indent_str}")

            if input_id_type == "sql_computation":
                sql_data = typing.cast(DataFrameNodeSqlComputation, data)
                sql_query = sql_data.get("sql_query")
                sql_dialect = sql_data.get("sql_dialect")
                if sql_query:
                    lines.append(f"{indent_str}#### SQL Query:")
                    lines.append("")
                    prefix = indent_str + "    "
                    lines.append(textwrap.indent(sql_query, prefix))
                    if sql_dialect:
                        lines.append(f"{indent_str}#### SQL Dialect: {sql_dialect}")
                    lines.append(f"{indent_str}")

            elif input_id_type == "file":
                file_data = typing.cast(DataFrameNodeFile, data)
                file_ref = file_data.get("file_ref")
                sheet_name = file_data.get("sheet_name")
                lines.append(f"{indent_str}#### Source: File")
                if file_ref:
                    lines.append(f"{indent_str}- File Reference: `{file_ref}`")
                if sheet_name:
                    lines.append(f"{indent_str}- Sheet Name: `{sheet_name}`")
                lines.append(f"{indent_str}")

            elif input_id_type == "in_memory":
                lines.append(f"{indent_str}#### Source: In-memory data frame")
                lines.append(f"{indent_str}")

            else:
                lines.append(
                    f"{indent_str}#### Error: Unknown input_id_type: {input_id_type} when dealing with data frame data: {self.data}"
                )

        elif self.kind == "semantic_data_model":
            data = typing.cast(SemanticDataModelNode, self.data)
            logical_table_name = data.get("logical_table_name", "unknown")
            source = data.get("source")

            lines.append(f"{indent_str}## Semantic Data Model: `{logical_table_name}`")
            lines.append(f"{indent_str}")

            if source == "database":
                db_data = typing.cast(SemanticDataModelNodeDatabase, data)
                lines.append(f"{indent_str}#### Source: Database")
                connection_hostname = db_data.get("connection_hostname")
                connection_accountname = db_data.get("connection_accountname")
                connection_user = db_data.get("connection_user")
                connection_database = db_data.get("connection_database")
                database = db_data.get("database")
                schema = db_data.get("schema")
                table = db_data.get("table")

                # Display connection details if available, otherwise fall back to connection ID
                if connection_hostname:
                    lines.append(f"{indent_str}- Hostname: `{connection_hostname}`")
                elif connection_accountname:
                    lines.append(f"{indent_str}- Account: `{connection_accountname}`")

                if connection_user:
                    lines.append(f"{indent_str}- User: `{connection_user}`")

                if connection_database:
                    lines.append(f"{indent_str}- Database: `{connection_database}`")
                elif database:
                    lines.append(f"{indent_str}- Database: `{database}`")

                if schema:
                    lines.append(f"{indent_str}- Schema: `{schema}`")
                if table:
                    lines.append(f"{indent_str}- Table: `{table}`")
                lines.append(f"{indent_str}")

            elif source == "file":
                file_data = typing.cast(SemanticDataModelNodeFile, data)
                lines.append(f"{indent_str}#### Source: File")
                file_reference = file_data.get("file_reference")
                if file_reference:
                    if isinstance(file_reference, dict):
                        file_ref = file_reference.get("file_ref")
                        sheet_name = file_reference.get("sheet_name")
                        if file_ref:
                            lines.append(f"{indent_str}- File Reference: `{file_ref}`")
                        if sheet_name:
                            lines.append(f"{indent_str}- Sheet Name: `{sheet_name}`")
                    else:
                        # Shouldn't happen, but just in case
                        lines.append(f"{indent_str}- File Reference: `{file_reference}`")
                table = file_data.get("table")
                if table:
                    lines.append(f"{indent_str}- Table: `{table}`")
                lines.append(f"{indent_str}")

            elif source == "data_frame":
                df_data = typing.cast(SemanticDataModelNodeDataFrame, data)
                lines.append(f"{indent_str}#### Source: Data Frame")
                data_frame_name = df_data.get("data_frame_name")
                if data_frame_name:
                    lines.append(f"{indent_str}- Data Frame Name: `{data_frame_name}`")
                table = df_data.get("table")
                if table:
                    lines.append(f"{indent_str}- Table: `{table}`")
                lines.append(f"{indent_str}")

            else:
                error_data = typing.cast(SemanticDataModelNodeError, data)
                error = error_data.get("error", "Unknown source")
                lines.append(f"{indent_str}#### Error: {error}")
                lines.append(f"{indent_str}")

        elif self.kind == "data_frame_source":
            data = typing.cast(DataFrameSourceNode, self.data)
            name = data.get("name", "unknown")
            source_type = data.get("source_type", "unknown")
            source_id = data.get("source_id")

            lines.append(f"{indent_str}## Data Frame Source: `{name}`")
            lines.append(f"{indent_str}")
            lines.append(f"{indent_str}#### Source Type: {source_type}")
            if source_id:
                lines.append(f"{indent_str}- Source ID: `{source_id}`")
            lines.append(f"{indent_str}")

        elif self.kind == "assembly_info":
            data = typing.cast(AssemblyInfoNode, self.data)
            error = data.get("error")
            if error:
                lines.append(f"{indent_str}## Assembly Info")
                lines.append(f"{indent_str}")
                lines.append(f"{indent_str}#### Error: {error}")
                lines.append(f"{indent_str}")

        else:
            lines.append(f"{indent_str}#### Error: Unknown kind: {self.kind} when dealing with data: {self.data}")

        # Add children recursively
        if self.children:
            if level == 0:
                lines.append("## Dependencies")
                lines.append("")

            for _child_name, child_node in sorted(self.children.items()):
                child_markdown = child_node.as_markdown(level=level + 1)
                if child_markdown.strip():
                    lines.append(child_markdown)
                    lines.append("")  # Add extra line between top-level sections

        return "\n".join(lines)


class AssemblyInfo:
    """
    A class to represent the assembly information of a data frame.
    """

    def __init__(self):
        self._initial_data_frame: PlatformDataFrame | None = None
        self._dependencies: Dependencies | None = None
        self._final_data_node: DataNodeResult | None = None

    def set_initial_data_frame(self, data_frame: "PlatformDataFrame"):
        self._initial_data_frame = data_frame

    def set_dependencies(self, dependency: "Dependencies"):
        self._dependencies = dependency

    def set_final_data_node(self, data_node: "DataNodeResult"):
        self._final_data_node = data_node

    def to_tree(self) -> "_Node":
        from agent_platform.server.data_frames.data_node import DataNodeFromIbisResult

        if not self._initial_data_frame:
            assembly_info_node: AssemblyInfoNode = {
                "error": "No initial data frame provided",
            }
            root = _Node(kind="assembly_info", data=assembly_info_node)
            return root

        data_frame = self._initial_data_frame
        root = _Node(kind="data_frame", data=None)

        data: DataFrameNode | None = None

        if data_frame.input_id_type == "sql_computation":
            if isinstance(self._final_data_node, DataNodeFromIbisResult):
                full_sql_query_logical_str = self._final_data_node.full_sql_query_logical_str
            else:
                full_sql_query_logical_str = None

            data_sql_computation: DataFrameNodeSqlComputation = {
                "name": data_frame.name,
                "input_id_type": data_frame.input_id_type,
                "sql_query": data_frame.computation,
                "sql_dialect": data_frame.sql_dialect,
                "full_sql_query_logical_str": full_sql_query_logical_str,
                "description": data_frame.description,
            }
            data = data_sql_computation

            if self._dependencies:
                self._build_dependencies_tree(root, self._dependencies)

        elif data_frame.input_id_type == "file":
            data_file: DataFrameNodeFile = {
                "name": data_frame.name,
                "input_id_type": data_frame.input_id_type,
                "file_id": data_frame.file_id,
                "file_ref": data_frame.file_ref,
                "sheet_name": data_frame.sheet_name,
                "description": data_frame.description,
            }
            data = data_file

        elif data_frame.input_id_type == "in_memory":
            data_in_memory: DataFrameNodeInMemory = {
                "name": data_frame.name,
                "input_id_type": data_frame.input_id_type,
                "description": data_frame.description,
            }
            data = data_in_memory

        root.data = data

        return root

    def _build_dependencies_tree(self, parent_node: "_Node", dependencies: "Dependencies") -> None:
        """Recursively build the dependency tree."""
        # Add leaf data frame dependencies (file or in_memory)
        for name, df in dependencies._data_frames.items():
            if df.input_id_type == "file":
                child = _Node(
                    kind="data_frame",
                    data=DataFrameNodeFile(
                        name=name,
                        input_id_type=df.input_id_type,
                        file_id=df.file_id,
                        file_ref=df.file_ref,
                        sheet_name=df.sheet_name,
                        description=df.description,
                    ),
                )
            elif df.input_id_type == "in_memory":
                child = _Node(
                    kind="data_frame",
                    data=DataFrameNodeInMemory(
                        name=name,
                        input_id_type=df.input_id_type,
                        description=df.description,
                    ),
                )
            else:
                child = _Node(
                    kind="data_frame",
                    data=DataFrameNodeInMemory(
                        name=name,
                        input_id_type=df.input_id_type,
                        description=df.description,
                    ),
                )
            parent_node.children[name] = child

        # Add data frame source dependencies (semantic data model)
        for name, df_source in dependencies._data_frames_sources.items():
            if df_source.source_type == "semantic_data_model":
                base_table = df_source.base_table
                if base_table is None:
                    child = _Node(
                        kind="semantic_data_model",
                        data=SemanticDataModelNodeError(
                            logical_table_name=name,
                            error="base_table is None",
                        ),
                    )
                else:
                    # Check if it's from a database connection
                    data_connection_id = base_table.get("data_connection_id")
                    if data_connection_id is not None:
                        db_data: SemanticDataModelNodeDatabase = {
                            "logical_table_name": name,
                            "source": "database",
                            "data_connection_id": data_connection_id,
                            "database": base_table.get("database"),
                            "schema": base_table.get("schema"),
                            "table": base_table.get("table"),
                        }
                        source_data = db_data
                    # Check if it's from a file
                    elif base_table.get("file_reference") is not None:
                        file_ref = base_table.get("file_reference")
                        file_data: SemanticDataModelNodeFile = {
                            "logical_table_name": name,
                            "source": "file",
                            "file_reference": file_ref,
                            "table": base_table.get("table"),
                        }
                        source_data = file_data
                    # Check if it's from a data frame
                    elif base_table.get("table") is not None:
                        df_data: SemanticDataModelNodeDataFrame = {
                            "logical_table_name": name,
                            "source": "data_frame",
                            "data_frame_name": base_table.get("table"),
                        }
                        source_data = df_data
                    else:
                        error_data: SemanticDataModelNodeError = {
                            "logical_table_name": name,
                            "error": (
                                "Unable to determine source (no data_connection_id, file_reference, or data_frame_name)"
                            ),
                        }
                        source_data = error_data

                    child = _Node(kind="semantic_data_model", data=source_data)
            else:
                child = _Node(
                    kind="data_frame_source",
                    data=DataFrameSourceNode(
                        name=name,
                        source_type=df_source.source_type,
                        source_id=df_source.source_id,
                    ),
                )
            parent_node.children[name] = child

        # Add sub-dependencies (recursive SQL computations)
        for name, sub_dependencies in dependencies._sub_dependencies.items():
            sub_df = sub_dependencies._data_frame
            use_data: DataFrameNodeSqlComputation = {
                "name": name,
                "input_id_type": sub_df.input_id_type,
                "sql_query": sub_df.computation,
                "sql_dialect": sub_df.sql_dialect,
                "description": sub_df.description,
                "full_sql_query_logical_str": None,
            }
            child = _Node(
                kind="data_frame",
                data=use_data,
            )
            # Recursively build the tree for this sub-dependency
            self._build_dependencies_tree(child, sub_dependencies)
            parent_node.children[name] = child

    def __repr__(self) -> str:
        import yaml

        if not self._initial_data_frame:
            return "No initial data frame provided (information incomplete)"

        as_tree = self.to_tree()
        return yaml.safe_dump(as_tree.to_dict())

    async def to_markdown(self, storage: "BaseStorage | None" = None) -> str:
        """Convert assembly info to markdown, optionally enriching with connection details.

        Args:
            storage: Optional storage instance to fetch connection details from.
                    If provided, connection details will be enriched in the markdown output.
        """
        if not self._initial_data_frame:
            return "No initial data frame provided (information incomplete)"

        as_tree = self.to_tree()
        if storage is not None:
            await as_tree.enrich_connection_details(storage)
        return as_tree.as_markdown()

    def __str__(self) -> str:
        if not self._initial_data_frame:
            return "No initial data frame provided (information incomplete)"

        as_tree = self.to_tree()
        return as_tree.as_markdown()
