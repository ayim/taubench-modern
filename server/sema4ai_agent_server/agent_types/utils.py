"""
Provides tool binding methods that do not perform checks done by LangChain.

The default `bind_tools` methods provided by LangChain checks things like if a tool
choice of "auto" or "none" is provided with more than one tool at a time, which is
valid but for some reason throws an error in their implementation.

Other tools like the `pydantic_output_parser` method are available in this module.
"""

from typing import Any, Callable, Literal, Sequence, Type, TypeVar

from deprecated import deprecated
from langchain_anthropic import ChatAnthropic
from langchain_anthropic.output_parsers import ToolsOutputParser
from langchain_aws import ChatBedrockConverse
from langchain_core.language_models.base import LanguageModelInput
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AnyMessage,
    BaseMessage,
    FunctionMessage,
    HumanMessage,
)
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from langchain_google_vertexai import ChatVertexAI, PydanticFunctionsOutputParser
from langchain_openai import AzureChatOpenAI, ChatOpenAI
from langchain_openai.output_parsers import PydanticToolsParser
from pydantic import BaseModel

from sema4ai_agent_server.schema import (
    MODEL,
    Agent,
    AgentReasoning,
    AmazonBedrock,
    AnthropicClaude,
)

# Define supported agent types
AGENT_TYPES = (AzureChatOpenAI, ChatOpenAI, ChatAnthropic, ChatVertexAI)


def bind_tools_to_open_ai(
    llm: ChatOpenAI | AzureChatOpenAI,
    tools: Sequence[dict[str, Any] | type[BaseModel] | Type | Callable | BaseTool],
    *,
    tool_choice: dict
    | str
    | Literal["auto", "none", "required", "any"]
    | bool
    | None = None,
    strict: bool | None = None,
    **kwargs: Any,
) -> Runnable[LanguageModelInput, BaseMessage]:
    """Bind tool-like objects to this chat model.

    Assumes model is compatible with OpenAI tool-calling API.

    Duplicate of the `bind_tools` method for both OpenAI and AzuerChatOpenAI
    because the LangChain implementation of `bind_tools` for AzureChatOpenAI
    has not been updated to allow for `tool_choice="required"` or `tool_choice="any"`.

    Args:
        tools: A list of tool definitions to bind to this chat model.
            Can be  a dictionary, pydantic model, callable, or BaseTool. Pydantic
            models, callables, and BaseTools will be automatically converted to
            their schema dictionary representation.
        tool_choice: Which tool to require the model to call.
            Must be the name of a provided function or
            "auto" to automatically determine which function to call
            (if any), or a dict of the form:
            {"type": "function", "function": {"name": <<tool_name>>}}.
        **kwargs: Any additional parameters to pass to the
            :class:`~langchain.runnable.Runnable` constructor.
    """

    formatted_tools = [convert_to_openai_tool(tool, strict=strict) for tool in tools]
    if tool_choice:
        if isinstance(tool_choice, str):
            # tool_choice is a tool/function name
            if tool_choice not in ("auto", "none", "any", "required"):
                tool_choice = {
                    "type": "function",
                    "function": {"name": tool_choice},
                }
            # 'any' is not natively supported by OpenAI API.
            # We support 'any' since other models use this instead of 'required'.
            if tool_choice == "any":
                tool_choice = "required"
        elif isinstance(tool_choice, bool):
            tool_choice = "required"
        elif isinstance(tool_choice, dict):
            tool_names = [
                formatted_tool["function"]["name"] for formatted_tool in formatted_tools
            ]
            if not any(
                tool_name == tool_choice["function"]["name"] for tool_name in tool_names
            ):
                raise ValueError(
                    f"Tool choice {tool_choice} was specified, but the only "
                    f"provided tools were {tool_names}."
                )
        else:
            raise ValueError(
                f"Unrecognized tool_choice type. Expected str, bool or dict. "
                f"Received: {tool_choice}"
            )
        kwargs["tool_choice"] = tool_choice
    return llm.bind(tools=formatted_tools, **kwargs)


