import dataclasses
import datetime
import typing
from typing import Annotated, Literal, TypedDict

from fastapi import HTTPException, Response
from fastapi.routing import APIRouter
from pydantic.main import BaseModel
from structlog.stdlib import get_logger

from agent_platform.core.data_frames.semantic_data_model_types import VerifiedQuery
from agent_platform.core.errors import ErrorCode, PlatformHTTPError
from agent_platform.server.api.dependencies import (
    StorageDependency,
)
from agent_platform.server.auth import AuthedUser
from agent_platform.server.kernel.semantic_data_model import get_semantic_data_model_name
from sema4ai.common.callback import Callback

if typing.TYPE_CHECKING:
    import pyarrow
    from sema4ai.actions import Row

    from agent_platform.core.files import UploadedFile
    from agent_platform.core.thread import Thread
    from agent_platform.server.data_frames.data_reader import FileDataReader
    from agent_platform.server.storage.base import BaseStorage

router = APIRouter()
logger = get_logger(__name__)


@dataclasses.dataclass
class _DataFrameInspectionAPI:
    thread_id: Annotated[str, "The ID of the thread that the data frame is in."]
    name: Annotated[str, "The name of the data frame."]
    sheet_name: Annotated[
        str | None,
        "The name of the sheet that the data frame is in (None if not applicable, i.e.: "
        "if the data frame is a .csv, not excel).",
    ]
    num_rows: Annotated[int, "The number of rows in the data frame."]
    num_columns: Annotated[int, "The number of columns in the data frame."]
    created_at: Annotated[datetime.datetime, "The date and time the data frame was created."]
    column_headers: Annotated[list[str], "The headers of the columns in the data frame."]
    sample_rows: Annotated[list[list], "The sample rows of the data frame."]
    file_id: Annotated[str | None, "The ID of the file that the data frame is in."]
    file_ref: Annotated[str | None, "The reference of the file that the data frame is in."]


class CacheMissError(Exception):
    """Raised when a cache miss occurs."""


class _CacheMetadataSingleSheet(TypedDict):
    """
    Metadata for a single-sheet file.

    Cached under the 'metadata' key for a single sheet.
    """

    name: str
    file_id: str
    file_ref: str
    sheet_name: str
    num_rows: int
    num_columns: int
    created_at: str
    column_headers: list[str]


class _CacheMetadataMultiSheet(TypedDict):
    """
    Metadata for a multi-sheet file.

    Cached under the 'metadata' key when a multi-sheet file is inspected.
    Individual sheets are cached under the 'metadata' key based on the sheet name.
    """

    sheet_names: list[str]


