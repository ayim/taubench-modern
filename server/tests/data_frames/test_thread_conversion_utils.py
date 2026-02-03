"""Tests for thread_conversion_utils.py - specifically testing SDM-file relationship detection."""

import pytest

from server.tests.storage_fixtures import *  # noqa: F403


@pytest.mark.asyncio
async def test_get_related_to_semantic_data_model_name_returns_sdm_name_for_file_in_thread(
    sqlite_storage, tmpdir
) -> None:
    """Test that _get_related_to_semantic_data_model_name returns the SDM name when
    a file in the thread matches an SDM's table columns.

    This test verifies that when:
    1. A file exists in a thread with specific columns
    2. An SDM exists with a logical table whose columns match the file
    3. The SDM has an unresolved (empty) file reference

    Then the function correctly:
    - Uses the collector to resolve the file reference
    - Returns the SDM name when the file_ref matches
    """
    from agent_platform.core.agent_architectures.thread_conversion_utils import (
        _get_related_to_semantic_data_model_name,
    )
    from agent_platform.core.semantic_data_model.types import SemanticDataModel
    from server.tests.storage.sample_model_creator import SampleModelCreator

    storage = sqlite_storage
    sample_model_creator = SampleModelCreator(storage, tmpdir)

    # Create the agent and thread
    sample_agent = await sample_model_creator.obtain_sample_agent()
    # Thread is created implicitly when we create files (via obtain_sample_file)
    await sample_model_creator.obtain_sample_thread()

    # Create a CSV file with specific columns (name, age)
    file_content = b"""name,age
John,25
Jane,30
Jim,35
"""
    sample_file = await sample_model_creator.obtain_sample_file(
        file_content=file_content, file_name="people.csv", mime_type="text/csv"
    )

    # Create an SDM with a logical table that has columns matching the file
    # The file_reference is intentionally unresolved (empty dict) - the collector should resolve it
    sdm_name = "People Data Model"
    semantic_model = SemanticDataModel.model_validate(
        {
            "name": sdm_name,
            "description": "A semantic data model for people data",
            "tables": [
                {
                    "name": "people_table",
                    "description": "People data from uploaded file",
                    "base_table": {
                        "table": "people_table",
                        # Note: {} is falsy in Python, so we need a non-empty dict to trigger detection
                        # Use a dummy sheet_name to make the dict truthy while missing thread_id/file_ref
                        # (can't use None because exclude_none=True removes it)
                        "file_reference": {"sheet_name": "Sheet1"},
                    },
                    "dimensions": [
                        {"name": "name", "expr": "name", "data_type": "TEXT"},
                    ],
                    "facts": [
                        {"name": "age", "expr": "age", "data_type": "NUMBER"},
                    ],
                }
            ],
        }
    )

    # Store the SDM and associate it with the agent
    sdm_id = await storage.set_semantic_data_model(
        semantic_data_model_id=None,
        semantic_model=semantic_model,
        data_connection_ids=[],
        file_references=[],
    )
    await storage.set_agent_semantic_data_models(sample_agent.agent_id, [sdm_id])

    # Create a kernel with the required properties
    kernel = await sample_model_creator.create_agent_server_kernel()

    # Call the function under test
    result = await _get_related_to_semantic_data_model_name(kernel, sample_file)

    # The function should return the SDM name since the file matches the SDM's table columns
    assert result == sdm_name


@pytest.mark.asyncio
async def test_get_related_to_semantic_data_model_name_returns_none_when_no_matching_sdm(
    sqlite_storage, tmpdir
) -> None:
    """Test that _get_related_to_semantic_data_model_name returns None when
    no SDM matches the file.
    """
    from agent_platform.core.agent_architectures.thread_conversion_utils import (
        _get_related_to_semantic_data_model_name,
    )
    from server.tests.storage.sample_model_creator import SampleModelCreator

    storage = sqlite_storage
    sample_model_creator = SampleModelCreator(storage, tmpdir)

    # Create the agent and thread
    await sample_model_creator.obtain_sample_agent()
    await sample_model_creator.obtain_sample_thread()

    # Create a CSV file with specific columns
    file_content = b"""product,price
Widget,10.99
Gadget,25.50
"""
    sample_file = await sample_model_creator.obtain_sample_file(
        file_content=file_content, file_name="products.csv", mime_type="text/csv"
    )

    # No SDM created - there's nothing to match against

    # Create a kernel with the required properties
    kernel = await sample_model_creator.create_agent_server_kernel()

    # Call the function under test
    result = await _get_related_to_semantic_data_model_name(kernel, sample_file)

    # The function should return None since there's no matching SDM
    assert result is None


