import dataclasses
import datetime
import typing
from typing import Annotated, Literal, TypedDict

from fastapi import HTTPException, Response
from fastapi.routing import APIRouter
from pydantic.main import BaseModel
from structlog.stdlib import get_logger

from agent_platform.server.api.dependencies import (
    StorageDependency,
)
from agent_platform.server.auth import AuthedUser
from sema4ai.common.callback import Callback

if typing.TYPE_CHECKING:
    import pyarrow
    from sema4ai.actions import Row

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
                cache_key_sheet_metadata = self._generate_cache_key(
                    "metadata", self._file_id, sheet_name
                )
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
            cache_key_samples = self._generate_cache_key(
                "samples_small", self._file_id, data_frame.sheet_name
            )
            cached_entry = await self._storage.get_cache_entry(cache_key_samples)
            if cached_entry is None:
                ret.cache_miss.append(data_frame)
            else:
                sample_rows = json.loads(cached_entry.cache_data.decode("utf-8"))
                data_frame.sample_rows = sample_rows[:num_samples]
                ret.cache_hit.append(data_frame)
                logger.info(
                    f"Loaded {len(data_frame.sample_rows)} samples from samples cache for "
                    f"data frame {data_frame.name}"
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
            cache_key_full_data = self._generate_cache_key(
                "full_data", self._file_id, data_frame.sheet_name
            )
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
                loaded_full = await self.load_samples_from_full_data_cache(
                    loaded.cache_miss, num_samples
                )
                loaded.cache_hit.extend(loaded_full.cache_hit)
                loaded.cache_miss = loaded_full.cache_miss

        elif num_samples == -1 or num_samples > self.max_samples_in_short_samples_cache:
            # We have to load from the full data (we just cache up to 10 samples separately)
            loaded = await self.load_samples_from_full_data_cache(found_in_cache, num_samples)

        else:
            raise RuntimeError(
                f"Invalid number of samples: {num_samples} (should not get here as it's "
                f"validated above)"
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

    async def cache_multiple_sheet_names(
        self, sheet_names: list[str], time_to_compute_data_in_seconds: float
    ):
        import json

        await self._storage.set_cache_entry(
            self._generate_cache_key("metadata", self._file_id, None),
            json.dumps({"sheet_names": sheet_names}).encode("utf-8"),
            time_to_compute_data_in_seconds=time_to_compute_data_in_seconds,
        )

    async def cache_metadata(
        self, data_frame: _DataFrameInspectionAPI, time_to_compute_data_in_seconds: float
    ):
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


@router.get("/{tid}/inspect-file-as-data-frame")
async def inspect_file_as_data_frame(  # noqa: C901, PLR0913, PLR0912,PLR0915
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

    import time

    from agent_platform.core.errors.base import PlatformError
    from agent_platform.core.errors.responses import ErrorCode
    from agent_platform.server.data_frames.data_node import convert_pyarrow_slice_to_list_of_rows
    from agent_platform.server.data_frames.data_reader import (
        create_file_data_reader,
        get_file_metadata,
    )

    if num_samples < -1:
        raise PlatformError(
            ErrorCode.BAD_REQUEST, message="num_samples must be 0, -1 or a positive number"
        )

    # Don't cache if we have dummy UploadedFile instances
    # (file_id is empty, thread_id is None, agent_id is None)
    should_cache = bool(file_id and tid)

    # Get the file metadata to make sure the file exists and the user has access to it.
    file_metadata = await get_file_metadata(
        user.user_id, tid, storage, file_id=file_id, file_ref=file_ref
    )

    # Try to get from cache first if we should cache
    loaded: _CacheHandler._LoadedFromCache | None = None
    if should_cache:
        try:
            found_in_cache: list[_DataFrameInspectionAPI] = []
            assert file_id
            cache_handler = _CacheHandler(tid, storage, sheet_name, file_id)
            found_in_cache = await cache_handler.create_data_frames_inspection_api_from_cache()

            if num_samples == 0:
                # We're good to go, no samples to load, full cache hit.
                return found_in_cache

            loaded = await cache_handler.load_samples_from_cache(found_in_cache, num_samples)
            if not loaded.cache_miss:
                # Ok, all matched from the cache.
                return loaded.cache_hit
        except CacheMissError:
            pass
        except Exception as e:
            logger.critical(f"Failed to get cached data: {e}", exc_info=True)

    # If we get here, either we shouldn't cache or cache miss occurred
    start_time = time.monotonic()

    data_reader = await create_file_data_reader(
        user, tid, storage, sheet_name, file_metadata=file_metadata
    )

    ret: list[_DataFrameInspectionAPI] = []

    all_sheets = list(data_reader.iter_sheets())

    if should_cache:
        if len(all_sheets) > 1:
            await cache_handler.cache_multiple_sheet_names(
                [(sheet.name or "<unnamed-sheet>") for sheet in all_sheets],
                start_time - time.monotonic(),
            )

    for sheet in all_sheets:
        value = _DataFrameInspectionAPI(
            thread_id=tid,
            name=file_metadata.file_ref,
            file_id=file_metadata.file_id,
            file_ref=file_metadata.file_ref,
            sheet_name=sheet.name,
            num_rows=sheet.num_rows,
            num_columns=sheet.num_columns,
            created_at=datetime.datetime.now(),
            column_headers=sheet.column_headers,
            sample_rows=[],
        )

        if should_cache:
            await cache_handler.cache_metadata(value, start_time - time.monotonic())

        if num_samples == 0:
            sample_rows = []

        # i.e.: if we want all samples or if if the number of samples required is greater
        # than the amount of samples stored in the "short samples" cache we load
        # the full data and cache both the full data as well as the short samples data.
        elif num_samples == -1 or (
            should_cache and num_samples > cache_handler.max_samples_in_short_samples_cache
        ):
            full_data: pyarrow.Table = sheet.to_ibis()
            sample_rows: list[Row] = convert_pyarrow_slice_to_list_of_rows(
                full_data, None, None, None, None
            )
            # Cache the full data and the sample data
            if should_cache:
                await cache_handler.cache_full_data(value, full_data, start_time - time.monotonic())
                sampled_to_cache = sample_rows[: cache_handler.max_samples_in_short_samples_cache]
                await cache_handler.cache_sample_data(
                    value, sampled_to_cache, start_time - time.monotonic()
                )

            if num_samples != -1:
                sample_rows = sample_rows[:num_samples]

        else:
            assert num_samples > 0, "num_samples must be 0, -1 or a positive number"

            sample_rows = sheet.list_sample_rows(num_samples)

            if should_cache:
                # Cache 10 rows
                sampled_to_cache = sample_rows[: cache_handler.max_samples_in_short_samples_cache]
                await cache_handler.cache_sample_data(
                    value, sampled_to_cache, start_time - time.monotonic()
                )

        value.sample_rows = sample_rows

        ret.append(value)

    return ret


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


@router.post("/{tid}/data-frames/from-file")
async def create_data_frame_from_file(  # noqa: PLR0913
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
    import keyword
    import os.path
    import uuid

    from agent_platform.core.data_frames.data_frames import DATAFRAMES_LLM_SAMPLE_ROWS_LIMIT
    from agent_platform.core.errors.base import PlatformError
    from sema4ai.common.text import slugify

    if num_samples < 0:
        use_num_samples = num_samples
    else:
        use_num_samples = max(num_samples, DATAFRAMES_LLM_SAMPLE_ROWS_LIMIT)

    inspected_data_frames = await inspect_file_as_data_frame(
        user, tid, storage, use_num_samples, sheet_name, file_id=file_id, file_ref=file_ref
    )
    if len(inspected_data_frames) == 0:
        raise HTTPException(status_code=400, detail="No data frames found in file")

    if len(inspected_data_frames) > 1:
        found_sheet_names = [
            inspected_data_frame.sheet_name for inspected_data_frame in inspected_data_frames
        ]
        raise HTTPException(
            status_code=400,
            detail="Multiple data frames found in file. Please specify sheet_name. "
            f"Available sheet names: {found_sheet_names!r}.",
        )

    inspected_data_frame = inspected_data_frames[0]

    from agent_platform.core.data_frames.data_frames import PlatformDataFrame
    from agent_platform.server.storage.base import BaseStorage

    base_storage = typing.cast(BaseStorage, storage)

    # Get the thread to find the agent_id
    thread = await base_storage.get_thread(user.user_id, tid)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    use_name = name
    if not use_name:
        # Try to generate a name from the file name / sheet name.
        ref = os.path.basename(inspected_data_frame.name)
        ref = os.path.splitext(ref)[0]

        use_name = slugify(ref).replace("-", "_")
        if sheet_name:
            sheet_name_as_slug = slugify(sheet_name).replace("-", "_")
            use_name = f"{use_name}_{sheet_name_as_slug}"

        if not use_name.isidentifier() or keyword.iskeyword(use_name):
            use_name = f"data_{use_name}"  # first char may be digit or it's a keyword.

        if not use_name.isidentifier() or keyword.iskeyword(use_name):
            # Still not valid, let's raise an error.
            raise PlatformError(
                message=(
                    "It was not possible to generate a valid name for the data frame. "
                    f"Please provide one as a parameter to the request (auto-generated name: "
                    f"{use_name!r})."
                )
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

    await base_storage.save_data_frame(data_frame)

    return _DataFrameCreationAPI(
        data_frame_id=data_frame.data_frame_id,
        thread_id=data_frame.thread_id,
        name=data_frame.name,
        sheet_name=sheet_name,
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
            sql_query=data_frame.computation
            if data_frame.input_id_type == "sql_computation"
            else None,
        )

        if num_samples != 0:
            initial_time = time.monotonic()
            data_frames_kernel = DataFramesKernel(base_storage, user, tid)
            resolved_df = await data_frames_kernel.resolve_data_frame(data_frame)
            data_frame_api.sample_rows = resolved_df.list_sample_rows(num_samples)
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

    data_frames_kernel = DataFramesKernel(base_storage, user, tid)

    resolved_df, samples_table = await create_data_frame_from_sql_computation_api(
        data_frames_kernel=data_frames_kernel,
        storage=base_storage,
        new_data_frame_name=payload.new_data_frame_name,
        sql_query=payload.sql_query,
        dialect=payload.sql_dialect,
        description=payload.description,
        num_samples=num_samples,
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
        sql_query=platform_data_frame.computation
        if platform_data_frame.input_id_type == "sql_computation"
        else None,
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
async def get_data_frame(  # noqa: PLR0913
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
async def slice_data_frame(  # noqa: PLR0912,C901
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

    from agent_platform.core.errors.base import PlatformError
    from agent_platform.core.errors.responses import ErrorCode
    from agent_platform.server.data_frames.data_frames_kernel import DataFramesKernel
    from agent_platform.server.storage.base import BaseStorage

    initial_time = time.monotonic()
    logger.info(
        f"Starting slice_data_frame for {payload.data_frame_name or payload.data_frame_id} "
        f"in thread {tid}"
    )

    # Validate that exactly one of data_frame_id or data_frame_name is provided
    if payload.data_frame_id is None and payload.data_frame_name is None:
        raise PlatformError(
            error_code=ErrorCode.BAD_REQUEST,
            message="Either data_frame_id or data_frame_name must be provided",
        )

    if payload.data_frame_id is not None and payload.data_frame_name is not None:
        raise PlatformError(
            error_code=ErrorCode.BAD_REQUEST,
            message="Only one of data_frame_id or data_frame_name can be provided",
        )

    base_storage = typing.cast(BaseStorage, storage)
    data_frames_kernel = DataFramesKernel(base_storage, user, tid)

    # Find the data frame
    data_frame = None
    if payload.data_frame_id is not None:
        # Get by ID
        data_frames = await base_storage.list_data_frames(tid)
        for df in data_frames:
            if df.data_frame_id == payload.data_frame_id:
                data_frame = df
                break
        else:
            raise PlatformError(
                error_code=ErrorCode.NOT_FOUND,
                message=f"Data frame with id {payload.data_frame_id} not found in thread: {tid}",
            )
    else:
        # Get by name
        data_frames = await base_storage.list_data_frames(tid)
        for df in data_frames:
            if df.name == payload.data_frame_name:
                data_frame = df
                break
        else:
            raise PlatformError(
                error_code=ErrorCode.NOT_FOUND,
                message=(
                    f"Data frame with name {payload.data_frame_name} not found in thread: {tid}"
                ),
            )

    try:
        # Resolve the data frame
        resolved_df = await data_frames_kernel.resolve_data_frame(data_frame)

        # Get the sliced data
        sliced_data = resolved_df.slice(
            offset=payload.offset,
            limit=payload.limit,
            column_names=payload.column_names,
            output_format=payload.output_format,
            order_by=payload.order_by,
        )

        logger.info(
            f"Sliced data frame {data_frame.name} in {time.monotonic() - initial_time:.2f} seconds"
        )

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
            raise PlatformError(
                message=f"Unsupported format: {payload.output_format}",
            )

    except PlatformError:
        raise
    except Exception as e:
        logger.error("Error slicing data frame", error=e, data_frame_id=data_frame.data_frame_id)
        raise PlatformError(message="Internal server error while slicing data frame") from e
