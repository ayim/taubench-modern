# ruff: noqa: E501, C901
import typing
from typing import Annotated, Protocol

from structlog.stdlib import get_logger

if typing.TYPE_CHECKING:
    from agent_platform.core.files.files import UploadedFile
    from agent_platform.core.kernel import Kernel
    from agent_platform.core.prompts import UserPromptMessageContent
    from agent_platform.core.thread.base import AnyThreadMessageContent
    from agent_platform.core.thread.content.attachment import ThreadAttachmentContent

logger = get_logger(__name__)


class ThreadConversionState(Protocol):
    """Protocol for the architecture state required for
    converting thread content to prompt content."""

    attachment_id_to_attachment_text_cache: Annotated[
        dict[str, str], "A cache of attachment IDs to attachment text."
    ]


async def _get_file_details(
    kernel: "Kernel",
    attachment_content: "ThreadAttachmentContent",
) -> "UploadedFile | None":
    """Gets the name and ref of a file from an attachment content."""
    if not attachment_content.uri:
        return None
    file_id = attachment_content.uri.replace("agent-server-file://", "")
    file_details = await kernel.files.get_file_by_id(file_id)
    if not file_details:
        return None
    return file_details


async def user_thread_contents_to_prompt_contents(
    kernel: "Kernel",
    contents: "list[AnyThreadMessageContent]",
    state: ThreadConversionState | None = None,
) -> "list[UserPromptMessageContent]":
    """Converts a list of thread contents to a list of prompt contents.

    Arguments:
        kernel: The kernel instance.
        contents: The list of thread contents to convert.
        state: The thread conversion state (if given we may automatically
               extract data frames and nudge the agent prompt on how to
               handle pdfs/csv etc on file uploads).
    """

    from agent_platform.core.prompts.content.text import PromptTextContent
    from agent_platform.core.thread.content.attachment import ThreadAttachmentContent
    from agent_platform.core.thread.content.text import ThreadTextContent

    prompt_contents: list[UserPromptMessageContent] = []

    for content in contents:
        match content:
            case ThreadTextContent() as text_content:
                prompt_contents.append(
                    PromptTextContent(
                        text=text_content.text.strip(),
                    ),
                )
            case ThreadAttachmentContent() as attachment_content:
                if state is not None:
                    attachment_text = state.attachment_id_to_attachment_text_cache.get(
                        attachment_content.content_id
                    )
                    if attachment_text is not None:
                        prompt_contents.append(PromptTextContent(text=attachment_text))
                        continue

                file_details = await _get_file_details(kernel, attachment_content)
                if file_details is not None:
                    file_reference_text = (
                        f"Uploaded file. "
                        f"File name/reference: '{file_details.file_ref}', "
                        f"MIME type: '{file_details.mime_type}'"
                    )

                    final_text = file_reference_text

                    is_work_item_attachment = file_details.work_item_id is not None

                    # In a file upload, we'll actually try to guess the purpose of the file
                    # (and if possible even extract some information from it) and then
                    # ask the agent to do something based on that.
                    additional_text = await _build_prompt_from_user_uploaded_file(
                        kernel,
                        file_details,
                        state=state,
                        is_work_item_attachment=is_work_item_attachment,
                    )

                    if additional_text:
                        final_text = f"{file_reference_text}\n{additional_text}"

                    # Store the result in the cache
                    if state is not None:
                        state.attachment_id_to_attachment_text_cache[
                            attachment_content.content_id
                        ] = final_text
                    prompt_contents.append(PromptTextContent(text=final_text))

            # TODO: multi-modal content/docs
            case _:
                raise ValueError(f"Unsupported thread content kind: {content.kind}")

    return prompt_contents


async def _build_prompt_from_user_uploaded_file(  # noqa: PLR0911
    kernel: "Kernel",
    file_details: "UploadedFile",
    *,
    state: ThreadConversionState | None = None,
    is_work_item_attachment: bool = False,
) -> str:
    """Builds a prompt from a file."""
    from textwrap import dedent

    from agent_platform.core.files.mime_types import MIME_TYPE_PDF

    # Check if file is related to a semantic data model
    sdm_name = await _get_related_to_semantic_data_model_name(kernel, file_details)
    if sdm_name:
        if is_work_item_attachment:
            return dedent(
                f"""
                Note: this file is related to the semantic data model named '{sdm_name}'.
                Follow the runbook for instructions related to the semantic data model
                or uploaded files.
                """
            ).strip()
        else:
            return dedent(
                f"""
                Note: this file is related to the semantic data model named '{sdm_name}'.
                Follow the runbook if it has instructions related to the semantic data model
                or uploaded files, otherwise, do not call any tools at this point and present
                options asking the user what he wants to answer based on it.
                """
            ).strip()

    if file_details.mime_type == MIME_TYPE_PDF:
        if is_work_item_attachment:
            return dedent("""
                Note: This is a PDF file. Follow the runbook for instructions related to
                the PDF file or uploaded files.
                Note: remember that it's not possible to directly create a data frame from a PDF file.
                """).strip()
        else:
            return dedent("""
                Note: This is a PDF file. Follow the runbook if it has instructions related
                to the PDF file or uploaded files, otherwise, if you have tools related
                to PDF handling, present options to the user to process the file based on
                those tools (but try to avoid calling them at this moment).
                Note: remember that it's not possible to directly create a data frame from a PDF file.
                """).strip()

    if state is not None:
        # This would auto-create data frames if the data frames tools are enabled.
        # Only do it if the state is provided.
        data_frame_prompt = await kernel.data_frames.on_upload_file_build_prompt(
            file_details, is_work_item_attachment=is_work_item_attachment
        )
        if data_frame_prompt:
            return data_frame_prompt

    # No known way to process this file, use generic message.
    if is_work_item_attachment:
        return "Note: follow the runbook for instructions related to the uploaded file."
    else:
        return (
            "Note: follow the runbook if it has instructions\n"
            "related to the uploaded file, otherwise, ask what to do with this file."
        )


async def _get_related_to_semantic_data_model_name(
    kernel: "Kernel",
    file_details: "UploadedFile",
) -> str | None:
    """Check if a file is related to a semantic data model.
    Returns the semantic data model name if found, otherwise None."""
    from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel
    from agent_platform.server.storage.base import BaseStorage
    from agent_platform.server.storage.option import StorageService

    try:
        storage = StorageService.get_instance()
        # Get semantic data models for the thread
        semantic_data_models_info: list[
            BaseStorage.SemanticDataModelInfo
        ] = await storage.list_semantic_data_models(
            agent_id=kernel.agent.agent_id, thread_id=kernel.thread.thread_id
        )

        # Check if file_ref matches any file reference in semantic data models
        for sdm_info in semantic_data_models_info:
            semantic_data_model: SemanticDataModel = sdm_info["semantic_data_model"]
            tables = semantic_data_model.get("tables") or []
            for semantic_data_model_table in tables:
                base_table = semantic_data_model_table.get("base_table")
                if not base_table:
                    continue
                file_reference = base_table.get("file_reference")
                if not file_reference:
                    continue
                if file_reference.get("file_ref") == file_details.file_ref:
                    return semantic_data_model.get("name") or "'<unable to get name>'"

    except Exception:
        logger.exception("Error checking if file is related to semantic data model")

    return None
