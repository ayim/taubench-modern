import base64
import json
import os
import tempfile
from pathlib import Path

import pytest
from sema4ai.actions._action import set_current_requests_contexts
from sema4ai.actions._action_context import InvocationContext, RequestContexts

from sema4ai_docint.services.persistence.file import (
    ActionsChatFileAccessor,
)


@pytest.mark.asyncio
class TestChatFileAccessor:
    @pytest.mark.parametrize("storage_type", ["url", "directory"])
    async def test_file_crud_operations(self, agent_server_cli, thread_id, storage_type):
        # Configure the thread_id in the current_requests_contexts singleton
        data = json.dumps({"thread_id": thread_id})
        invocation_context = InvocationContext(data=base64.b64encode(data.encode()).decode())
        request_contexts = RequestContexts(request=None)
        request_contexts._invocation_context = invocation_context
        set_current_requests_contexts(request_contexts)

        # Set up storage based on parameterization
        if storage_type == "url":
            # Use the agent server URL
            os.environ["SEMA4AI_FILE_MANAGEMENT_URL"] = (
                f"http://localhost:{agent_server_cli.get_http_port()}/api/v2"
            )
            temp_dir = None
        elif storage_type == "directory":
            # Create a temporary directory for local file storage
            temp_dir = tempfile.mkdtemp()
            # Use file:// URI scheme for local directory
            os.environ["SEMA4AI_FILE_MANAGEMENT_URL"] = f"file://{temp_dir}"

        try:
            accessor = ActionsChatFileAccessor()

            # List the files
            files = await accessor.list()
            assert len(files) == 0, "Expected no files in the thread"

            # Write a file
            await accessor.write_text("test_file.txt", b"Hello, world!")

            # List the files again
            files = await accessor.list()
            assert len(files) == 1, "Expected one file in the thread"
            assert files[0] == "test_file.txt", "Expected file to be named test_file.txt"

            # Read the file
            content = await accessor.read_text("test_file.txt")
            assert content == b"Hello, world!", "Expected file content to be 'Hello, world!'"
        finally:
            # Clean up temporary directory if created
            if temp_dir and Path(temp_dir).exists():
                import shutil

                shutil.rmtree(temp_dir)