class _CacheHandler:
    """
    Helper class to handle caching of data frame inspection metadata and samples.

    Expected cache structure:
    1. metadata:
        For a multi-sheet file we store just the sheet_names (_CacheMetadataMultiSheet)
        For a single-sheet file (or individual sheets in a multi-sheet file) we store
          the metadata (_CacheMetadataSingleSheet)

    2. samples_small:
        Just available for single-sheet or individual sheets in a multi-sheet file.
        We store directly 20 samples for each data frame.

    3. full_data:
        Just available for single-sheet or individual sheets in a multi-sheet file.
        We store the full data frame data from file/sheet as a bytes object in parquet format.
    """

    max_samples_in_short_samples_cache = 20

    def __init__(
        self,
        tid: str,
        storage: "BaseStorage",
        sheet_name: str | None,
        file_id: str,
    ):
        self._tid = tid
        self._storage = storage
        self._file_id = file_id
        self._cache_key_metadata = self._generate_cache_key("metadata", self._file_id, sheet_name)
        self._cached_metadata: BaseStorage.CacheValue | None = None
        self._is_multi_sheet = False

    def _generate_cache_key(
        self,
        kind: Literal["metadata", "samples_small", "full_data"],
        file_id: str,
        sheet_name: str | None,
    ) -> str:
        """Generate cache key based on the file id and sheet name."""
        s = f"df_v1,{kind}"

        if kind == "samples_small":
            s += f",max_samples:{self.max_samples_in_short_samples_cache}"

        if sheet_name:
            s += f",sheet:{sheet_name}"

        if file_id:
            s += f",file_id:{file_id}"

        return s

    async def get_cached_metadata(self) -> "BaseStorage.CacheValue | None":
        """Get the cached metadata for the file."""
        if self._cached_metadata is None:
            self._cached_metadata = await self._storage.get_cache_entry(self._cache_key_metadata)
        return self._cached_metadata

    async def create_data_frames_inspection_api_from_cache(self) -> list[_DataFrameInspectionAPI]:
        """Create a list of _DataFrameInspectionAPI objects from the cache."""
        import json

        metadata_json = await self.get_cached_metadata()
        if metadata_json is None:
            raise CacheMissError("No cached metadata found")

        metadata = json.loads(metadata_json.cache_data.decode("utf-8"))
        self._is_multi_sheet = "sheet_names" in metadata
        if self._is_multi_sheet:  # We're loading a multi-sheet file
            cache_tracking_callback(CacheHitEvent(event="multi_sheet_names"))
            multi_sheet_metadata = typing.cast(_CacheMetadataMultiSheet, metadata)
            sheet_names = multi_sheet_metadata["sheet_names"]
            ret: list[_DataFrameInspectionAPI] = []

            cache_keys_from_sheet_name: list[str] = []
            sheet_name_to_cache_key: dict[str, str] = {}
            for sheet_name in sheet_names:
                cache_key_sheet_metadata = self._generate_cache_key("metadata", self._file_id, sheet_name)
                cache_keys_from_sheet_name.append(cache_key_sheet_metadata)
                sheet_name_to_cache_key[sheet_name] = cache_key_sheet_metadata

            cached_entries = await self._storage.get_cache_entries(cache_keys_from_sheet_name)

            if len(cached_entries) != len(sheet_names):
                raise CacheMissError("Some cached metadata entries are missing")

            for sheet_name in sheet_names:
                cache_key = sheet_name_to_cache_key[sheet_name]
                cached_entry = cached_entries[cache_key]
                metadata_json = json.loads(cached_entry.cache_data.decode("utf-8"))
                single_sheet_metadata = typing.cast(_CacheMetadataSingleSheet, metadata_json)
                value = _DataFrameInspectionAPI(
                    thread_id=self._tid,
                    name=single_sheet_metadata["name"],
                    file_id=single_sheet_metadata["file_id"],
                    file_ref=single_sheet_metadata["file_ref"],
                    sheet_name=single_sheet_metadata["sheet_name"],
                    num_rows=single_sheet_metadata["num_rows"],
                    num_columns=single_sheet_metadata["num_columns"],
                    created_at=datetime.datetime.fromisoformat(single_sheet_metadata["created_at"]),
                    column_headers=single_sheet_metadata["column_headers"],
                    sample_rows=[],
                )
                ret.append(value)
            cache_tracking_callback(
                CacheHitEvent(
                    event="multi_sheet",
                    description=f"{len(ret)} data frames",
                )
            )
            return ret
        else:
            # If there's no sheet_names, this is not a multi-sheet cached entry (and thus)
            # the metadata should contain the info for the single sheet.
            single_sheet_metadata = typing.cast(_CacheMetadataSingleSheet, metadata)
            ret: list[_DataFrameInspectionAPI] = [
                _DataFrameInspectionAPI(
                    thread_id=self._tid,
                    name=single_sheet_metadata["name"],
                    file_id=single_sheet_metadata["file_id"],
                    file_ref=single_sheet_metadata["file_ref"],
                    sheet_name=single_sheet_metadata["sheet_name"],
                    num_rows=single_sheet_metadata["num_rows"],
                    num_columns=single_sheet_metadata["num_columns"],
                    created_at=datetime.datetime.fromisoformat(single_sheet_metadata["created_at"]),
                    column_headers=single_sheet_metadata["column_headers"],
                    sample_rows=[],
                )
            ]
            cache_tracking_callback(CacheHitEvent(event="single_sheet", description="1 data frame"))
            return ret

    @dataclasses.dataclass
    class _LoadedFromCache:
        cache_hit: Annotated[
            list[_DataFrameInspectionAPI],
            "Data frames which were successfully sampled from the cache.",
        ]
        cache_miss: Annotated[
            list[_DataFrameInspectionAPI],
            "Data frames which we were not able to sample from the cache.",
        ]

    async def load_samples_from_sample_rows_cache(
        self,
        data_frames: list[_DataFrameInspectionAPI],
        num_samples: int,
    ) -> _LoadedFromCache:
        """Load the samples from the samples rows cache."""
        import json

        ret = self._LoadedFromCache(cache_hit=[], cache_miss=[])
        for data_frame in data_frames:
            cache_key_samples = self._generate_cache_key("samples_small", self._file_id, data_frame.sheet_name)
            cached_entry = await self._storage.get_cache_entry(cache_key_samples)
            if cached_entry is None:
                ret.cache_miss.append(data_frame)
            else:
                sample_rows = json.loads(cached_entry.cache_data.decode("utf-8"))
                data_frame.sample_rows = sample_rows[:num_samples]
                ret.cache_hit.append(data_frame)
                logger.info(
                    f"Loaded {len(data_frame.sample_rows)} samples from samples cache for data frame {data_frame.name}"
                )
                cache_tracking_callback(CacheHitEvent(event="samples_small"))
        return ret

    async def load_samples_from_full_data_cache(
        self,
        data_frames: list[_DataFrameInspectionAPI],
        num_samples: int,
    ) -> _LoadedFromCache:
        """Load the samples from the full data cache."""
        from agent_platform.server.data_frames.data_node import ParquetHandler

        ret = self._LoadedFromCache(cache_hit=[], cache_miss=[])
        for data_frame in data_frames:
            cache_key_full_data = self._generate_cache_key("full_data", self._file_id, data_frame.sheet_name)
            cached_entry = await self._storage.get_cache_entry(cache_key_full_data)
            if cached_entry is None:
                ret.cache_miss.append(data_frame)
            else:
                # The data is a parquet binary file, load it into a ParquetHandler
                parquet_handler = ParquetHandler(cached_entry.cache_data)
                data_frame.sample_rows = parquet_handler.list_sample_rows(num_samples)
                ret.cache_hit.append(data_frame)
                logger.info(
                    f"Loaded {len(data_frame.sample_rows)} samples from full data cache for "
                    f"data frame {data_frame.name}"
                )
                cache_tracking_callback(CacheHitEvent(event="full_data"))
        return ret

    async def load_samples_from_cache(
        self, found_in_cache: list[_DataFrameInspectionAPI], num_samples: int
    ) -> _LoadedFromCache:
        if num_samples > 0 and num_samples <= self.max_samples_in_short_samples_cache:
            # we can load from the samples cache
            loaded = await self.load_samples_from_sample_rows_cache(found_in_cache, num_samples)
            if loaded.cache_miss:
                # We haven't been able to load all samples from the samples cache
                # try to load from the full data
                loaded_full = await self.load_samples_from_full_data_cache(loaded.cache_miss, num_samples)
                loaded.cache_hit.extend(loaded_full.cache_hit)
                loaded.cache_miss = loaded_full.cache_miss

        elif num_samples == -1 or num_samples > self.max_samples_in_short_samples_cache:
            # We have to load from the full data (we just cache up to 10 samples separately)
            loaded = await self.load_samples_from_full_data_cache(found_in_cache, num_samples)

        else:
            raise RuntimeError(
                f"Invalid number of samples: {num_samples} (should not get here as it's validated above)"
            )

        return loaded

    async def cache_full_data(
        self,
        data_frame: _DataFrameInspectionAPI,
        full_data: "pyarrow.Table",
        time_to_compute_data_in_seconds: float,
    ):
        """Cache the full and sample data."""
        from agent_platform.server.data_frames.data_node import convert_pyarrow_slice_to_parquet

        as_parquet = convert_pyarrow_slice_to_parquet(full_data, None, None, None, None)
        await self._storage.set_cache_entry(
            self._generate_cache_key("full_data", self._file_id, data_frame.sheet_name),
            as_parquet,
            time_to_compute_data_in_seconds=time_to_compute_data_in_seconds,
        )

    async def cache_sample_data(
        self,
        data_frame: _DataFrameInspectionAPI,
        sampled: "list[Row]",
        time_to_compute_data_in_seconds: float,
    ):
        """Cache the sample data."""
        import json

        await self._storage.set_cache_entry(
            self._generate_cache_key("samples_small", self._file_id, data_frame.sheet_name),
            json.dumps(sampled).encode("utf-8"),
            time_to_compute_data_in_seconds=time_to_compute_data_in_seconds,
        )

    async def cache_multiple_sheet_names(self, sheet_names: list[str], time_to_compute_data_in_seconds: float):
        import json

        await self._storage.set_cache_entry(
            self._generate_cache_key("metadata", self._file_id, None),
            json.dumps({"sheet_names": sheet_names}).encode("utf-8"),
            time_to_compute_data_in_seconds=time_to_compute_data_in_seconds,
        )

    async def cache_metadata(self, data_frame: _DataFrameInspectionAPI, time_to_compute_data_in_seconds: float):
        import json

        value = {
            "name": data_frame.name,
            "file_id": data_frame.file_id,
            "file_ref": data_frame.file_ref,
            "sheet_name": data_frame.sheet_name,
            "num_rows": data_frame.num_rows,
            "num_columns": data_frame.num_columns,
            "created_at": data_frame.created_at.isoformat(),
            "column_headers": data_frame.column_headers,
        }

        await self._storage.set_cache_entry(
            self._generate_cache_key("metadata", self._file_id, data_frame.sheet_name),
            json.dumps(value).encode("utf-8"),
            time_to_compute_data_in_seconds=time_to_compute_data_in_seconds,
        )


