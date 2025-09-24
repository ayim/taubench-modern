"""Unit tests for the OpenAI platform converters."""

import base64
from unittest.mock import MagicMock

import pytest

from agent_platform.core.errors.base import PlatformHTTPError
from agent_platform.core.kernel import Kernel
from agent_platform.core.platforms.openai.converters import OpenAIConverters
from agent_platform.core.platforms.openai.prompts import OpenAIPrompt
from agent_platform.core.prompts import (
    Prompt,
    PromptDocumentContent,
    PromptImageContent,
    PromptTextContent,
    PromptToolResultContent,
    PromptToolUseContent,
    PromptUserMessage,
)
from agent_platform.core.tools.tool_definition import ToolDefinition


class TestOpenAIConverters:
    """Test converters for OpenAI."""

    @pytest.fixture
    def converters(self) -> OpenAIConverters:
        """Create a converter instance for testing."""
        return OpenAIConverters()

    @pytest.fixture
    def kernel(self) -> Kernel:
        """Create a kernel instance for testing."""
        return MagicMock(spec=Kernel)

    @pytest.mark.asyncio
    async def test_convert_text_content(self, converters: OpenAIConverters) -> None:
        """Test converting text content."""
        content = PromptTextContent(text="Hello, world!")
        result = await converters.convert_text_content(content)

        assert isinstance(result, dict)
        assert result.get("type") == "input_text"
        assert result.get("text") == "Hello, world!"

    @pytest.mark.asyncio
    async def test_convert_image_content_url(
        self,
        converters: OpenAIConverters,
    ) -> None:
        """Test converting image content."""

        result = await converters.convert_image_content(
            PromptImageContent(
                mime_type="image/png",
                sub_type="url",
                value="https://example.com/image.png",
                detail="high_res",
            )
        )
        assert isinstance(result, dict)
        assert result.get("type") == "input_image"
        assert result.get("detail") == "high"
        image_url = result.get("image_url")
        assert isinstance(image_url, str)
        assert image_url == "https://example.com/image.png"

    @pytest.mark.asyncio
    async def test_convert_image_content_b64(
        self,
        converters: OpenAIConverters,
        b64_image_prompt_content: PromptImageContent,
    ) -> None:
        """Test converting image content."""

        result = await converters.convert_image_content(b64_image_prompt_content)
        assert isinstance(result, dict)
        assert result.get("type") == "input_image"
        image_url = result.get("image_url")
        assert isinstance(image_url, str)
        assert image_url.startswith("data:image/png;base64,")

    @pytest.mark.asyncio
    async def test_convert_tool_use_content(self, converters: OpenAIConverters) -> None:
        """Test converting tool use content."""
        content = PromptToolUseContent(
            tool_call_id="test-tool-call-id",
            tool_name="test-tool",
            tool_input_raw='{"key": "value"}',
        )
        result = await converters.convert_tool_use_content(content)

        assert result.get("type") == "function_call"
        assert result.get("call_id") == "test-tool-call-id"
        assert result.get("name") == "test-tool"

    @pytest.mark.asyncio
    async def test_convert_prompt(
        self,
        converters: OpenAIConverters,
        kernel: Kernel,
    ) -> None:
        """Test converting a prompt."""
        prompt = Prompt(
            system_instruction="You are a helpful assistant.",
            messages=[
                PromptUserMessage([PromptTextContent(text="Hello, world!")]),
            ],
        )
        finalized_prompt = await prompt.finalize_messages(kernel)
        result = await converters.convert_prompt(finalized_prompt, model_id="gpt-4o")

        assert isinstance(result, OpenAIPrompt)
        assert result.instructions == "You are a helpful assistant."
        assert result.input is not None
        assert len(result.input) == 1

        user_msg = result.input[0]
        assert isinstance(user_msg, dict)
        assert user_msg.get("role") == "user"
        content_list = user_msg.get("content")
        assert isinstance(content_list, list)
        assert len(content_list) == 1
        first_part = content_list[0]
        assert isinstance(first_part, dict)
        assert first_part.get("type") == "input_text"
        assert first_part.get("text") == "Hello, world!"

    @pytest.mark.asyncio
    async def test_convert_prompt_o4_mini(
        self,
        converters: OpenAIConverters,
        kernel: Kernel,
    ) -> None:
        """Test converting a prompt."""
        prompt = Prompt(
            system_instruction="You are a helpful assistant.",
            messages=[
                PromptUserMessage([PromptTextContent(text="Hello, world!")]),
            ],
        )
        finalized_prompt = await prompt.finalize_messages(kernel)
        result = await converters.convert_prompt(
            finalized_prompt,
            model_id="o4-mini",
        )

        assert isinstance(result, OpenAIPrompt)
        # With Responses API, system instructions are provided via `instructions`
        assert result.instructions == "You are a helpful assistant."
        assert result.input is not None
        assert len(result.input) == 1
        user_msg = result.input[0]
        assert isinstance(user_msg, dict)
        assert user_msg.get("role") == "user"
        content_list = user_msg.get("content")
        assert isinstance(content_list, list)
        assert len(content_list) == 1
        first_part = content_list[0]
        assert isinstance(first_part, dict)
        assert first_part.get("type") == "input_text"
        assert first_part.get("text") == "Hello, world!"

    @pytest.mark.asyncio
    async def test_convert_prompt_with_tools(
        self,
        converters: OpenAIConverters,
        kernel: Kernel,
    ) -> None:
        """Test converting a prompt with tools."""
        tool = ToolDefinition(
            name="test-tool",
            description="A test tool",
            input_schema={
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "A test key",
                    },
                },
                "required": ["key"],
            },
            function=lambda key: key,
        )
        prompt = Prompt(
            system_instruction="You are a helpful assistant.",
            messages=[
                PromptUserMessage([PromptTextContent(text="Hello, world!")]),
            ],
            tools=[tool],
        )
        finalized_prompt = await prompt.finalize_messages(kernel)
        result = await converters.convert_prompt(finalized_prompt, model_id="gpt-4o")

        assert isinstance(result, OpenAIPrompt)
        assert result.tools is not None
        assert len(result.tools) == 1

        tool_obj = result.tools[0]
        assert tool_obj.get("type") == "function"
        assert tool_obj.get("name") == "test-tool"

    @pytest.mark.asyncio
    async def test_convert_document_content(
        self,
        converters: OpenAIConverters,
    ) -> None:
        """Test converting document content."""
        pdf_bytes = b"%PDF-1.5 test"
        base64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
        document = PromptDocumentContent(
            mime_type="application/pdf",
            value=base64_pdf,
            name="report.pdf",
            sub_type="base64",
        )

        result = await converters.convert_document_content(document)

        assert result.get("type") == "input_file"
        assert result.get("filename") == "report.pdf"
        assert result.get("file_data") == f"data:application/pdf;base64,{base64_pdf}"

    @pytest.mark.asyncio
    async def test_convert_document_content_bytes(
        self,
        converters: OpenAIConverters,
    ) -> None:
        """Test converting document content."""
        pdf_bytes = b"%PDF-1.5 test"
        # Convert to base64 so we can verify it later
        base64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")

        document = PromptDocumentContent(
            mime_type="text/plain",
            value=pdf_bytes,
            name="report.pdf",
            sub_type="raw_bytes",
        )

        result = await converters.convert_document_content(document)

        assert result.get("type") == "input_file"
        assert result.get("filename") == "report.pdf"
        assert result.get("file_data") == f"data:text/plain;base64,{base64_pdf}"

    @pytest.mark.asyncio
    async def test_convert_document_content_url(
        self,
        converters: OpenAIConverters,
    ) -> None:
        """Test converting document content."""
        import httpx

        try:
            response = httpx.get("https://cdn.sema4.ai/gallery/actions/browsing/1.3.3/README.md")
            response.raise_for_status()
        except httpx.HTTPError:
            pytest.skip("Failed to download README.md")

        print(response.text)
        base64_content = base64.b64encode(response.text.encode("utf-8")).decode("utf-8")
        print(base64_content)

        document = PromptDocumentContent(
            mime_type="text/plain",
            value="https://cdn.sema4.ai/gallery/actions/browsing/1.3.3/README.md",
            name="README.md",
            sub_type="url",
        )

        result = await converters.convert_document_content(document)

        assert result.get("type") == "input_file"
        assert result.get("filename") == "README.md"
        assert result.get("file_data") == f"data:text/plain;base64,{base64_content}"

    @pytest.mark.asyncio
    async def test_convert_prompt_with_document(
        self,
        converters: OpenAIConverters,
        kernel: Kernel,
    ) -> None:
        """Ensure document content is passed through to the OpenAI request."""
        pdf_bytes = b"%PDF-1.5 test"
        base64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
        prompt = Prompt(
            messages=[
                PromptUserMessage(
                    [
                        PromptDocumentContent(
                            mime_type="application/pdf",
                            value=base64_pdf,
                            name="report.pdf",
                            sub_type="base64",
                        )
                    ]
                )
            ],
        )

        finalized_prompt = await prompt.finalize_messages(kernel)
        result = await converters.convert_prompt(finalized_prompt, model_id="gpt-4.1")

        assert result.input is not None
        assert len(result.input) == 1
        user_msg = result.input[0]
        content: list[dict] = user_msg.get("content", [])  # type: ignore
        assert any(part.get("type") == "input_file" for part in content)

    @pytest.mark.asyncio
    async def test_convert_tool_result_content(
        self,
        converters: OpenAIConverters,
    ) -> None:
        """Test converting tool result content."""
        content = PromptToolResultContent(
            tool_call_id="test-tool-call-id",
            tool_name="test-tool",
            content=[PromptTextContent(text="Hello, world!")],
        )
        result = await converters.convert_tool_result_content(content)

        assert isinstance(result, dict)
        assert result.get("type") == "function_call_output"
        assert result.get("call_id") == "test-tool-call-id"
        assert result.get("output") == "Hello, world!"

    @pytest.mark.asyncio
    async def test_convert_prompt_with_no_messages(
        self,
        converters: OpenAIConverters,
        kernel: Kernel,
    ) -> None:
        """Test converting a prompt with no messages."""
        prompt = Prompt(
            system_instruction="You are a helpful assistant.",
            messages=[],
        )
        finalized_prompt = await prompt.finalize_messages(kernel)
        result = await converters.convert_prompt(finalized_prompt, model_id="gpt-4o")

        assert isinstance(result, OpenAIPrompt)
        assert isinstance(result.input, list)
        assert len(result.input) == 0
        assert result.instructions == "You are a helpful assistant."

    @pytest.mark.asyncio
    async def test_convert_prompt_with_no_system_instruction(
        self,
        converters: OpenAIConverters,
        kernel: Kernel,
    ) -> None:
        """Test converting a prompt with no system instruction."""
        prompt = Prompt(
            messages=[
                PromptUserMessage([PromptTextContent(text="Hello, world!")]),
            ],
        )
        finalized_prompt = await prompt.finalize_messages(kernel)
        result = await converters.convert_prompt(finalized_prompt, model_id="gpt-4o")

        assert isinstance(result, OpenAIPrompt)
        assert isinstance(result.input, list)
        assert len(result.input) == 1
        user_msg = result.input[0]
        assert isinstance(user_msg, dict)
        assert user_msg.get("role") == "user"
        content_list = user_msg.get("content")
        assert isinstance(content_list, list)
        assert len(content_list) == 1
        first_part = content_list[0]
        assert isinstance(first_part, dict)
        assert first_part.get("type") == "input_text"
        assert first_part.get("text") == "Hello, world!"
        assert result.instructions is None

    @pytest.mark.asyncio
    async def test_tool_conversion(self, converters: OpenAIConverters) -> None:
        """Test converting tools."""
        tool = ToolDefinition(
            name="test-tool",
            description="A test tool",
            input_schema={"type": "object"},
            function=lambda: None,
        )

        tools = await converters._convert_tools([tool])
        assert len(tools) == 1

        tool_obj = tools[0]
        assert tool_obj.get("type") == "function"
        assert tool_obj.get("name") == "test-tool"
        assert tool_obj.get("description") == "A test tool"
        parameters = tool_obj.get("parameters")
        assert isinstance(parameters, dict)
        assert parameters.get("type") == "object"

    @pytest.mark.asyncio
    async def test_system_instruction_conversion(
        self,
        converters: OpenAIConverters,
        kernel: Kernel,
    ) -> None:
        """Test system instruction handling via Responses API prompt fields."""
        # With instruction
        prompt = Prompt(
            system_instruction="Test instruction",
            messages=[PromptUserMessage([PromptTextContent(text="Hi")])],
        )
        finalized = await prompt.finalize_messages(kernel)
        converted = await converters.convert_prompt(finalized, model_id="gpt-4o")
        assert converted.instructions == "Test instruction"

        # Without instruction
        prompt2 = Prompt(messages=[PromptUserMessage([PromptTextContent(text="Hi")])])
        finalized2 = await prompt2.finalize_messages(kernel)
        converted2 = await converters.convert_prompt(finalized2, model_id="gpt-4o")
        assert converted2.instructions is None

        # o1-mini retains instructions in `instructions`
        prompt3 = Prompt(
            system_instruction="Test instruction",
            messages=[PromptUserMessage([PromptTextContent(text="Hi")])],
        )
        finalized3 = await prompt3.finalize_messages(kernel)
        converted3 = await converters.convert_prompt(finalized3, model_id="o1-mini-2024-07-18")
        assert converted3.instructions == "Test instruction"

    @pytest.mark.asyncio
    async def test_process_user_message_content(
        self,
        converters: OpenAIConverters,
    ) -> None:
        """Test processing user message content for Responses API."""
        # Text only
        text_content = [PromptTextContent(text="Hello, world!")]
        result, tool_results = await converters._process_user_message_content(text_content)
        assert len(result) == 1
        assert result[0].get("type") == "input_text"
        assert result[0].get("text") == "Hello, world!"
        assert len(tool_results) == 0

        # Text and tool result (tool outputs follow the message as separate items)
        mixed_content = [
            PromptTextContent(text="Hello, world!"),
            PromptToolResultContent(
                tool_call_id="test-id",
                tool_name="test-tool",
                content=[PromptTextContent(text="ok")],
            ),
        ]
        result, tool_results = await converters._process_user_message_content(mixed_content)
        assert len(result) == 1
        assert result[0].get("type") == "input_text"
        assert result[0].get("text") == "Hello, world!"
        assert len(tool_results) == 1
        assert tool_results[0].get("type") == "function_call_output"

    @pytest.mark.asyncio
    async def test_check_file_size(self) -> None:
        """Test checking file size."""
        # 1KB of "base64 encoded" data, well below the 1MB limit
        test_data = "a" * 1024
        OpenAIConverters._check_file_size("application/pdf", test_data, limit_mb=1)

        # 1MB of "base64 encoded" data, would exceed the 1MB limit (1024 * 1024 *1.5)
        test_data = "a" * 1024 * 1535
        with pytest.raises(PlatformHTTPError):
            OpenAIConverters._check_file_size("application/pdf", test_data, limit_mb=1)