@pytest.mark.asyncio
async def test_get_related_to_semantic_data_model_name_returns_none_when_columns_dont_match(
    sqlite_storage, tmpdir
) -> None:
    """Test that _get_related_to_semantic_data_model_name returns None when
    an SDM exists but its columns don't match the file's columns.
    """
    from agent_platform.core.agent_architectures.thread_conversion_utils import (
        _get_related_to_semantic_data_model_name,
    )
    from agent_platform.core.semantic_data_model.types import SemanticDataModel
    from server.tests.storage.sample_model_creator import SampleModelCreator

    storage = sqlite_storage
    sample_model_creator = SampleModelCreator(storage, tmpdir)

    # Create the agent and thread
    sample_agent = await sample_model_creator.obtain_sample_agent()
    await sample_model_creator.obtain_sample_thread()

    # Create a CSV file with columns: product, price
    file_content = b"""product,price
Widget,10.99
Gadget,25.50
"""
    sample_file = await sample_model_creator.obtain_sample_file(
        file_content=file_content, file_name="products.csv", mime_type="text/csv"
    )

    # Create an SDM with columns that DON'T match the file (name, age vs product, price)
    # The file_reference is intentionally unresolved (empty dict)
    semantic_model = SemanticDataModel.model_validate(
        {
            "name": "People Data Model",
            "description": "A semantic data model for people data",
            "tables": [
                {
                    "name": "people_table",
                    "description": "People data",
                    "base_table": {
                        "table": "people_table",
                        # Note: {} is falsy in Python, so we need a non-empty dict to trigger detection
                        # Use a dummy sheet_name to make the dict truthy while missing thread_id/file_ref
                        # (can't use None because exclude_none=True removes it)
                        "file_reference": {"sheet_name": "Sheet1"},
                    },
                    "dimensions": [
                        {"name": "name", "expr": "name", "data_type": "TEXT"},
                    ],
                    "facts": [
                        {"name": "age", "expr": "age", "data_type": "NUMBER"},
                    ],
                }
            ],
        }
    )

    sdm_id = await storage.set_semantic_data_model(
        semantic_data_model_id=None,
        semantic_model=semantic_model,
        data_connection_ids=[],
        file_references=[],
    )
    await storage.set_agent_semantic_data_models(sample_agent.agent_id, [sdm_id])

    # Create a kernel with the required properties
    kernel = await sample_model_creator.create_agent_server_kernel()

    # Call the function under test
    result = await _get_related_to_semantic_data_model_name(kernel, sample_file)

    # The function should return None since the columns don't match
    assert result is None


@pytest.mark.asyncio
async def test_get_related_to_semantic_data_model_name_with_resolved_file_reference(sqlite_storage, tmpdir) -> None:
    """Test that _get_related_to_semantic_data_model_name returns the SDM name when
    the SDM already has a resolved file_reference matching the file.
    """
    from agent_platform.core.agent_architectures.thread_conversion_utils import (
        _get_related_to_semantic_data_model_name,
    )
    from agent_platform.core.semantic_data_model.types import SemanticDataModel
    from server.tests.storage.sample_model_creator import SampleModelCreator

    storage = sqlite_storage
    sample_model_creator = SampleModelCreator(storage, tmpdir)

    # Create the agent and thread
    sample_agent = await sample_model_creator.obtain_sample_agent()
    sample_thread = await sample_model_creator.obtain_sample_thread()

    # Create a CSV file
    file_content = b"""name,age
John,25
Jane,30
"""
    sample_file = await sample_model_creator.obtain_sample_file(
        file_content=file_content, file_name="people.csv", mime_type="text/csv"
    )

    # Create an SDM with a pre-resolved file_reference
    sdm_name = "People Data Model With Ref"
    semantic_model: SemanticDataModel = SemanticDataModel.model_validate(
        {
            "name": sdm_name,
            "description": "A semantic data model with resolved file reference",
            "tables": [
                {
                    "name": "people_table",
                    "description": "People data from uploaded file",
                    "base_table": {
                        "table": "people_table",
                        "file_reference": {
                            "thread_id": sample_thread.thread_id,
                            "file_ref": sample_file.file_ref,
                        },
                    },
                    "dimensions": [
                        {"name": "name", "expr": "name", "data_type": "TEXT"},
                    ],
                    "facts": [
                        {"name": "age", "expr": "age", "data_type": "NUMBER"},
                    ],
                }
            ],
        }
    )

    sdm_id = await storage.set_semantic_data_model(
        semantic_data_model_id=None,
        semantic_model=semantic_model,
        data_connection_ids=[],
        file_references=[
            (sample_thread.thread_id, sample_file.file_ref),
        ],
    )
    await storage.set_agent_semantic_data_models(sample_agent.agent_id, [sdm_id])

    # Create a kernel with the required properties
    kernel = await sample_model_creator.create_agent_server_kernel()

    # Call the function under test
    result = await _get_related_to_semantic_data_model_name(kernel, sample_file)

    # The function should return the SDM name since the file_ref matches directly
    assert result == sdm_name
