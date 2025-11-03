import typing
from pathlib import Path

from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel
from agent_platform.core.kernel_interfaces.data_frames import DataFrameArchState
from server.tests.storage_fixtures import *  # noqa

if typing.TYPE_CHECKING:
    from agent_platform.server.storage.sqlite.sqlite import SQLiteStorage

SEMANTIC_DATA_MODEL_WITH_UNRESOLVED_FILE_REFERENCE: SemanticDataModel = {
    "name": "test_semantic_model_with_unresolved_file",
    "description": "A test semantic model with unresolved file reference",
    "tables": [
        {
            "name": "sales_data",
            "base_table": {
                "table": "sales_data_table",
                "file_reference": {
                    "thread_id": "",
                    "file_ref": "",
                    "sheet_name": None,
                },
            },
            "dimensions": [
                {
                    "name": "product_name",
                    "expr": "product_name",
                    "data_type": "TEXT",
                    "description": "The name of the product",
                },
                {
                    "name": "category",
                    "expr": "category",
                    "data_type": "TEXT",
                    "description": "The category of the product",
                },
            ],
            "facts": [
                {
                    "name": "revenue",
                    "expr": "revenue",
                    "data_type": "NUMBER",
                    "description": "The revenue amount",
                },
                {
                    "name": "quantity",
                    "expr": "quantity",
                    "data_type": "NUMBER",
                    "description": "The quantity sold",
                },
            ],
        },
    ],
}


class _CustomArchState(DataFrameArchState):
    def __init__(self):
        self.empty_file_cache_key_to_matching_info = {}
        self.data_frames_tools_state = "enabled"


async def test_semantic_data_model_collector(sqlite_storage: "SQLiteStorage", tmpdir: Path):
    from agent_platform.core.user import User
    from agent_platform.server.auth.handlers import AuthedUser
    from agent_platform.server.data_frames.semantic_data_model_collector import (
        MatchingInfo,
        SemanticDataModelCollector,
    )
    from server.tests.storage.sample_model_creator import SampleModelCreator

    model_creator = SampleModelCreator(sqlite_storage, tmpdir)
    await model_creator.setup()
    user_id = await model_creator.get_user_id()
    agent = await model_creator.obtain_sample_agent()
    thread = await model_creator.obtain_sample_thread()

    # First, save the semantic data model with unresolved file reference
    semantic_data_model_id = await sqlite_storage.set_semantic_data_model(
        semantic_data_model_id=None,
        semantic_model=SEMANTIC_DATA_MODEL_WITH_UNRESOLVED_FILE_REFERENCE,
        data_connection_ids=[],
        file_references=[],
    )

    # Associate the semantic data model with the thread
    await sqlite_storage.set_thread_semantic_data_models(
        thread_id=thread.thread_id,
        semantic_data_model_ids=[semantic_data_model_id],
    )

    state = _CustomArchState()

    collector = SemanticDataModelCollector(
        agent_id=agent.agent_id,
        thread_id=thread.thread_id,
        user=typing.cast(AuthedUser, User(user_id=user_id, sub="")),
        state=state,
    )

    cache_hits: list[MatchingInfo] = []

    def on_cache_hit(matching_info: MatchingInfo):
        cache_hits.append(matching_info)

    collector.on_cache_hit.register(on_cache_hit)

    # First attempt: should fail to collect because no matching file exists
    collected = await collector.collect_semantic_data_models(storage=sqlite_storage)
    assert len(collected) == 0, "Should not collect semantic data model without matching file"

    # Create a CSV file with matching columns
    csv_content = (
        b"product_name,category,revenue,quantity\n"
        b"Widget A,Electronics,100.50,5\n"
        b"Widget B,Electronics,75.25,3\n"
        b"Widget C,Home,50.00,2"
    )
    csv_file = await model_creator.obtain_sample_file(
        file_content=csv_content,
        file_name="sales_data.csv",
        mime_type="text/csv",
    )

    assert not state.empty_file_cache_key_to_matching_info, "Cache should be empty"

    # Second attempt: should succeed because matching file now exists
    collected = await collector.collect_semantic_data_models(storage=sqlite_storage)
    assert len(collected) == 1, "Should collect semantic data model with matching file"
    assert not cache_hits, "No cache hits should be registered"
    assert state.empty_file_cache_key_to_matching_info, "Cache should be populated"

    def verify_collected(collected):
        # Verify the collected model has resolved file reference
        collected_model_and_refs = collected[0]
        collected_model = collected_model_and_refs.semantic_data_model_info["semantic_data_model"]
        tables = collected_model.get("tables")
        assert tables is not None, "Tables should not be None"
        table = tables[0]
        base_table = table.get("base_table")
        assert base_table is not None, "Base table should not be None"
        file_reference = base_table.get("file_reference")
        assert file_reference is not None, "File reference should not be None"

        assert file_reference.get("thread_id") == thread.thread_id
        assert file_reference.get("file_ref") == csv_file.file_ref
        assert file_reference.get("sheet_name") is None

    verify_collected(collected)

    # Third attempt: should hit the cache
    collected = await collector.collect_semantic_data_models(storage=sqlite_storage)
    assert len(collected) == 1, "Should collect semantic data model with matching file"
    assert len(cache_hits) == 1, "One cache hit should be registered"
    verify_collected(collected)

    del cache_hits[:]
    # Now, delete the file and the cache should not match again
    await model_creator.storage.delete_file(thread, csv_file.file_id, user_id)

    collected = await collector.collect_semantic_data_models(storage=sqlite_storage)
    assert len(collected) == 0, "Should not collect semantic data model without matching file"
    assert not cache_hits, "No cache hits should be registered"