# Helper callback to track cache hits (used for testing)
cache_tracking_callback = Callback()


@dataclasses.dataclass(slots=True)
class CacheHitEvent:
    event: Literal["single_sheet", "multi_sheet", "multi_sheet_names", "samples_small", "full_data"]
    event_type: Literal["cache_hit"] = "cache_hit"
    description: str | None = None

    def __str__(self):
        ret = f"{self.event_type}: {self.event}"
        if self.description:
            ret += f" - {self.description}"
        return ret


class InspectFileAsDataFrame:
    _data_reader: "FileDataReader | None" = None
    _cache_handler: "_CacheHandler | None" = None

    def __init__(
        self,
        user: AuthedUser,
        tid: str,
        storage: StorageDependency,
        num_samples: int,
        sheet_name: str | None,
        file_metadata: "UploadedFile",
    ):
        self._user = user
        self._tid = tid
        self._storage = storage
        self._num_samples = num_samples
        self._sheet_name = sheet_name
        self._file_metadata = file_metadata

    @property
    def num_samples(self) -> int:
        return self._num_samples

    @num_samples.setter
    def num_samples(self, value: int):
        self._num_samples = value

    def get_cache_handler(self) -> _CacheHandler:
        if self._cache_handler is None:
            self._cache_handler = _CacheHandler(self._tid, self._storage, self._sheet_name, self._file_metadata.file_id)
        return self._cache_handler

    async def inspect_from_cache(
        self,
    ) -> _CacheHandler._LoadedFromCache | list[_DataFrameInspectionAPI] | None:
        loaded: _CacheHandler._LoadedFromCache | None = None

        try:
            cache_handler = self.get_cache_handler()
            found_in_cache: list[_DataFrameInspectionAPI] = []
            found_in_cache = await cache_handler.create_data_frames_inspection_api_from_cache()
            num_samples = self._num_samples

            if num_samples == 0:
                # We're good to go, no samples to load, full cache hit.
                return found_in_cache

            loaded = await cache_handler.load_samples_from_cache(found_in_cache, num_samples)
            if not loaded.cache_miss:
                # Ok, all matched from the cache.
                return loaded.cache_hit
            return loaded
        except CacheMissError:
            pass
        except Exception as e:
            logger.critical(f"Failed to get cached data: {e}", exc_info=True)

        return None

    async def get_data_reader(self) -> "FileDataReader":
        from agent_platform.server.data_frames.data_reader import (
            create_file_data_reader,
        )

        if self._data_reader is None:
            self._data_reader = await create_file_data_reader(
                user=self._user,
                tid=self._tid,
                storage=self._storage,
                sheet_name=self._sheet_name,
                file_metadata=self._file_metadata,
            )
        return self._data_reader

    async def inspect_and_cache_from_file(self) -> list[_DataFrameInspectionAPI]:
        import time

        from agent_platform.server.data_frames.data_node import (
            convert_pyarrow_slice_to_list_of_rows,
        )

        cache_handler = self.get_cache_handler()
        start_time = time.monotonic()

        data_reader: FileDataReader = await self.get_data_reader()

        ret: list[_DataFrameInspectionAPI] = []

        all_sheets = list(data_reader.iter_sheets())

        if len(all_sheets) > 1:
            await cache_handler.cache_multiple_sheet_names(
                [(sheet.name or "<unnamed-sheet>") for sheet in all_sheets],
                start_time - time.monotonic(),
            )

        num_samples = self._num_samples

        for sheet in all_sheets:
            value = _DataFrameInspectionAPI(
                thread_id=self._tid,
                name=self._file_metadata.file_ref,
                file_id=self._file_metadata.file_id,
                file_ref=self._file_metadata.file_ref,
                sheet_name=sheet.name,
                num_rows=sheet.num_rows,
                num_columns=sheet.num_columns,
                created_at=datetime.datetime.now(),
                column_headers=sheet.column_headers,
                sample_rows=[],
            )

            await cache_handler.cache_metadata(value, start_time - time.monotonic())

            if num_samples == 0:
                sample_rows = []

            # i.e.: if we want all samples or if if the number of samples required is greater
            # than the amount of samples stored in the "short samples" cache we load
            # the full data and cache both the full data as well as the short samples data.
            elif num_samples == -1 or (num_samples > cache_handler.max_samples_in_short_samples_cache):
                full_data: pyarrow.Table = sheet.to_ibis()
                sample_rows: list[Row] = convert_pyarrow_slice_to_list_of_rows(full_data, None, None, None, None)
                # Cache the full data and the sample data
                await cache_handler.cache_full_data(value, full_data, start_time - time.monotonic())
                sampled_to_cache = sample_rows[: cache_handler.max_samples_in_short_samples_cache]
                await cache_handler.cache_sample_data(value, sampled_to_cache, start_time - time.monotonic())

                if num_samples != -1:
                    sample_rows = sample_rows[:num_samples]

            else:
                assert num_samples > 0, "num_samples must be 0, -1 or a positive number"

                sample_rows = sheet.list_sample_rows(num_samples)

                # Cache 10 rows
                sampled_to_cache = sample_rows[: cache_handler.max_samples_in_short_samples_cache]
                await cache_handler.cache_sample_data(value, sampled_to_cache, start_time - time.monotonic())

            value.sample_rows = sample_rows

            ret.append(value)

        return ret


@router.get("/{tid}/inspect-file-as-data-frame")
async def inspect_file_as_data_frame(
    user: AuthedUser,
    tid: str,
    storage: StorageDependency,
    num_samples: Annotated[
        int,
        """The number of samples to return for each data frame.

        If 0, no samples are returned.
        If -1, all samples are returned.
        If a positive number, return up to that number of samples.
        """,
    ] = 0,
    sheet_name: Annotated[
        str | None,
        """The name of the sheet to inspect. If not given and a multi-sheet
        file is given, all sheets are inspected.""",
    ] = None,
    file_id: Annotated[
        str | None,
        """The ID of the file to inspect (when used, file_ref is not needed).""",
    ] = None,
    file_ref: Annotated[
        str | None,
        """The reference of the file (usually the file name) to inspect
        (when used, file_id is not needed).""",
    ] = None,
) -> list[_DataFrameInspectionAPI]:
    """Inspect a file as a data frame.

    Note: may return multiple data frames if the file is a multi-sheet excel file."""

    from agent_platform.core.files.mime_types import TABULAR_DATA_MIME_TYPES
    from agent_platform.server.data_frames.data_reader import (
        get_file_metadata,
    )

    if num_samples < -1:
        raise PlatformHTTPError(
            error_code=ErrorCode.BAD_REQUEST,
            message="num_samples must be 0, -1 or a positive number",
        )

    # Get the file metadata to make sure the file exists and the user has access to it.
    file_metadata = await get_file_metadata(user.user_id, tid, storage, file_id=file_id, file_ref=file_ref)

    inspector = InspectFileAsDataFrame(user, tid, storage, num_samples, sheet_name, file_metadata)

    try:
        # Try to get from cache first if we should/can use the cache
        loaded: _CacheHandler._LoadedFromCache | list[_DataFrameInspectionAPI] | None
        loaded = await inspector.inspect_from_cache()

        if isinstance(loaded, list):
            return loaded

        # If we get here, the cache wasn't hit... for simplicity we're
        # reading all the data from the file again for now.
        return await inspector.inspect_and_cache_from_file()
    except Exception as e:
        if isinstance(file_metadata.mime_type, str) and file_metadata.mime_type not in TABULAR_DATA_MIME_TYPES:
            raise PlatformDataFrameWrongMimeTypeError(file_metadata.mime_type) from e

        raise


