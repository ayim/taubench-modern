import datetime
import typing
from dataclasses import dataclass
from typing import Literal, TypedDict

from agent_platform.core.data_frames.semantic_data_model_types import BaseTable

if typing.TYPE_CHECKING:
    from sema4ai.actions._table import Row


@dataclass
class DataFrameSource:
    """Represents the source of a data frame."""

    source_type: Literal["data_frame", "semantic_data_model"]
    """The type of the source.
    - "data_frame": the source is a data frame.
    - "semantic_data_model": the source is a semantic data model.
    """

    # Only available if source_type is "data_frame".
    source_id: str | None = None
    """The ID of the data frame (UUID)."""

    # Only available if source_type is "semantic_data_model".
    base_table: BaseTable | None = None
    """The base table information of the semantic data model."""

    logical_table_name: str | None = None
    """The name of the logical table (when a semantic data model is used)."""

    def __post_init__(self) -> None:
        from agent_platform.core.utils.asserts import assert_literal_value_valid

        assert_literal_value_valid(self, "source_type")

    def model_dump(self) -> dict:
        ret: dict = {"source_type": self.source_type}

        if self.source_id is not None:
            ret["source_id"] = self.source_id

        if self.base_table is not None:
            ret["base_table"] = self.base_table

        if self.logical_table_name is not None:
            ret["logical_table_name"] = self.logical_table_name

        return ret

    @classmethod
    def model_validate(cls, data: dict) -> "DataFrameSource":
        source_id = data.get("source_id")
        base_table = data.get("base_table")
        logical_table_name = data.get("logical_table_name")
        source_type = data["source_type"]

        if source_type == "data_frame":
            if not source_id:
                raise KeyError("source_id must be set when source_type is data_frame")

        elif source_type == "semantic_data_model":
            if not base_table or not logical_table_name:
                raise KeyError(
                    "base_table and logical_table_name must be set when source_type is "
                    "semantic_data_model"
                )
        else:
            raise ValueError(
                f"Invalid value for 'source_type': {source_type!r}. "
                f"Must be one of: 'data_frame', 'semantic_data_model'",
            )

        return cls(
            source_type=source_type,
            source_id=source_id,
            base_table=base_table,
            logical_table_name=logical_table_name,
        )


class _Sentinel:
    """A sentinel value."""


_SENTINEL = _Sentinel()


class ExtraDataFrameData(TypedDict, total=False):
    """Extra data for a data frame."""

    sql_dialect: str | None
    """The dialect of the SQL query that was used to create the data frame
    (can be set when the input_id_type is "sql_computation")."""

    sample_rows: "list[Row] | None"
    """The sample rows for the data frame."""


# The maximum number of rows to return to the LLM when using a data frame
# (this is the amount of samples that we'll always preload and save in the data
# frame)
DATAFRAMES_LLM_SAMPLE_ROWS_LIMIT = 10


