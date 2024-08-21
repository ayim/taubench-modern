from typing import Any, Callable, Literal, Sequence, TypeVar

from langchain_anthropic import ChatAnthropic
from langchain_anthropic.chat_models import convert_to_anthropic_tool
from langchain_anthropic.output_parsers import ToolsOutputParser
from langchain_core.language_models.base import LanguageModelInput
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.pydantic_v1 import BaseModel
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langchain_core.tools import tool as tool_from_callable
from langchain_core.utils.function_calling import convert_to_openai_tool
from langchain_google_vertexai import ChatVertexAI, PydanticFunctionsOutputParser
from langchain_openai import AzureChatOpenAI, ChatOpenAI
from langchain_openai.output_parsers import PydanticToolsParser
from vertexai.generative_models._generative_models import ToolConfig

# Define supported agent types
AGENT_TYPES = (AzureChatOpenAI, ChatOpenAI, ChatAnthropic, ChatVertexAI)


def bind_tools_to_open_ai(
    llm: ChatOpenAI | AzureChatOpenAI,
    tools: Sequence[dict[str, Any] | type[BaseModel] | Callable | BaseTool],
    *,
    tool_choice: dict | str | Literal["auto", "none"] | bool | None = None,
    **kwargs: Any,
) -> Runnable[LanguageModelInput, BaseMessage]:
    """Bind tool-like objects to this chat model.

    Assumes model is compatible with OpenAI tool-calling API.

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

    formatted_tools = [convert_to_openai_tool(tool) for tool in tools]
    if tool_choice is not None and tool_choice:
        if isinstance(tool_choice, str):
            if tool_choice not in ("auto", "none"):
                tool_choice = {
                    "type": "function",
                    "function": {"name": tool_choice},
                }
        elif isinstance(tool_choice, bool):
            tool_choice = {
                "type": "function",
                "function": {"name": formatted_tools[0]["function"]["name"]},
            }
        elif isinstance(tool_choice, dict):
            if tool_choice["function"]["name"] not in [
                tool["function"]["name"] for tool in formatted_tools
            ]:
                raise ValueError(
                    f"Tool choice {tool_choice} was specified, but the only "
                    f"provided tools were {[tool['function']['name'] for tool in formatted_tools]}."
                )
        else:
            raise ValueError(
                f"Unrecognized tool_choice type. Expected str, bool or dict. "
                f"Received: {tool_choice}"
            )
        kwargs["tool_choice"] = tool_choice
    return llm.bind(tools=formatted_tools, **kwargs)


def bind_tools_to_anthropic(
    llm: ChatAnthropic,
    tools: Sequence[dict[str, Any] | type[BaseModel] | Callable | BaseTool],
    *,
    tool_choice: dict | str | Literal["auto", "none"] | bool | None = None,
    **kwargs: Any,
) -> Runnable[LanguageModelInput, BaseMessage]:
    """Bind tool-like objects to this chat model.

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
            from langchain_core.pydantic_v1 import BaseModel, Field

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
    formatted_tools = [convert_to_anthropic_tool(tool) for tool in tools]
    if tool_choice is not None and tool_choice:
        if isinstance(tool_choice, str):
            if tool_choice not in ("auto", "none"):
                tool_choice = {
                    "type": "tool",
                    "name": tool_choice,
                }
        elif isinstance(tool_choice, bool):
            tool_choice = {
                "type": "tool",
                "name": formatted_tools[0]["name"],
            }
        elif isinstance(tool_choice, dict):
            if tool_choice["name"] not in [tool["name"] for tool in formatted_tools]:
                raise ValueError(
                    f"Tool choice {tool_choice} was specified, but the only "
                    f"provided tools were {[tool['name'] for tool in formatted_tools]}."
                )
        else:
            raise ValueError(
                f"Unrecognized tool_choice type. Expected str, bool or dict. "
                f"Received: {tool_choice}"
            )
        kwargs["tool_choice"] = tool_choice
    return llm.bind(tools=formatted_tools, **kwargs)


def bind_tools_to_vertex(
    llm: ChatVertexAI,
    tools: Sequence[dict[str, Any] | type[BaseModel] | Callable | BaseTool],
    *,
    tool_choice: dict | str | Literal["auto", "none"] | bool | None = None,
    **kwargs: Any,
) -> Runnable[LanguageModelInput, BaseMessage]:
    """Bind tool-like objects to this chat model.

    Assumes model is compatible with Vertex tool-calling API.

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
    formatted_tools = []
    for schema in tools:
        if isinstance(schema, BaseTool) or (
            isinstance(schema, type) and issubclass(schema, BaseModel)
        ):
            formatted_tools.append(schema)
        elif callable(schema):
            formatted_tools.append(tool_from_callable(schema))  # type: ignore
        else:
            raise ValueError("Tool must be a BaseTool, Pydantic model, or callable.")

    if tool_choice is not None and tool_choice and llm._is_gemini_advanced:
        if isinstance(tool_choice, (str, list)):
            if tool_choice not in ("auto", "none"):
                if isinstance(tool_choice, str):
                    tool_choice = [tool_choice]
                tool_config = {
                    "function_calling_config": {
                        "mode": ToolConfig.FunctionCallingConfig.Mode.ANY,
                        "allowed_function_names": tool_choice,
                    }
                }
        elif isinstance(tool_choice, bool):
            try:
                name = formatted_tools[0]["name"]
            except (KeyError, TypeError):
                try:
                    name = formatted_tools[0].name
                except AttributeError:
                    name = formatted_tools[0].__name__
            tool_config = {
                "function_calling_config": {
                    "mode": ToolConfig.FunctionCallingConfig.Mode.ANY,
                    "allowed_function_names": [name],
                }
            }
        else:
            raise ValueError(
                f"Unrecognized tool_choice type. Expected str or bool. "
                f"Received: {tool_choice}"
            )
        kwargs["tool_config"] = tool_config

    return llm.bind(functions=formatted_tools, **kwargs)


def bind_tools(
    llm: BaseChatModel,
    tools: Sequence[dict[str, Any] | type[BaseModel] | Callable | BaseTool],
    *,
    tool_choice: dict | str | Literal["auto", "none"] | bool | None = None,
    **kwargs: Any,
) -> Runnable[LanguageModelInput, BaseMessage]:
    if isinstance(llm, (ChatOpenAI, AzureChatOpenAI)):
        return bind_tools_to_open_ai(llm, tools, tool_choice=tool_choice, **kwargs)
    elif isinstance(llm, ChatAnthropic):
        return bind_tools_to_anthropic(llm, tools, tool_choice=tool_choice, **kwargs)
    elif isinstance(llm, ChatVertexAI):
        return bind_tools_to_vertex(llm, tools, tool_choice=tool_choice, **kwargs)
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