@dataclasses.dataclass
class _DataFrameCreationAPI:
    data_frame_id: Annotated[str, "The ID of the data frame."]
    thread_id: Annotated[str, "The ID of the thread that the data frame is in."]
    name: Annotated[str, "The name of the data frame."]
    sheet_name: Annotated[
        str | None,
        """The name of the sheet that the data frame is in (None if not applicable, i.e.:
        if the data frame is a .csv, not excel).""",
    ]
    description: Annotated[str | None, "The description for the data frame."]
    num_rows: Annotated[int, "The number of rows in the data frame."]
    num_columns: Annotated[int, "The number of columns in the data frame."]
    created_at: Annotated[datetime.datetime, "The date and time the data frame was created."]
    column_headers: Annotated[list[str], "The headers of the columns in the data frame."]
    sample_rows: Annotated[list[list], "The sample rows of the data frame."]
    input_id_type: Annotated[
        Literal["file", "sql_computation", "in_memory"],
        "The type of the input ID.",
    ]
    parent_data_frame_ids: Annotated[
        list[str] | None,
        """The IDs of the data frames that were used to create the data frame (None if not
        applicable).""",
    ]
    file_id: Annotated[
        str | None,
        "The ID of the file that the data frame is in (only available if input_id_type is 'file').",
    ]
    file_ref: Annotated[
        str | None,
        """The reference of the file that the data frame is in (only available if input_id_type
        is 'file').""",
    ]
    sql_dialect: Annotated[
        str | None,
        """The dialect of the SQL query that was used to create the data frame (only available
        if input_id_type is 'sql_computation').""",
    ]
    sql_query: Annotated[
        str | None,
        """The SQL query that was used to create the data frame (only available if input_id_type
        is 'sql_computation').""",
    ]


class PlatformDataFrameWrongMimeTypeError(PlatformHTTPError):
    def __init__(self, mime_type: str):
        super().__init__(
            error_code=ErrorCode.BAD_REQUEST,
            message=f"""
            It is not possilbe to create data frames from files with the mime type {mime_type!r}.
            Only files with tabular data (e.g. .csv, .xlsx, .xls) can be used to create data frames.
            Please use a different tool to extract information from this file.
            """,
        )


@router.post("/{tid}/data-frames/from-file")
async def create_data_frame_from_file(
    user: AuthedUser,
    tid: str,
    storage: StorageDependency,
    num_samples: Annotated[
        int,
        """The number of samples to return for each data frame.

        If 0, no samples are returned.
        If -1, all samples are returned.
        If a positive number, return up to that number of samples.
        """,
    ] = 0,
    sheet_name: Annotated[
        str | None,
        """The name of the sheet to inspect. If not given and a multi-sheet
        file is given, an error is raised.""",
    ] = None,
    description: Annotated[str | None, "The description for the data frame."] = None,
    name: Annotated[str | None, "The name for the data frame."] = None,
    file_id: Annotated[
        str | None,
        """The ID of the file to create the data frame from (when used, file_ref is not needed).""",
    ] = None,
    file_ref: Annotated[
        str | None,
        """The reference of the file (usually the file name) to create the data frame from
        (when used, file_id is not needed).""",
    ] = None,
) -> _DataFrameCreationAPI:
    """Create a data frame from a file.

    Note: if the file is a multi-sheet excel file, this needs to be called for each sheet
    by specifying the sheet_name.
    """

    from agent_platform.core.data_frames.data_frames import DATAFRAMES_LLM_SAMPLE_ROWS_LIMIT
    from agent_platform.server.storage.base import BaseStorage

    if num_samples < 0:
        use_num_samples = num_samples
    else:
        use_num_samples = max(num_samples, DATAFRAMES_LLM_SAMPLE_ROWS_LIMIT)

    inspected_data_frames = await inspect_file_as_data_frame(
        user, tid, storage, use_num_samples, sheet_name, file_id=file_id, file_ref=file_ref
    )
    if len(inspected_data_frames) == 0:
        raise PlatformHTTPError(
            error_code=ErrorCode.BAD_REQUEST,
            message="No data frames found in file",
        )

    if len(inspected_data_frames) > 1:
        found_sheet_names = [inspected_data_frame.sheet_name for inspected_data_frame in inspected_data_frames]
        raise PlatformHTTPError(
            error_code=ErrorCode.BAD_REQUEST,
            message="Multiple data frames found in file. Please specify sheet_name. "
            f"Available sheet names: {found_sheet_names!r}.",
        )

    inspected_data_frame = inspected_data_frames[0]
    return await create_data_frame_from_inspected_data_frame(
        user, tid, typing.cast(BaseStorage, storage), inspected_data_frame, name, description
    )