@dataclass
class PlatformDataFrame:
    """Represents a Data Frame. Data frames may be created directly from a file
    (i.e.: a file upload) or from a computation (i.e.: a sql to be executed by ibis).

    When created from a file, the file_id must be set and the input_id_type must be "file".

    When created from a computation, the computation must be set (ibis SQL to be evaluated),
    the input_id_type must be "sql_computation" and the computation_input_sources must be set.
    """

    data_frame_id: str
    """The ID of the data frame (UUID)."""

    user_id: str
    """The ID of the user that created the data frame."""

    agent_id: str
    """The ID of the agent that the data frame belongs to."""

    thread_id: str
    """The ID of the thread that the data frame belongs to."""

    num_rows: int
    """The number of rows in the data frame."""

    num_columns: int
    """The number of columns in the data frame."""

    column_headers: list[str]
    """The headers of the columns in the data frame."""

    name: str
    """A name for the data frame to be referenced later on (as a table
    name in a sql query or variable in an expression).
    Must be unique within the thread and must be a valid variable name."""

    input_id_type: Literal["file", "sql_computation", "in_memory"]
    """The type of the input ID.
    - "file": the data frame was created from a file.
    - "sql_computation": the data frame was created from a sql computation.
    - "in_memory": the data frame was created from an in-memory data frame
        i.e.: a data frame (from polars, pyarrow, pandas, json, etc.) the
        contents must be available in the parquet_contents field.
    """

    created_at: datetime.datetime
    """The date and time the data frame was created."""

    computation_input_sources: dict[str, DataFrameSource]
    """The sources of the data frame (where the key is the reference to the name
    of the source in the computation)."""

    file_id: str | None = None
    """The reference input (file id). Only available if input_id_type is "file"."""

    file_ref: str | None = None
    """The reference of the file (usually the file name) to create the data frame from
    (when used, file_id is not needed)."""

    sheet_name: str | None = None
    """The name of the sheet that the data frame is in (only available if input_id_type is "file"
    and the file is an excel file, not csv)."""

    description: str | None = None
    """A description of the data frame."""

    computation: str | None = None
    """The computation that was used to create the data frame (a sql to be
    executed by ibis for example, only available if input_id_type is "sql_computation")."""

    parquet_contents: bytes | None = None
    """The contents of the data frame in parquet format (only available if we actually decide
    to instantiate the data frame and store it for future use, otherwise it must be recomputed)."""

    extra_data: ExtraDataFrameData | None = None
    """Extra data to be stored in the database. This is a free-form field that can be used to
    store any additional data that is not covered by the other fields. The dict may only contain
    data that can be serialized to JSON."""

    @classmethod
    def build_extra_data(
        cls,
        *,
        sql_dialect: str | None = None,
        sample_rows: "list[Row] | None" = None,
    ) -> ExtraDataFrameData:
        """Build the extra data for the data frame."""
        extra_data: ExtraDataFrameData = {}

        if sql_dialect is not None:
            extra_data["sql_dialect"] = sql_dialect

        if sample_rows is not None:
            extra_data["sample_rows"] = sample_rows

        return extra_data

    def patch_extra_data(
        self,
        *,
        sql_dialect: str | None | _Sentinel = _SENTINEL,
        sample_rows: "list[Row] | None | _Sentinel" = _SENTINEL,
    ) -> None:
        """Patch the extra data for the data frame."""
        initial: ExtraDataFrameData
        if self.extra_data is None:
            initial = {}
        else:
            initial = self.extra_data

        if not isinstance(sql_dialect, _Sentinel):
            if sql_dialect is None:
                initial.pop("sql_dialect", None)
            else:
                initial["sql_dialect"] = sql_dialect

        if not isinstance(sample_rows, _Sentinel):
            if sample_rows is None:
                initial.pop("sample_rows", None)
            else:
                initial["sample_rows"] = sample_rows

        self.extra_data = initial

    @property
    def sql_dialect(self) -> str | None:
        """The dialect of the SQL query that was used to create the data frame
        (can be set when the input_id_type is "sql_computation").
        If not set, it'll return None.
        """
        dialect = None
        if self.extra_data is not None:
            dialect = self.extra_data.get("sql_dialect")

        return dialect

    @property
    def sample_rows(self) -> "list[Row]":
        """The sample rows for the data frame."""
        if self.extra_data is None:
            return []
        return self.extra_data.get("sample_rows") or []

    def __post_init__(self) -> None:
        self.verify()

    def verify(self) -> None:  # noqa: C901
        """
        If changes are made outside, this method can be called to verify the data frame is valid.
        """

        from agent_platform.core.data_frames.data_frame_utils import (
            DataFrameNameError,
            is_valid_data_frame_name,
            make_data_frame_name_valid,
        )
        from agent_platform.core.errors.base import PlatformHTTPError
        from agent_platform.core.errors.responses import ErrorCode
        from agent_platform.core.utils.asserts import assert_literal_value_valid

        assert_literal_value_valid(self, "input_id_type")

        if self.input_id_type == "sql_computation":
            assert self.computation is not None, (
                "SQL computation must have the computation field set"
            )

        column_headers = self.column_headers
        assert isinstance(column_headers, list)
        for header in column_headers:
            assert isinstance(header, str), (
                f"Column header must be a list of strings. Got element {header} "
                f"of type {type(header)}"
            )

        assert isinstance(self.data_frame_id, str)
        assert isinstance(self.user_id, str)
        assert isinstance(self.agent_id, str)
        assert isinstance(self.thread_id, str)
        assert isinstance(self.num_rows, int)
        assert isinstance(self.num_columns, int)
        assert isinstance(self.name, str)
        assert isinstance(self.created_at, datetime.datetime)
        assert isinstance(self.computation_input_sources, dict)

        # Verify the name is a valid variable name (so that it can be properly referenced later on).
        if not is_valid_data_frame_name(self.name):
            message = (
                "Unable to create data frame because the data frame name provided "
                f"({self.name!r}) is not a valid variable name. Please retry with a valid "
                "name."
            )
            try:
                valid_name = make_data_frame_name_valid(self.name)
            except DataFrameNameError as e:
                raise PlatformHTTPError(
                    error_code=ErrorCode.UNPROCESSABLE_ENTITY,
                    message=message,
                ) from e
            else:
                raise PlatformHTTPError(
                    error_code=ErrorCode.UNPROCESSABLE_ENTITY,
                    message=(message + f" (example: {valid_name})."),
                )

        for key, source in self.computation_input_sources.items():
            assert isinstance(key, str)
            assert isinstance(source, DataFrameSource)

        if self.sheet_name is not None:
            assert isinstance(self.sheet_name, str)
        if self.file_id is not None:
            assert isinstance(self.file_id, str)
        if self.file_ref is not None:
            assert isinstance(self.file_ref, str)
        if self.description is not None:
            assert isinstance(self.description, str)
        if self.computation is not None:
            assert isinstance(self.computation, str)
        if self.extra_data is not None:
            assert isinstance(self.extra_data, dict)

    def model_dump(self) -> dict:
        import copy

        result = {
            "data_frame_id": self.data_frame_id,
            "user_id": self.user_id,
            "agent_id": self.agent_id,
            "thread_id": self.thread_id,
            "num_rows": self.num_rows,
            "num_columns": self.num_columns,
            "column_headers": self.column_headers,
            "name": self.name,
            "input_id_type": self.input_id_type,
            "created_at": self.created_at.isoformat(),
            "sheet_name": self.sheet_name,
            "computation_input_sources": {
                key: source.model_dump() for key, source in self.computation_input_sources.items()
            },
        }

        result["file_id"] = self.file_id
        result["file_ref"] = self.file_ref
        result["description"] = self.description
        result["computation"] = self.computation
        result["parquet_contents"] = self.parquet_contents
        result["extra_data"] = copy.deepcopy(self.extra_data)

        return result

    @classmethod
    def model_validate(cls, data: dict) -> "PlatformDataFrame":
        """Creates a PlatformDataFrame object from a dictionary.

        Important: the `extra_data` field is not deepcopied, so it is not safe to modify
        the reference to the original dict after the object is created.
        """
        # Parse datetime
        created_at = data["created_at"]
        if isinstance(created_at, str):
            try:
                created_at = datetime.datetime.fromisoformat(created_at)
            except ValueError as e:
                raise ValueError(
                    f"Unable to parse created_at: {created_at!r} (must be a date with a "
                    "string in ISO format)"
                ) from e
        else:
            raise ValueError(f"created_at must be a string. Got {type(created_at)}")

        # Parse computation_input_sources
        computation_input_sources = {
            key: DataFrameSource.model_validate(source_data)
            for key, source_data in data["computation_input_sources"].items()
        }

        return cls(
            data_frame_id=data["data_frame_id"],
            user_id=data["user_id"],
            agent_id=data["agent_id"],
            thread_id=data["thread_id"],
            num_rows=data["num_rows"],
            num_columns=data["num_columns"],
            column_headers=data["column_headers"],
            name=data["name"],
            input_id_type=data["input_id_type"],
            created_at=created_at,
            computation_input_sources=computation_input_sources,
            file_id=data.get("file_id"),
            file_ref=data.get("file_ref"),
            sheet_name=data.get("sheet_name"),
            description=data.get("description"),
            computation=data.get("computation"),
            parquet_contents=data.get("parquet_contents"),
            extra_data=data.get("extra_data"),
        )
