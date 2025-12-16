"""Direct kernel transport for document intelligence.

This module provides DirectKernelTransport, which implements the DirectTransport
protocol for direct access to agent-server's internal storage and file management
services, bypassing HTTP overhead.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from sema4ai_docint.agent_server_client.transport.direct import DirectTransport

from agent_platform.core.context import AgentServerContext
from agent_platform.core.payloads.prompts_generate import PromptsGeneratePayload
from agent_platform.server.file_manager.utils import url_to_fs_path

if TYPE_CHECKING:
    from sema4ai_docint.agent_server_client.transport.base import ResponseMessage

    from agent_platform.server.file_manager import BaseFileManager
    from agent_platform.server.storage import BaseStorage

logger = logging.getLogger(__name__)


class DirectKernelTransport(DirectTransport):
    """Direct kernel transport implementing DirectTransport protocol.

    This transport provides direct access to agent-server's internal storage
    and file management services, avoiding HTTP overhead.
    """

    def __init__(
        self,
        storage: "BaseStorage",
        file_manager: "BaseFileManager",
        thread_id: str,
        agent_id: str,
        user_id: str,
        server_context: AgentServerContext,
    ):
        self._thread_id = thread_id
        self._agent_id = agent_id
        self._storage = storage
        self._file_manager = file_manager
        self._user_id = user_id
        self._server_context = server_context

    @property
    def thread_id(self) -> str:
        return self._thread_id

    @property
    def agent_id(self) -> str:
        return self._agent_id

    async def prompts_generate(self, payload: PromptsGeneratePayload) -> "ResponseMessage":
        """Generate a prompt response using the agent server.

        Uses the shared prompts service for generation, avoiding HTTP overhead.

        Args:
            payload: The prompt payload containing:
                - platform_config: Optional platform config (fetched from agent if missing)
                - model: Optional model name
                - model_type: Model type (default: "llm")

        Returns:
            ResponseMessage: The generated response
        """
        from agent_platform.core.prompts import Prompt
        from agent_platform.server.services.prompts_service import (
            convert_core_response_to_transport,
            generate_prompt_response,
        )

        # Parse prompt from payload
        if "prompt" not in payload:
            raise ValueError("Payload missing 'prompt' field")

        prompt_data = payload["prompt"]
        if isinstance(prompt_data, Prompt):
            prompt = prompt_data
        elif isinstance(prompt_data, dict):
            prompt = Prompt.model_validate(prompt_data)
        else:
            raise ValueError(f"Invalid prompt type: {type(prompt_data)}")

        # Get platform config - fetch from agent if not provided in payload
        platform_config = payload.get("platform_config")
        if not platform_config:
            platform_config = (
                (await self._storage.get_agent(self._user_id, self._agent_id)).platform_configs[0].model_dump()
            )

        model = payload.get("model")
        model_type = payload.get("model_type", "llm")

        core_response = await generate_prompt_response(
            prompt=prompt,
            platform_config_raw=platform_config,
            server_context=self._server_context,
            model=model,
            model_type=model_type,
            agent_id=self._agent_id,
            thread_id=self._thread_id,
        )
        return convert_core_response_to_transport(core_response)

    async def get_file(self, name: str, thread_id: str | None = None) -> Path:
        """Get a file from storage by reference.

        This provides direct access to files via the file manager, bypassing
        the HTTP API entirely.

        Args:
            name: The file reference/name to retrieve
            thread_id: Optional thread ID (uses transport's thread_id if not provided)

        Returns:
            Path: The path to the file

        Raises:
            FileNotFoundError: If the thread or file is not found
        """
        tid = thread_id or self._thread_id

        thread = await self._storage.get_thread(self._user_id, tid)
        if not thread:
            raise FileNotFoundError(f"Thread {tid} not found")

        file = await self._storage.get_file_by_ref(thread, name, self._user_id)
        if not file:
            raise FileNotFoundError(f"File {name} not found in thread {tid}")

        if not file.file_path:
            raise FileNotFoundError(f"File {name} has no file_path")

        # Convert file:// URI to filesystem path, decoding URL-encoded characters
        fs_path = url_to_fs_path(file.file_path)
        return Path(fs_path)

    async def upload_file_bytes(
        self,
        *,
        thread_id: str,
        file_ref: str,
        content: bytes,
        mime_type: str = "text/plain",
    ) -> None:
        """Upload file bytes into a thread using agent-server's internal file manager.

        This mirrors the behavior of POST /threads/{tid}/files (validation + storage)
        but avoids HTTP overhead.
        """
        from io import BytesIO

        from fastapi import UploadFile

        from agent_platform.core.payloads import UploadFilePayload

        thread = await self._storage.get_thread(self._user_id, thread_id)
        if not thread:
            raise FileNotFoundError(f"Thread {thread_id} not found")

        # FastAPI/Starlette UploadFile is sufficient for our file_manager codepath:
        # it reads from `.file` and uses `.filename`.
        upload = UploadFile(filename=file_ref, file=BytesIO(content), headers=None)
        _ = mime_type  # mime_type is currently inferred by file_manager; keep for API completeness.

        await self._file_manager.upload([UploadFilePayload(file=upload)], thread, self._user_id)

    async def list_file_refs(self, *, thread_id: str) -> list[str]:
        """List file refs for a thread using internal storage."""
        thread = await self._storage.get_thread(self._user_id, thread_id)
        if not thread:
            return []

        files = await self._storage.get_thread_files(thread_id, self._user_id)
        return [f.file_ref for f in files]

    async def get_file_url(self, *, thread_id: str, file_ref: str) -> str | None:
        """Return a file URL/URI for a given file_ref in a thread."""
        thread = await self._storage.get_thread(self._user_id, thread_id)
        if not thread:
            return None

        file = await self._storage.get_file_by_ref(thread, file_ref, self._user_id)
        if not file:
            return None

        refreshed = await self._file_manager.refresh_file_paths([file])
        if not refreshed:
            return None

        # UploadedFile.file_url is set to file_path in __post_init__ in core.
        return refreshed[0].file_url or refreshed[0].file_path
