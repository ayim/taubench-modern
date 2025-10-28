import typing

from pydantic import BaseModel
from structlog import get_logger

if typing.TYPE_CHECKING:
    from agent_platform.core.data_frames.semantic_data_model_types import (
        FileReference,
        LogicalTable,
        SemanticDataModel,
    )
    from agent_platform.core.data_frames.semantic_data_model_validation import (
        EmptyFileReference,
        References,
    )
    from agent_platform.core.kernel_interfaces.data_frames import DataFrameArchState
    from agent_platform.server.api.private_v2.threads_data_frames import _DataFrameInspectionAPI
    from agent_platform.server.auth.handlers import AuthedUser
    from agent_platform.server.storage.base import BaseStorage

logger = get_logger(__name__)


class MatchingInfo(BaseModel):
    uploaded_file_thread_id: str
    uploaded_file_file_ref: str
    sheet_name_to_logical_table_names: "dict[str | None, list[str]]"


class SemanticDataModelCollector:
    """
    This class is responsible for collecting semantic data models from the thread.
    It will collect the semantic data models from the thread and check if they have
    any unresolved file references. If they do, it will try to find a file in the thread
    that matches the unresolved file reference (and update the resulting semantic data model
    with the file reference).

    If the reference cannot be resolved, the semantic data model will not be included in the
    resulting list.
    """

    def __init__(
        self,
        agent_id: str,
        thread_id: str,
        user: "AuthedUser",
        state: "DataFrameArchState | None",
    ):
        from sema4ai.common.callback import Callback

        self.agent_id = agent_id
        self.thread_id = thread_id
        self.user = user
        self.state = state
        self.on_cache_hit = Callback()

    async def _find_file_which_matches_unresolved_file_reference(  # noqa
        self,
        storage: "BaseStorage",
        references: "References",
        semantic_data_model: "SemanticDataModel",
        updated_at: str,
    ) -> MatchingInfo | None:
        from agent_platform.server.api.private_v2.threads_data_frames import (
            inspect_file_as_data_frame,
        )

        tables_with_unresolved_file_references: set[EmptyFileReference] = (
            references.tables_with_unresolved_file_references
        )

        if not tables_with_unresolved_file_references:
            raise RuntimeError(
                "Don't call this method unless there are actual unresolved file references!"
            )

        # Load the files in the thread
        files_in_thread = await storage.get_thread_files(
            thread_id=self.thread_id,
            user_id=self.user.user_id,
        )

        if self.state is not None:
            cache_key_lst = [f"{self.thread_id}:{updated_at}"]
            for empty_file_reference in tables_with_unresolved_file_references:
                cache_key_lst.append(
                    f"{empty_file_reference.base_table_table}:{empty_file_reference.sheet_name}"
                )
            cache_key = ";".join(cache_key_lst)

            matching_info = self.state.empty_file_cache_key_to_matching_info.get(cache_key)
            if matching_info:
                try:
                    ret = MatchingInfo(**matching_info)
                    existing_file = next(
                        (
                            file
                            for file in files_in_thread
                            if file.file_ref == ret.uploaded_file_file_ref
                        ),
                        None,
                    )
                    if existing_file is not None:
                        self.on_cache_hit(ret)
                        return ret
                except Exception:
                    logger.error(
                        f"Error parsing matching info for cache key {cache_key}: {matching_info}",
                        exc_info=True,
                    )

        for uploaded_file in files_in_thread:
            try:
                # Note: it's a bit of a brute force approach to have to inspect the files,
                # but it's the only way to know if the file matches the semantic data model.
                # We should at least cache this information accordingly (both the result of
                # the inspection as well as which file matches which semantic data model).
                # At least we cache the inspection metadata for the file!
                inspected_data_frames: list[
                    _DataFrameInspectionAPI
                ] = await inspect_file_as_data_frame(
                    user=self.user,
                    tid=self.thread_id,
                    storage=storage,
                    num_samples=0,  # No samples are needed, just metadata!
                    sheet_name=None,  # inspect all sheets
                    file_id=uploaded_file.file_id,
                    file_ref=uploaded_file.file_ref,
                )

                # Check if any of the inspected data frames match any of the unresolved references
                sheet_name_to_logical_table_names: dict[str | None, list[str]] = {}
                found_matching = 0
                for inspected_data_frame in inspected_data_frames:
                    assert inspected_data_frame.file_ref is not None, (
                        "File ref is expected in data frame inspected from file."
                    )
                    for unresolved_reference in tables_with_unresolved_file_references:
                        # Match by sheet name and columns in the table

                        if len(inspected_data_frames) == 1:
                            sheet_matches = True  # single sheet, matches by default
                        else:
                            sheet_matches = (
                                not (
                                    unresolved_reference.sheet_name
                                    and inspected_data_frame.sheet_name
                                )
                                or unresolved_reference.sheet_name
                                == inspected_data_frame.sheet_name
                            )

                        if not sheet_matches:
                            continue

                        logical_table_with_matching_columns = (
                            self._logical_table_with_matching_columns(
                                semantic_data_model, unresolved_reference, inspected_data_frame
                            )
                        )

                        if not logical_table_with_matching_columns:
                            continue

                        matching_table_names: list[str] = (
                            sheet_name_to_logical_table_names.setdefault(
                                inspected_data_frame.sheet_name, []
                            )
                        )
                        name = logical_table_with_matching_columns.get("name")
                        if not name:
                            logger.error(
                                f"Logical table with matching columns has no name: "
                                f"{logical_table_with_matching_columns}",
                            )
                            continue
                        matching_table_names.append(name)
                        found_matching += 1
                        if found_matching == len(tables_with_unresolved_file_references):
                            logger.info(
                                f"Found matching file for unresolved reference (file_ref: "
                                f"{uploaded_file.file_ref})",
                            )
                            matching_info = MatchingInfo(
                                uploaded_file_thread_id=inspected_data_frame.thread_id,
                                uploaded_file_file_ref=inspected_data_frame.file_ref,
                                sheet_name_to_logical_table_names=sheet_name_to_logical_table_names,
                            )
                            if self.state is not None:
                                self.state.empty_file_cache_key_to_matching_info[cache_key] = (
                                    matching_info.model_dump()
                                )
                            return matching_info
            except Exception as e:
                logger.error(
                    f"Error inspecting file {uploaded_file.file_ref} for unresolved "
                    f"references: {e}",
                )
                continue

        logger.info(
            f"No matching file found in thread for unresolved references in semantic data model: "
            f"{tables_with_unresolved_file_references}",
        )
        return None

    def _logical_table_with_matching_columns(
        self,
        semantic_data_model: "SemanticDataModel",
        unresolved_reference: "EmptyFileReference",
        inspected_data_frame: "_DataFrameInspectionAPI",
    ) -> "LogicalTable | None":
        """Check if the columns of the semantic data model table match the columns of the
        inspected data frame.

        Args:
            semantic_data_model: The semantic data model containing table definitions
            unresolved_reference: The unresolved file reference containing the logical table name
            inspected_data_frame: The inspected data frame with column headers

        Returns:
            True if the columns match, False otherwise
        """
        # Get the logical table from the semantic data model
        logical_table = self._find_logical_table_by_name(
            semantic_data_model, unresolved_reference.logical_table_name
        )
        if not logical_table:
            return None

        # Extract column names from the semantic data model table
        semantic_columns = self._extract_semantic_table_columns(logical_table)
        if not semantic_columns:
            return None

        # Get column headers from the inspected data frame
        inspected_columns = set(x.lower() for x in inspected_data_frame.column_headers or [])

        # Check if the semantic columns match the inspected columns
        # We consider it a match if all semantic columns are present in the inspected data frame
        # (the inspected data frame may have additional columns)
        if semantic_columns.issubset(inspected_columns):
            return logical_table
        return None

    def _find_logical_table_by_name(
        self, semantic_data_model: "SemanticDataModel", logical_table_name: str
    ) -> "LogicalTable | None":
        """Find a logical table by name in the semantic data model.

        Args:
            semantic_data_model: The semantic data model
            logical_table_name: The name of the logical table to find

        Returns:
            The logical table dict if found, None otherwise
        """
        tables = semantic_data_model.get("tables") or []
        for table in tables:
            if table.get("name") == logical_table_name:
                return table
        return None

    def _extract_semantic_table_columns(self, logical_table: "LogicalTable") -> set[str]:
        """Extract column names from a logical table's dimensions, facts, and time_dimensions.

        Args:
            logical_table: The logical table dict

        Returns:
            Set of column names from the semantic table
        """
        columns = set()

        for attr in ["dimensions", "facts", "time_dimensions", "metrics"]:
            columns_info = logical_table.get(attr) or []
            for column_info in columns_info:
                if isinstance(column_info, dict) and "name" in column_info:
                    columns.add(column_info["expr"].lower())
        return columns

    async def collect_semantic_data_models(
        self, storage: "BaseStorage"
    ) -> "list[BaseStorage.SemanticDataModelInfo]":
        try:
            return await self._collect_semantic_data_models(storage)
        except Exception:
            logger.exception("Error collecting semantic data models")
            return []

    async def _collect_semantic_data_models(  # noqa
        self, storage: "BaseStorage"
    ) -> "list[BaseStorage.SemanticDataModelInfo]":
        from agent_platform.core.data_frames.semantic_data_model_validation import (
            validate_semantic_model_payload_and_extract_references,
        )

        semantic_data_model_infos: list[
            BaseStorage.SemanticDataModelInfo
        ] = await storage.list_semantic_data_models(
            agent_id=self.agent_id, thread_id=self.thread_id
        )

        # At this point we should make sure that any semantic data model used needs to have
        # a valid target (for instance, a semantic data model needs to reference either
        # a valid data connection or a valid file, if we're not able to find a valid target
        # then we cannot use it).

        resolved_semantic_data_model_infos: list[BaseStorage.SemanticDataModelInfo] = []

        for semantic_data_model_info in semantic_data_model_infos:
            semantic_data_model: SemanticDataModel = semantic_data_model_info["semantic_data_model"]
            references = validate_semantic_model_payload_and_extract_references(semantic_data_model)
            if references.errors:
                logger.error(
                    f"Error: semantic data model: {semantic_data_model.get('name')} has errors"
                    f" (unable to use it in the kernel)",
                    errors=references.errors,
                )
                continue

            if not references.tables_with_unresolved_file_references:
                resolved_semantic_data_model_infos.append(semantic_data_model_info)
                continue

            # Ok, we have some unresolved file references, we need to collect the files
            # in the thread and check if they may be able to satisfy the requirements
            # for the semantic data model to be applied to. If they do, update the
            # semantic data model info with the proper file references.

            found = await self._find_file_which_matches_unresolved_file_reference(
                storage, references, semantic_data_model, semantic_data_model_info["updated_at"]
            )

            if found is not None:
                logical_table_name_to_logical_table: dict[str, LogicalTable] = {}
                for logical_table in semantic_data_model.get("tables") or []:
                    name = logical_table.get("name")
                    if not name:
                        continue
                    logical_table_name_to_logical_table[name] = logical_table

                # Update the file information in the base_table to match the found file
                matched_all = True
                for (
                    sheet_name,
                    logical_table_names,
                ) in found.sheet_name_to_logical_table_names.items():
                    for logical_table_name in logical_table_names:
                        logical_table = logical_table_name_to_logical_table.get(logical_table_name)
                        if not logical_table:
                            matched_all = False
                            break

                        base_table = logical_table.get("base_table")
                        if base_table is None:
                            base_table = logical_table["base_table"] = {}

                        assert base_table is not None
                        assert found.uploaded_file_thread_id is not None
                        file_reference: FileReference = {
                            "thread_id": found.uploaded_file_thread_id,
                            "file_ref": found.uploaded_file_file_ref,
                            "sheet_name": sheet_name,
                        }
                        base_table["file_reference"] = file_reference

                if matched_all:
                    # We've mutated the semantic data model info in the code above!
                    resolved_semantic_data_model_infos.append(semantic_data_model_info)

        return resolved_semantic_data_model_infos