async def create_data_frame_from_inspected_data_frame(
    user: AuthedUser,
    tid: str,
    storage: "BaseStorage",
    inspected_data_frame: _DataFrameInspectionAPI,
    name: str | None = None,
    description: str | None = None,
) -> _DataFrameCreationAPI:
    """
    Note: the inspected_data_frame must have been sampled with num_samples of
    `DATAFRAMES_LLM_SAMPLE_ROWS_LIMIT` or more.
    """
    import keyword
    import os.path
    import uuid

    from agent_platform.core.data_frames.data_frames import (
        DATAFRAMES_LLM_SAMPLE_ROWS_LIMIT,
        PlatformDataFrame,
    )
    from sema4ai.common.text import slugify

    # Get the thread to find the agent_id
    thread = await storage.get_thread(user.user_id, tid)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    use_name = name
    if not use_name:
        # Try to generate a name from the file name / sheet name.
        ref = os.path.basename(inspected_data_frame.name)
        ref = os.path.splitext(ref)[0]

        use_name = slugify(ref).replace("-", "_")
        if inspected_data_frame.sheet_name:
            sheet_name_as_slug = slugify(inspected_data_frame.sheet_name).replace("-", "_")
            use_name = f"{use_name}_{sheet_name_as_slug}"

        if not use_name.isidentifier() or keyword.iskeyword(use_name):
            use_name = f"data_{use_name}"  # first char may be digit or it's a keyword.

        if not use_name.isidentifier() or keyword.iskeyword(use_name):
            # Still not valid, let's raise an error.
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST,
                message=(
                    "It was not possible to generate a valid name for the data frame. "
                    f"Please provide one as a parameter to the request (auto-generated name: "
                    f"{use_name!r})."
                ),
            )

    sql_dialect = "duckdb"  # For files, duckdb is the backing engine

    data_frame = PlatformDataFrame(
        data_frame_id=str(uuid.uuid4()),
        user_id=user.user_id,
        agent_id=thread.agent_id,
        thread_id=tid,
        sheet_name=inspected_data_frame.sheet_name,
        num_rows=inspected_data_frame.num_rows,
        num_columns=inspected_data_frame.num_columns,
        column_headers=inspected_data_frame.column_headers,
        name=use_name,
        input_id_type="file",
        created_at=datetime.datetime.now(datetime.UTC),
        computation_input_sources={},
        file_id=inspected_data_frame.file_id,
        file_ref=inspected_data_frame.file_ref,
        description=description,
        computation=None,
        # we could save the data as parquet, but for now, let's experiment in always
        # rebuilding the full data whenever asked.
        parquet_contents=None,
        extra_data=PlatformDataFrame.build_extra_data(
            sample_rows=inspected_data_frame.sample_rows[:DATAFRAMES_LLM_SAMPLE_ROWS_LIMIT],
            sql_dialect=sql_dialect,
        ),
    )

    await storage.save_data_frame(data_frame)

    return _DataFrameCreationAPI(
        data_frame_id=data_frame.data_frame_id,
        thread_id=data_frame.thread_id,
        name=data_frame.name,
        sheet_name=data_frame.sheet_name,
        description=data_frame.description,
        num_rows=data_frame.num_rows,
        num_columns=data_frame.num_columns,
        created_at=data_frame.created_at,
        column_headers=data_frame.column_headers,
        sample_rows=inspected_data_frame.sample_rows,
        file_id=data_frame.file_id,
        file_ref=data_frame.file_ref,
        input_id_type="file",
        parent_data_frame_ids=None,
        sql_dialect=sql_dialect,
        sql_query=None,
    )


@dataclasses.dataclass
class _DataFrameFromJsonPayload:
    json_data: Annotated[dict, "The JSON data to convert to a DataFrame."]
    jq_expression: Annotated[
        str | None,
        "JQ expression to transform/select the JSON data into tabular format. "
        "If not provided, the JSON data is used as is.",
    ] = None
    name: Annotated[str | None, "The name for the data frame."] = None
    description: Annotated[str | None, "The description for the data frame."] = None


def _generate_data_frame_name(provided_name: str | None) -> str:
    """Generate a valid data frame name from the provided name or create a default one."""
    import keyword
    import uuid

    from sema4ai.common.text import slugify

    if not provided_name:
        return f"data_frame_{str(uuid.uuid4())[:8]}"

    use_name = slugify(provided_name).replace("-", "_")
    if not use_name.isidentifier() or keyword.iskeyword(use_name):
        use_name = f"data_{use_name}"

    if not use_name.isidentifier() or keyword.iskeyword(use_name):
        raise PlatformHTTPError(
            error_code=ErrorCode.BAD_REQUEST,
            message=(
                "It was not possible to generate a valid name for the data frame. "
                f"Please provide a valid Python identifier (provided name: {provided_name!r}, "
                f"auto-generated name: {use_name!r})."
            ),
        )

    return use_name


def _convert_jq_result_to_columns_rows(
    transformed_data: dict | list,
) -> tuple[list[str], list[list]]:
    """Convert JQ transformation result to columns and rows format.

    Raises:
        ValueError: If the transformed data is not in the expected format.
    """
    from agent_platform.server.kernel.data_frames import _clean_value_for_json

    if isinstance(transformed_data, dict):
        # Single object - one row
        columns = list(transformed_data.keys())
        rows = [[_clean_value_for_json(transformed_data[col]) for col in columns]]
        return columns, rows
    elif isinstance(transformed_data, list):
        if not transformed_data:
            raise ValueError("JQ expression returned empty array")
        if not all(isinstance(item, dict) for item in transformed_data):
            raise ValueError("JQ expression must return object(s), not primitive values")

        dict_list = typing.cast(list[dict], transformed_data)
        columns = []
        for item in dict_list:
            for key in item.keys():
                if key not in columns:
                    columns.append(key)

        rows = []
        for item in dict_list:
            row = [_clean_value_for_json(item.get(col)) for col in columns]
            rows.append(row)
        return columns, rows
    else:
        raise ValueError("JQ expression must return an object or array of objects")


async def _verify_thread_access(base_storage: "BaseStorage", user_id: str, tid: str) -> "Thread":
    """Verify that the user has access to the thread and return the thread."""
    return await base_storage.get_thread(user_id, tid)


@router.post("/{tid}/data-frames/from-json")
async def create_data_frame_from_json(
    payload: _DataFrameFromJsonPayload,
    user: AuthedUser,
    tid: str,
    storage: StorageDependency,
    num_samples: Annotated[
        int,
        """The number of samples to return for each data frame.

        If 0, no samples are returned.
        If -1, all samples are returned.
        If a positive number, return up to that number of samples.
        """,
    ] = 0,
) -> _DataFrameCreationAPI:
    """Create a data frame from JSON data using a JQ expression.

    This endpoint accepts JSON data and a JQ expression that transforms/selects
    the data into tabular format. The JQ expression determines what becomes rows and columns.
    """
    from agent_platform.orchestrator._jq_transform import apply_jq_transform

    from agent_platform.core.data_frames.data_frames import DATAFRAMES_LLM_SAMPLE_ROWS_LIMIT
    from agent_platform.server.kernel.data_frames import create_data_frame_from_columns_and_rows
    from agent_platform.server.storage.base import BaseStorage

    base_storage = typing.cast(BaseStorage, storage)

    # Get the thread to find the agent_id
    thread = await _verify_thread_access(base_storage, user.user_id, tid)

    # Apply JQ transformation
    if payload.jq_expression is None:
        transformed_data = payload.json_data
    else:
        try:
            transformed_data = apply_jq_transform(payload.json_data, payload.jq_expression)
        except Exception as e:
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST, message=f"Error applying JQ expression: {e!s}"
            ) from e

    # Validate that transformed_data is dict or list (not a scalar)
    if not isinstance(transformed_data, dict | list):
        raise PlatformHTTPError(
            error_code=ErrorCode.BAD_REQUEST,
            message=(
                f"JQ expression must return an object or array to convert into a data frame, "
                f"got {type(transformed_data).__name__}"
            ),
        )

    try:
        columns, rows = _convert_jq_result_to_columns_rows(transformed_data)
    except ValueError as e:
        raise PlatformHTTPError(error_code=ErrorCode.BAD_REQUEST, message=str(e)) from e

    # Create the data frame
    if num_samples < 0:
        use_num_samples = num_samples
    else:
        use_num_samples = max(num_samples, DATAFRAMES_LLM_SAMPLE_ROWS_LIMIT)

    data_frame_name = payload.name or _generate_data_frame_name(payload.name)

    data_frame = await create_data_frame_from_columns_and_rows(
        columns=columns,
        rows=rows,
        name=data_frame_name,
        user_id=user.user_id,
        agent_id=thread.agent_id,
        thread_id=tid,
        storage=base_storage,
        description=payload.description,
        input_id_type="in_memory",
        num_sample_rows=use_num_samples,
    )

    # Get sample rows to return
    if use_num_samples == -1:
        sample_rows = rows
    elif use_num_samples > 0:
        sample_rows = rows[:use_num_samples]
    else:
        sample_rows = []

    return _DataFrameCreationAPI(
        data_frame_id=data_frame.data_frame_id,
        thread_id=data_frame.thread_id,
        name=data_frame.name,
        sheet_name=None,
        description=data_frame.description,
        num_rows=data_frame.num_rows,
        num_columns=data_frame.num_columns,
        created_at=data_frame.created_at,
        column_headers=data_frame.column_headers,
        sample_rows=sample_rows,
        file_id=None,
        file_ref=None,
        input_id_type="in_memory",
        parent_data_frame_ids=None,
        sql_dialect=None,
        sql_query=None,
    )