@deprecated
def bind_tools_to_anthropic(
    llm: ChatAnthropic,
    tools: Sequence[dict[str, Any] | type[BaseModel] | Callable | BaseTool],
    *,
    tool_choice: dict | str | Literal["auto", "none"] | bool | None = None,
    **kwargs: Any,
) -> Runnable[LanguageModelInput, BaseMessage]:
    """**Deprecated in favor of direct usage of `bind_tools` method.**

    Bind tool-like objects to this chat model.

    Allows tool choices while binding additional tools to the model.


    Args:
        tools: A list of tool definitions to bind to this chat model.
            Can be  a dictionary, pydantic model, callable, or BaseTool. Pydantic
            models, callables, and BaseTools will be automatically converted to
            their schema dictionary representation.
        tool_choice: Which tool to require the model to call.
            Must be the name of a provided function or
            "auto" to automatically determine which function to call
            (if any), or a dict of the form:
            {"type": "tool", "name": <<tool_name>>}.
        **kwargs: Any additional parameters to bind.

    Example:
        .. code-block:: python

            from langchain_anthropic import ChatAnthropic
            from pydantic import BaseModel, Field

            class GetWeather(BaseModel):
                '''Get the current weather in a given location'''

                location: str = Field(..., description="The city and state, e.g. San Francisco, CA")


            llm = ChatAnthropic(model="claude-3-opus-20240229", temperature=0)
            llm_with_tools = llm.bind_tools([GetWeather])
            llm_with_tools.invoke("what is the weather like in San Francisco",)
            # -> AIMessage(
            #     content=[
            #         {'text': '<thinking>\nBased on the user\'s question, the relevant function to call is GetWeather, which requires the "location" parameter.\n\nThe user has directly specified the location as "San Francisco". Since San Francisco is a well known city, I can reasonably infer they mean San Francisco, CA without needing the state specified.\n\nAll the required parameters are provided, so I can proceed with the API call.\n</thinking>', 'type': 'text'},
            #         {'text': None, 'type': 'tool_use', 'id': 'toolu_01SCgExKzQ7eqSkMHfygvYuu', 'name': 'GetWeather', 'input': {'location': 'San Francisco, CA'}}
            #     ],
            #     response_metadata={'id': 'msg_01GM3zQtoFv8jGQMW7abLnhi', 'model': 'claude-3-opus-20240229', 'stop_reason': 'tool_use', 'stop_sequence': None, 'usage': {'input_tokens': 487, 'output_tokens': 145}},
            #     id='run-87b1331e-9251-4a68-acef-f0a018b639cc-0'
            # )
    """  # noqa: E501
    return llm.bind_tools(tools, tool_choice=tool_choice, **kwargs)


@deprecated
def bind_tools_to_vertex(
    llm: ChatVertexAI,
    tools: Sequence[dict[str, Any] | type[BaseModel] | Callable | BaseTool],
    *,
    tool_choice: dict | str | Literal["auto", "none"] | bool | None = None,
    **kwargs: Any,
) -> Runnable[LanguageModelInput, BaseMessage]:
    """**Deprecated in favor of direct usage of `bind_tools` method, which
    includes support for ToolConfig objects.**

    Bind tool-like objects to this chat model.

    Assumes model is compatible with Vertex tool-calling API. Allows tool choices
    while binding additional tools to the model.

    Args:
        tools: A list of tool definitions to bind to this chat model.
            Can be a pydantic model, callable, or BaseTool. Pydantic
            models, callables, and BaseTools will be automatically converted to
            their schema dictionary representation.
        tool_choice: Which tool(s) to require the model to call.
            Must be the name of a provided function, a list of names, or
            "auto" to automatically determine which function to call
            (if any). Will be ignored if model is not an advanced model.
        **kwargs: Any additional parameters to pass to the
            :class:`~langchain.runnable.Runnable` constructor.
    """

    return llm.bind_tools(tools, tool_choice=tool_choice, **kwargs)


