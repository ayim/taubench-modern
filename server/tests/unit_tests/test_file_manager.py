import os
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Union
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest
from fastapi import UploadFile

from sema4ai_agent_server.file_manager.base import (
    BaseFileManager,
)
from sema4ai_agent_server.file_manager.cloud import CloudFileManager
from sema4ai_agent_server.file_manager.local import LocalFileManager
from sema4ai_agent_server.schema import (
    Agent,
    AgentArchitecture,
    Thread,
    UploadedFile,
    dummy_model,
)
from sema4ai_agent_server.storage.option import get_storage


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdirname:
        yield tmpdirname


@pytest.fixture
def mock_vectorstore():
    return Mock()


class MockStorage:
    def __init__(self):
        self.get_file = AsyncMock(return_value=None)
        self.get_file_by_id = AsyncMock()
        self.put_file_owner = AsyncMock()
        self.delete_file = AsyncMock()
        self.update_file = AsyncMock()
        self.update_file_retrieve_information = AsyncMock()


@pytest.fixture
def mock_requests():
    mock = MagicMock()
    mock.post.return_value.status_code = 204
    mock.get.return_value.status_code = 200
    mock.get.return_value.json.return_value = {"url": "https://example.com/file"}
    mock.delete.return_value.status_code = 200
    return mock


@pytest.fixture(params=[LocalFileManager, CloudFileManager])
def file_manager(request, temp_dir, mock_requests, mock_vectorstore):
    if request.param == LocalFileManager:
        manager = LocalFileManager(vectorstore=mock_vectorstore)
        manager.UPLOAD_DIR = temp_dir
    else:
        manager = CloudFileManager(vectorstore=mock_vectorstore)
        manager.FILE_MANAGEMENT_API_URL = "https://example.com/api"
        manager._get_presigned_post = MagicMock(
            return_value={
                "url": "https://example.com/upload",
                "form_data": {
                    "key": "test-file-key",
                    "AWSAccessKeyId": "test-access-key",
                    "policy": "test-policy",
                    "signature": "test-signature",
                },
            }
        )

        # Mock _get_presigned_url
        manager._get_presigned_url = MagicMock(
            return_value="https://example.com/download/test-file"
        )
        manager._delete_stored_file = AsyncMock()

    with patch("sema4ai_agent_server.file_manager.cloud.requests", mock_requests):
        yield manager


@pytest.fixture
def sample_file(temp_dir):
    file_content = b"test content"
    file_path = os.path.join(temp_dir, "test.txt")
    with open(file_path, "wb") as f:
        f.write(file_content)
    return UploadFile(filename="test.txt", file=open(file_path, "rb"))


@pytest.fixture
def sample_owner():
    return Agent(
        id=str(uuid4()),
        user_id=str(uuid4()),
        name="Test agent",
        description="Test agent Description",
        runbook="Test agent Runbook",
        config={},
        model=dummy_model,
        architecture=AgentArchitecture.AGENT,
        updated_at=datetime.now(timezone.utc),
        metadata=None,
    )


@pytest.fixture
def sample_uploaded_file(temp_dir):
    return UploadedFile(
        file_id=str(uuid4()),
        file_path=os.path.join(temp_dir, "test.txt"),
        file_ref="test.txt",
        file_hash="hash",
        embedded=True,
        file_path_expiration=datetime.now(timezone.utc) + timedelta(hours=1),
    )


@pytest.fixture
def mock_embed_runnable():
    with patch(
        "sema4ai_agent_server.file_manager.base.embed_runnable", autospec=True
    ) as mock:
        yield mock


@pytest.fixture
def mock_vstore():
    with patch("sema4ai_agent_server.file_manager.base.vstore", autospec=True) as mock:
        yield mock


@pytest.mark.asyncio
class TestFileManager:
    async def test_upload_success(
        self,
        file_manager: BaseFileManager,
        sample_file: UploadFile,
        sample_owner: Union[Agent, Thread],
        mock_embed_runnable: Mock,
        sample_uploaded_file: UploadedFile,
    ):
        mock_embed_runnable.invoke.return_value = {"embeddings": [0.1, 0.2, 0.3]}

        result = await file_manager.upload(sample_file, sample_owner)

        assert result.file_ref == sample_uploaded_file.file_ref
        mock_embed_runnable.invoke.assert_called_once()

    async def test_refresh_file_paths(
        self,
        file_manager: BaseFileManager,
        sample_uploaded_file: UploadedFile,
        sample_owner: Union[Agent, Thread],
    ):
        if not isinstance(file_manager, CloudFileManager):
            pytest.skip("refresh_file_paths is only relevant for CloudFileManager")

        expired_file = UploadedFile(
            **{
                **sample_uploaded_file.__dict__,
                "file_path_expiration": datetime.now(timezone.utc)
                - timedelta(minutes=5),
            }
        )
        valid_file = UploadedFile(
            **{
                **sample_uploaded_file.__dict__,
                "file_path_expiration": datetime.now(timezone.utc) + timedelta(hours=1),
            }
        )
        files = [expired_file, valid_file]

        await get_storage().put_file_owner(
            expired_file.file_id,
            expired_file.file_path,
            expired_file.file_ref,
            expired_file.file_hash,
            expired_file.embedded,
            sample_owner,
            expired_file.file_path_expiration,
        )
        refreshed_files = await file_manager.refresh_file_paths(files)

        assert refreshed_files[0].file_path == "https://example.com/download/test-file"
        assert refreshed_files[1].file_path == valid_file.file_path


if __name__ == "__main__":
    pytest.main()