async def test_semantic_data_model_collector_with_state_dict_access(
    sqlite_storage: "SQLiteStorage", tmpdir: Path
):
    """
    Regression test for bug where empty_file_cache_key_to_matching_info was a FieldInfo
    descriptor instead of a dict, causing AttributeError when calling .get().

    This test ensures that the state's empty_file_cache_key_to_matching_info field
    is a proper dict that supports .get() method calls.
    """
    from agent_platform.core.user import User
    from agent_platform.server.auth.handlers import AuthedUser
    from agent_platform.server.data_frames.semantic_data_model_collector import (
        SemanticDataModelCollector,
    )
    from server.tests.storage.sample_model_creator import SampleModelCreator

    model_creator = SampleModelCreator(sqlite_storage, tmpdir)
    await model_creator.setup()
    user_id = await model_creator.get_user_id()
    agent = await model_creator.obtain_sample_agent()
    thread = await model_creator.obtain_sample_thread()

    # Save semantic data model with unresolved file reference
    semantic_data_model_id = await sqlite_storage.set_semantic_data_model(
        semantic_data_model_id=None,
        semantic_model=SEMANTIC_DATA_MODEL_WITH_UNRESOLVED_FILE_REFERENCE,
        data_connection_ids=[],
        file_references=[],
    )

    await sqlite_storage.set_thread_semantic_data_models(
        thread_id=thread.thread_id,
        semantic_data_model_ids=[semantic_data_model_id],
    )

    from agent_platform.architectures.experimental.exp_1 import Exp1State

    state = Exp1State()

    # Critical assertion: verify state field is a dict with .get() method
    assert isinstance(state.empty_file_cache_key_to_matching_info, dict), (
        "empty_file_cache_key_to_matching_info must be a dict, not a FieldInfo descriptor"
    )
    assert hasattr(state.empty_file_cache_key_to_matching_info, "get"), (
        "empty_file_cache_key_to_matching_info must have .get() method"
    )

    collector = SemanticDataModelCollector(
        agent_id=agent.agent_id,
        thread_id=thread.thread_id,
        user=typing.cast(AuthedUser, User(user_id=user_id, sub="")),
        state=state,
    )

    # This would previously fail with AttributeError: 'FieldInfo' object has no attribute 'get'
    # if the field was defined using field(default_factory=dict) without @dataclass
    collected = await collector.collect_semantic_data_models(storage=sqlite_storage)

    # Should return empty list since no matching file exists
    assert len(collected) == 0, "Should not collect semantic data model without matching file"

    # Verify the cache dict is still accessible and empty
    assert state.empty_file_cache_key_to_matching_info == {}, "Cache should remain empty dict"