def bind_tools(
    llm: BaseChatModel,
    tools: Sequence[dict[str, Any] | type[BaseModel] | Type | Callable | BaseTool],
    *,
    tool_choice: dict
    | str
    | Literal["auto", "none", "required", "any"]
    | bool
    | None = None,
    **kwargs: Any,
) -> Runnable[LanguageModelInput, BaseMessage]:
    """Convenience method to bind tools to a chat model.

    For Vertex models, you may want to bind directly if using ToolConfig.
    """
    if isinstance(llm, (ChatOpenAI, AzureChatOpenAI)):
        return bind_tools_to_open_ai(llm, tools, tool_choice=tool_choice, **kwargs)
    elif isinstance(llm, ChatAnthropic):
        return llm.bind_tools(tools, tool_choice=tool_choice, **kwargs)
    elif isinstance(llm, ChatVertexAI):
        return llm.bind_tools(tools, tool_choice=tool_choice, **kwargs)
    elif isinstance(llm, ChatBedrockConverse):
        if isinstance(tool_choice, str) and tool_choice.lower() == "none":
            tool_choice = None
        return llm.bind_tools(tools, tool_choice=tool_choice, **kwargs)
    else:
        raise TypeError(f"Unsupported agent type: {type(llm)}")


M = TypeVar("M", bound=BaseModel)


def get_pydantic_output_parser(
    llm: BaseChatModel, schema: type[BaseModel]
) -> PydanticToolsParser | ToolsOutputParser | PydanticFunctionsOutputParser:
    if isinstance(llm, (ChatOpenAI, AzureChatOpenAI)):
        return PydanticToolsParser(first_tool_only=True, tools=[schema])
    if isinstance(llm, ChatAnthropic):
        return ToolsOutputParser(first_tool_only=True, pydantic_schemas=[schema])
    if isinstance(llm, ChatVertexAI):
        return PydanticFunctionsOutputParser(
            first_tool_only=True, pydantic_schemas=[schema]
        )


def clean_message(message: AnyMessage):
    """Sanitizes a message by converting certain types to an appropriate type.

    For example, this method converts a LiberalToolMessage type to ToolMessage type.
    """
    if isinstance(message, FunctionMessage):
        # anthropic doesn't like function messages
        return HumanMessage(content=str(message.content))
    else:
        return message


def get_messages(
    messages: list[AnyMessage], model: MODEL, *, continue_string="continue"
) -> list[AnyMessage]:
    """Sanitizes a message list by converting certain types to an
    appropriate type.

    For example, this method converts all LiberalToolMessage types to
    ToolMessage types.
    """
    # TODO: Consider fixing conversation for AmazonBedrock so that it properly has turns...
    sanitized_msgs = [clean_message(m) for m in messages]
    if isinstance(model, (AmazonBedrock)):
        # check if the first message is human, as that is required by bedrock
        if not isinstance(sanitized_msgs[0], HumanMessage):
            sanitized_msgs = [HumanMessage(content="Hi")] + sanitized_msgs

    if is_claude(model):
        # check if the first message is human, as that is required by bedrock
        if not isinstance(sanitized_msgs[0], HumanMessage):
            sanitized_msgs = [HumanMessage(content="Hi")] + sanitized_msgs
        # Check that any groups of similar message types are separated by a human message
        # to prevent LangChain from combining them, which doens't work with our metadata
        new_msgs = []
        for i, msg in enumerate(sanitized_msgs):
            if i > 0 and type(msg) is type(sanitized_msgs[i - 1]):
                new_msgs.append(HumanMessage(content=continue_string))
            new_msgs.append(msg)
        sanitized_msgs = new_msgs

    return sanitized_msgs


def format_knowledge_files(files: list[str]) -> str:
    """Format a list of knowledge files into a prompt-injectable string."""
    if files:
        file_list = "\n".join(f"- {file}" for file in files)
        return f"You have access to the following knowledge files:\n{file_list}"
    return ""


def is_claude(model: MODEL) -> bool:
    """Check if the model is a Claude model."""
    return (
        isinstance(model, (AnthropicClaude, AmazonBedrock)) and "claude" in model.name
    )


def is_reasoning(agent: Agent, level: AgentReasoning | None = None) -> bool:
    """Helper function to check if an agent is reasoning and at what
    level if desired. This is primarily used to reduce the number of
    checks for reasoning in the codebase.

    Args:
        agent: The agent to check reasoning for.
        level: The level of reasoning to check for. If None, it will
            check if the agent is reasoning at all.
    """
    if level is not None:
        return agent.advanced_config.reasoning == level
    else:
        return agent.advanced_config.reasoning != AgentReasoning.DISABLED