@router.get("/{tid}/data-frames")
async def get_thread_data_frames(
    user: AuthedUser,
    tid: str,
    storage: StorageDependency,
    num_samples: int = 0,
) -> list[_DataFrameCreationAPI]:
    """Get a list of data frames for a thread.

    Args:
        user: The user making the request.
        tid: The ID of the thread to get data frames for.
        storage: The storage to use to get the data frames.
        num_samples: The number of samples to return for each data frame.
            If 0, no samples are returned.
            If -1, all samples are returned.
            If a positive number, return up to that number of samples.

    Returns:
        A list of data frames created in the thread.
    """
    import time

    from agent_platform.core.data_frames.data_frames import PlatformDataFrame
    from agent_platform.server.data_frames.data_frames_kernel import DataFramesKernel
    from agent_platform.server.storage.base import BaseStorage

    base_storage = typing.cast(BaseStorage, storage)
    await _verify_thread_access(base_storage, user.user_id, tid)

    data_frames: list[PlatformDataFrame] = await base_storage.list_data_frames(tid)
    ret: list[_DataFrameCreationAPI] = []
    for data_frame in data_frames:
        data_frame_api = _DataFrameCreationAPI(
            data_frame_id=data_frame.data_frame_id,
            thread_id=data_frame.thread_id,
            name=data_frame.name,
            sheet_name=data_frame.sheet_name,
            description=data_frame.description,
            num_rows=data_frame.num_rows,
            num_columns=data_frame.num_columns,
            created_at=data_frame.created_at,
            column_headers=data_frame.column_headers,
            sample_rows=[],  # It'll be loaded later if needed
            file_id=data_frame.file_id,
            file_ref=data_frame.file_ref,
            input_id_type=data_frame.input_id_type,
            parent_data_frame_ids=list(data_frame.computation_input_sources.keys()),
            sql_dialect=data_frame.sql_dialect,
            sql_query=data_frame.computation if data_frame.input_id_type == "sql_computation" else None,
        )

        if num_samples != 0:
            initial_time = time.monotonic()
            data_frames_kernel = DataFramesKernel(base_storage, user, tid)
            resolved_df = await data_frames_kernel.resolve_data_frame(data_frame)
            data_frame_api.sample_rows = await resolved_df.list_sample_rows(num_samples)
            logger.info(
                f"Listed {num_samples} samples for data frame {data_frame.name} in "
                f"{time.monotonic() - initial_time:.2f} seconds"
            )
        ret.append(data_frame_api)
    return ret


@dataclasses.dataclass
class _DataFrameComputationPayload:
    new_data_frame_name: Annotated[str, "The name for the new data frame."]
    sql_query: Annotated[str, "The SQL query to execute."]
    description: Annotated[str | None, "Optional description for the new data frame."] = None
    sql_dialect: Annotated[
        str | None,
        "The dialect of the SQL query to use (default is computing based on dependencies).",
    ] = None
    semantic_data_model_name: Annotated[
        str | None,
        "The name of the semantic data model used to generate the SQL query.",
    ] = None


@router.post("/{tid}/data-frames/from-computation")
async def create_data_frame_from_sql_computation(
    payload: _DataFrameComputationPayload,
    user: AuthedUser,
    tid: str,
    storage: StorageDependency,
    num_samples: Annotated[
        int,
        """The number of samples to return for each data frame.

        If 0, no samples are returned.
        If -1, all samples are returned.
        If a positive number, return up to that number of samples.
        """,
    ] = 0,
) -> _DataFrameCreationAPI:
    """Create a new data frame from existing data frames using a SQL computation.

    Args:
        payload: The computation payload containing name, SQL query, and input data frames
        user: The user making the request
        tid: The ID of the thread
        storage: The storage to use

    Returns:
        The created data frame information
    """
    from agent_platform.server.data_frames.data_frames_from_computation import (
        create_data_frame_from_sql_computation_api,
    )
    from agent_platform.server.data_frames.data_frames_kernel import DataFramesKernel
    from agent_platform.server.storage.base import BaseStorage

    base_storage = typing.cast(BaseStorage, storage)
    await _verify_thread_access(base_storage, user.user_id, tid)

    data_frames_kernel = DataFramesKernel(base_storage, user, tid)

    resolved_df, samples_table = await create_data_frame_from_sql_computation_api(
        data_frames_kernel=data_frames_kernel,
        storage=base_storage,
        new_data_frame_name=payload.new_data_frame_name,
        sql_query=payload.sql_query,
        dialect=payload.sql_dialect,
        description=payload.description,
        num_samples=num_samples,
        semantic_data_model_name=payload.semantic_data_model_name,
    )

    platform_data_frame = resolved_df.platform_data_frame

    return _DataFrameCreationAPI(
        data_frame_id=platform_data_frame.data_frame_id,
        thread_id=platform_data_frame.thread_id,
        name=platform_data_frame.name,
        sheet_name=platform_data_frame.sheet_name,
        description=platform_data_frame.description,
        num_rows=platform_data_frame.num_rows,
        num_columns=platform_data_frame.num_columns,
        created_at=platform_data_frame.created_at,
        column_headers=platform_data_frame.column_headers,
        sample_rows=samples_table.rows,
        file_id=platform_data_frame.file_id,
        file_ref=platform_data_frame.file_ref,
        input_id_type="sql_computation",
        parent_data_frame_ids=list(platform_data_frame.computation_input_sources.keys()),
        sql_dialect=platform_data_frame.sql_dialect,
        sql_query=platform_data_frame.computation if platform_data_frame.input_id_type == "sql_computation" else None,
    )


