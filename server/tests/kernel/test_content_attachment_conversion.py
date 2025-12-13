from __future__ import annotations

import typing

import pytest

from agent_platform.core.thread.content.attachment import ThreadAttachmentContent
from server.tests.storage_fixtures import *  # noqa: F403

if typing.TYPE_CHECKING:
    from pathlib import Path

    from pytest_regressions.file_regression import FileRegressionFixture

    from agent_platform.server.storage.sqlite import SQLiteStorage


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scenario",
    [
        "semantic_data_model_matching",
        "data_frames_enabled",
        "data_frames_disabled",
        "pdf_file",
        "no_specific_instructions",
        "multi_data_frames",
    ],
)
@pytest.mark.parametrize(
    "is_work_item_attachment",
    [
        True,
        False,
    ],
)
async def test_thread_attachment_content_as_text_content_with_description(
    sqlite_storage: SQLiteStorage,
    tmp_path: Path,
    file_regression: FileRegressionFixture,
    scenario: str,
    is_work_item_attachment: bool,
    monkeypatch: pytest.MonkeyPatch,
):
    import json

    from agent_platform.architectures.experimental.exp_1 import Exp1State
    from agent_platform.core.agent_architectures.thread_conversion_utils import (
        user_thread_contents_to_prompt_contents,
    )
    from agent_platform.core.files.mime_types import MIME_TYPE_XLSX
    from server.tests.storage.sample_model_creator import SampleModelCreator

    storage = sqlite_storage

    model_creator = SampleModelCreator(storage, tmp_path)
    thread = await model_creator.obtain_sample_thread()

    owner = None
    if is_work_item_attachment:
        owner = await model_creator.create_work_item()

    if scenario == "multi_data_frames":
        test_data_path = Path(__file__).parent.parent / "data_frames" / "test_file_data_readers"
        file = test_data_path / "sample.xlsx"
        file_content = file.read_bytes()
        sample_file = await model_creator.obtain_sample_file(
            file_content=file_content,
            file_name="sample.xlsx",
            mime_type=MIME_TYPE_XLSX,
        )

    elif scenario in (
        "data_frames_enabled",
        "data_frames_disabled",
        "semantic_data_model_matching",
    ):
        sample_file = await model_creator.obtain_sample_file(
            file_content=b"Name,Age\nJohn,30\nJane,25",
            file_name="test.csv",
            mime_type="text/csv",
            owner=owner,
        )
        if scenario == "semantic_data_model_matching":
            # We need to create a semantic data model with the file reference
            await model_creator.obtain_sample_semantic_data_model(
                semantic_model={
                    "name": "test_semantic_model",
                    "description": "A test semantic model",
                    "tables": [
                        {
                            "name": "test_table",
                            "description": "A table referencing the name and age.",
                            "base_table": {
                                "file_reference": {
                                    "thread_id": thread.thread_id,
                                    "file_ref": sample_file.file_ref,
                                    "sheet_name": None,
                                },
                            },
                        },
                    ],
                },
            )

        if scenario == "data_frames_disabled":
            monkeypatch.setenv("SEMA4AI_AGENT_SERVER_ENABLE_DATA_FRAMES", "0")

    elif scenario == "pdf_file":
        sample_file = await model_creator.obtain_sample_file(
            file_content=b"pdf-content-here",
            file_name="test.pdf",
            mime_type="application/pdf",
            owner=owner,
        )
    elif scenario == "no_specific_instructions":
        sample_file = await model_creator.obtain_sample_file(
            file_content=b"no-specific-instructions-content-here",
            file_name="test.txt",
            mime_type="text/plain",
            owner=owner,
        )
    else:
        raise ValueError(f"Invalid scenario: {scenario}")

    file_id = sample_file.file_id

    content = ThreadAttachmentContent(
        name=sample_file.file_ref,
        mime_type=sample_file.mime_type,
        # That's what the UI does for description:
        # https://github.com/Sema4AI/agent-platform/blob/main/workroom/spar-ui/src/queries/threads.ts#L210
        description="1kb",
        uri=f"agent-server-file://{file_id}",
    )

    kernel = await model_creator.create_agent_server_kernel()
    state = Exp1State()
    await kernel.data_frames.step_initialize(state=state, storage=storage)
    contents = await user_thread_contents_to_prompt_contents(kernel, [content], state=state)
    as_json = [content.model_dump() for content in contents]
    as_str = json.dumps(as_json, indent=2)
    as_str = as_str.replace("\\n", "\n")

    assert len(state.attachment_id_to_attachment_text_cache) == 1

    generated = f"""
Scenario: {scenario}

Generated prompt contents:
{as_str}
"""
    file_regression.check(generated)