class _SliceDataInput(BaseModel):
    data_frame_id: Annotated[
        str | None, "The ID of the data frame to slice (mutually exclusive with data_frame_name)."
    ] = None
    data_frame_name: Annotated[
        str | None, "The name of the data frame to slice (mutually exclusive with data_frame_id)."
    ] = None
    offset: Annotated[int, "From which offset to start the slice (starts at 0)."] = 0
    limit: Annotated[int | None, "The maximum number of rows to return in the slice."] = None
    column_names: Annotated[list[str] | None, "The column names to include."] = None
    output_format: Annotated[Literal["json", "parquet"], "The output format."] = "json"
    order_by: Annotated[
        str | None,
        "The column name to order by (use '-' prefix to order by descending order).",
    ] = None


@router.get("/{tid}/data-frames/{data_frame_name}")
async def get_data_frame(
    user: AuthedUser,
    tid: str,
    data_frame_name: str,
    storage: StorageDependency,
    offset: Annotated[int, "From which offset to get the data frame rows (starts at 0)."] = 0,
    limit: Annotated[int | None, "The maximum number of rows to return."] = None,
    column_names: Annotated[
        str | None,
        """Comma-separated list of column names to include
        (if not provided, all columns are included).""",
    ] = None,
    output_format: Annotated[Literal["json", "parquet"], "The output format."] = "json",
    order_by: Annotated[
        str | None,
        "The column name to order by (use '-' prefix to order by descending order).",
    ] = None,
) -> Response:
    """Get a data frame's contents with optional slicing and filtering.

    Args:
        user: The user making the request
        tid: The ID of the thread
        data_frame_name: The name of the data frame to retrieve
        storage: The storage to use

    Returns:
        A response with the data frame contents in the specified format
    """
    return await slice_data_frame(
        user,
        tid,
        storage,
        _SliceDataInput(
            data_frame_id=None,
            data_frame_name=data_frame_name,
            offset=offset,
            limit=limit,
            column_names=[col.strip() for col in column_names.split(",")] if column_names else None,
            output_format=output_format,
            order_by=order_by,
        ),
    )


@router.post("/{tid}/data-frames/slice")
async def slice_data_frame(
    user: AuthedUser,
    tid: str,
    storage: StorageDependency,
    payload: _SliceDataInput,
) -> Response:
    """Get a slice of a data frame's contents.

    Args:
        user: The user making the request
        tid: The ID of the thread
        storage: The storage to use
        payload: The payload containing the data frame id or name, offset, limit,
                 column names, output format, and order by.

    Returns:
        A streaming response with the sliced data in the specified format
    """
    import time

    from agent_platform.server.data_frames.data_frames_kernel import DataFramesKernel
    from agent_platform.server.storage.base import BaseStorage

    initial_time = time.monotonic()
    logger.info(f"Starting slice_data_frame for {payload.data_frame_name or payload.data_frame_id} in thread {tid}")

    # Validate that exactly one of data_frame_id or data_frame_name is provided
    if payload.data_frame_id is None and payload.data_frame_name is None:
        raise PlatformHTTPError(
            error_code=ErrorCode.BAD_REQUEST,
            message="Either data_frame_id or data_frame_name must be provided",
        )

    if payload.data_frame_id is not None and payload.data_frame_name is not None:
        raise PlatformHTTPError(
            error_code=ErrorCode.BAD_REQUEST,
            message="Only one of data_frame_id or data_frame_name can be provided",
        )

    base_storage = typing.cast(BaseStorage, storage)
    await _verify_thread_access(base_storage, user.user_id, tid)

    data_frames_kernel = DataFramesKernel(base_storage, user, tid)

    # Find the data frame
    data_frame = None
    if payload.data_frame_id is not None:
        # Get by ID
        data_frame = await base_storage.get_data_frame(thread_id=tid, data_frame_id=payload.data_frame_id)
    else:
        # Get by name
        data_frame = await base_storage.get_data_frame(thread_id=tid, data_frame_name=payload.data_frame_name)

    try:
        # Resolve the data frame
        resolved_df = await data_frames_kernel.resolve_data_frame(data_frame)

        # Get the sliced data
        sliced_data = await resolved_df.slice(
            offset=payload.offset,
            limit=payload.limit,
            column_names=payload.column_names,
            output_format=payload.output_format,
            order_by=payload.order_by,
        )

        logger.info(f"Sliced data frame {data_frame.name} in {time.monotonic() - initial_time:.2f} seconds")

        # Return as streaming response
        if payload.output_format == "json":
            return Response(content=sliced_data, media_type="application/json")
        elif payload.output_format == "parquet":
            return Response(
                content=sliced_data,
                media_type="application/octet-stream",
                headers={"Content-Disposition": f"attachment; filename={data_frame.name}.parquet"},
            )
        else:
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST,
                message=f"Unsupported format: {payload.output_format}",
            )

    except PlatformHTTPError:
        raise
    except Exception as e:
        logger.error("Error slicing data frame", error=e, data_frame_id=data_frame.data_frame_id)
        raise PlatformHTTPError(
            error_code=ErrorCode.UNEXPECTED,
            message="Internal server error while slicing data frame",
        ) from e


@dataclasses.dataclass
class _DataFrameAssemblyInfoRequest:
    """Request payload for getting assembly information."""

    data_frame_names: Annotated[
        list[str],
        "The list of data frame names to get assembly information for.",
    ]


@router.post("/{tid}/data-frames/assembly-info")
async def get_data_frames_assembly_info(
    user: AuthedUser,
    tid: str,
    storage: StorageDependency,
    payload: _DataFrameAssemblyInfoRequest,
) -> dict[str, str]:
    """Get assembly information for one or more data frames.

    This endpoint returns information about how data frames were assembled, including:
    - The SQL query used to create the data frame (if applicable)
    - For each table referenced in the query, how it was assembled (recursively)

    Args:
        user: The user making the request.
        tid: The ID of the thread.
        storage: The storage to use.
        payload: The request payload containing the list of data frame names.

    Returns:
        A dictionary of data frame names to assembly information in markdown format.
    """
    from agent_platform.server.data_frames.data_frames_assembly_info import AssemblyInfo
    from agent_platform.server.data_frames.data_frames_kernel import DataFramesKernel
    from agent_platform.server.storage.base import BaseStorage

    base_storage = typing.cast(BaseStorage, storage)
    await _verify_thread_access(base_storage, user.user_id, tid)

    df_name_to_assembly_info = {}
    for data_frame_name in payload.data_frame_names:
        data_frame = await base_storage.get_data_frame(thread_id=tid, data_frame_name=data_frame_name)

        data_frames_kernel = DataFramesKernel(base_storage, user, tid)
        assembly_info = AssemblyInfo()

        await data_frames_kernel.resolve_data_frame(data_frame, assembly_info=assembly_info)
        df_name_to_assembly_info[data_frame_name] = await assembly_info.to_markdown(storage=base_storage)
    return df_name_to_assembly_info


@dataclasses.dataclass
class _GetAsValidatedQueryPayload:
    """Request payload for getting a data frame as a validated query."""

    data_frame_name: Annotated[str, "The name of the data frame to get as a validated query."]


class _GetAsValidatedQueryResponse(TypedDict):
    """Response containing the verified query and semantic data model name."""

    verified_query: VerifiedQuery
    semantic_data_model_name: Annotated[
        str | None,
        "The name of the semantic data model that was auto-detected from the data frame sources. "
        "None if semantic data model was not used to create the data frame.",
    ]


@router.post("/{tid}/data-frames/as-validated-query")
async def get_data_frame_as_validated_query(
    user: AuthedUser,
    tid: str,
    storage: StorageDependency,
    payload: _GetAsValidatedQueryPayload,
) -> _GetAsValidatedQueryResponse:
    """Get a data frame as a validated query with semantic data model name.

    This endpoint retrieves a data frame's SQL query as a validated query object.
    The data frame must have been created from a SQL computation.

    It also attempts to determine which semantic data model was used to create
    the data frame by analyzing the computation_input_sources. If a single semantic
    data model is found, its name is returned to enable auto-selection in the UI.

    Args:
        user: The user making the request.
        tid: The ID of the thread.
        storage: The storage to use.
        payload: The request payload containing the data frame name.

    Returns:
        A response containing the VerifiedQuery and the semantic data model name.
    """
    from agent_platform.server.data_frames.data_frames_kernel import DataFramesKernel
    from agent_platform.server.data_frames.data_node import DataNodeFromIbisResult
    from agent_platform.server.storage.base import BaseStorage

    base_storage = typing.cast(BaseStorage, storage)
    await _verify_thread_access(base_storage, user.user_id, tid)

    # Get the data frame
    data_frame = await base_storage.get_data_frame(thread_id=tid, data_frame_name=payload.data_frame_name)

    # Verify that the data frame was created from a SQL computation
    if data_frame.input_id_type != "sql_computation":
        raise PlatformHTTPError(
            error_code=ErrorCode.BAD_REQUEST,
            message=(
                f"Data frame '{payload.data_frame_name}' was not created from a "
                "SQL computation. Only data frames created from SQL queries can "
                "be saved as validated queries."
            ),
        )

    if not data_frame.computation:
        raise PlatformHTTPError(
            error_code=ErrorCode.BAD_REQUEST,
            message=f"Data frame '{payload.data_frame_name}' does not have a SQL query.",
        )

    # Note: we have to get the full_sql_query_logical_str to be able to recreate the query later.
    data_frames_kernel = DataFramesKernel(base_storage, user, tid)
    resolved_df = await data_frames_kernel.resolve_data_frame(data_frame)
    if not isinstance(resolved_df, DataNodeFromIbisResult):
        raise PlatformHTTPError(
            error_code=ErrorCode.BAD_REQUEST,
            message=(
                f"Data frame '{payload.data_frame_name}' did not resolve to the expected type "
                f"(and thus the full SQL query logical string is not available). "
                f"Type: {type(resolved_df)}"
            ),
        )

    full_sql_query_logical_str = resolved_df.full_sql_query_logical_str

    # Convert data frame name to verified query name format
    from agent_platform.core.data_frames.data_frame_utils import (
        data_frame_name_to_verified_query_name,
    )

    verified_query_name = data_frame_name_to_verified_query_name(payload.data_frame_name)

    verified_query = VerifiedQuery(
        name=verified_query_name,
        nlq=data_frame.description or "",
        verified_at=datetime.datetime.now(datetime.UTC).isoformat(),
        verified_by=user.user_id,
        sql=full_sql_query_logical_str,
    )

    # Get semantic data model name from data frame sources
    sdm_name = await get_semantic_data_model_name(data_frame)

    return _GetAsValidatedQueryResponse(
        verified_query=verified_query,
        semantic_data_model_name=sdm_name,
    )


@dataclasses.dataclass
class _SaveAsValidatedQueryPayload:
    """Request payload for saving a validated query."""

    verified_query: Annotated[VerifiedQuery, "The verified query to save (VerifiedQuery object)."]
    semantic_data_model_id: Annotated[str, "The ID of the semantic data model to add the validated query to."]


@router.post("/{tid}/data-frames/save-as-validated-query")
async def save_data_frame_as_validated_query(
    user: AuthedUser,
    tid: str,
    storage: StorageDependency,
    payload: _SaveAsValidatedQueryPayload,
) -> dict[str, str]:
    """Save a validated query in a semantic data model.

    This endpoint saves a validated query in the specified semantic data model.

    Args:
        user: The user making the request.
        tid: The ID of the thread.
        storage: The storage to use.
        payload: The request payload containing the verified query and semantic data model ID.

    Returns:
        A dictionary with a success message.
    """
    from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel
    from agent_platform.core.data_frames.semantic_data_model_validation import (
        validate_semantic_model_payload_and_extract_references,
    )
    from agent_platform.server.storage.base import BaseStorage

    base_storage = typing.cast(BaseStorage, storage)
    await _verify_thread_access(base_storage, user.user_id, tid)

    # Get the semantic data model
    semantic_data_model_dict = await base_storage.get_semantic_data_model(payload.semantic_data_model_id)

    # Cast to SemanticDataModel type
    semantic_data_model = typing.cast(SemanticDataModel, semantic_data_model_dict)

    # Extract existing references to preserve them when updating
    references = validate_semantic_model_payload_and_extract_references(semantic_data_model)
    if references.errors:
        raise PlatformHTTPError(
            error_code=ErrorCode.BAD_REQUEST,
            message="The semantic data model is invalid: \n" + "\n".join(references.errors),
        )

    # Initialize verified_queries if it doesn't exist
    if "verified_queries" not in semantic_data_model or not isinstance(semantic_data_model["verified_queries"], list):
        semantic_data_model["verified_queries"] = []

    # Cast the verified query from the payload
    verified_query = typing.cast(VerifiedQuery, payload.verified_query)

    # Check if a verified query with this name already exists
    verified_queries = semantic_data_model["verified_queries"]
    existing_query_index = None
    for i, query in enumerate(verified_queries):
        if query.name == verified_query.name:
            existing_query_index = i
            break

    # Add or update the verified query
    if existing_query_index is not None:
        verified_queries[existing_query_index] = verified_query
    else:
        verified_queries.append(verified_query)

    await base_storage.update_semantic_data_model(
        semantic_data_model_id=payload.semantic_data_model_id,
        semantic_model=semantic_data_model,
    )

    return {
        "message": f"Successfully saved validated query '{verified_query.name}'.",
    }
