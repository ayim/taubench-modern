"""Robocorp Action Server toolkit."""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional, TypedDict
from urllib.parse import urljoin

import requests
import structlog
from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.callbacks.manager import CallbackManager
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig, RunnablePassthrough
from langchain_core.tools import BaseTool, StructuredTool, Tool
from langchain_core.tracers.context import _tracing_v2_is_enabled
from langsmith import Client
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    create_model,
    field_validator,
)
from pydantic_core import to_jsonable_python

from sema4ai_agent_server.action_server._common import (
    get_param_fields,
    reduce_openapi_spec,
)
from sema4ai_agent_server.action_server._prompts import (
    API_CONTROLLER_PROMPT,
)

logger = structlog.get_logger(__name__)

LLM_TRACE_HEADER = "X-action-trace"


class RunDetailsCallbackHandler(BaseCallbackHandler):
    """Callback handler to add run details to the run."""

    def __init__(self, run_details: dict) -> None:
        """Initialize the callback handler.

        Args:
            run_details (dict): Run details.
        """
        self.run_details = run_details

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        **kwargs: Any,
    ) -> None:
        if "parent_run_id" in kwargs:
            self.run_details["run_id"] = kwargs["parent_run_id"]
        else:
            if "run_id" in self.run_details:
                self.run_details.pop("run_id")


class ToolInputSchema(BaseModel):
    """Tool input schema."""

    question: str = Field(...)


class ToolArgs(TypedDict):
    """Tool arguments."""

    name: str
    description: str
    callback_manager: CallbackManager


class ActionServerRequestTool(BaseTool):
    """Requests POST tool with LLM-instructed extraction of truncated responses."""

    name: str = "action_server_request"
    """Tool name."""
    description: str = "Useful to make requests to Action Server API"
    """Tool description."""
    endpoint: str
    """"Action API endpoint"""
    action_request: Callable[[str], str]
    """Action request execution"""

    def _run(
        self, query: str, run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        try:
            json_text = query[query.find("{") : query.rfind("}") + 1]
            payload = json.loads(json_text)

        except json.JSONDecodeError as e:
            raise e

        return self.action_request(self.endpoint, **payload["data"])

    async def _arun(self, text: str) -> str:
        raise NotImplementedError()


class ActionServerToolkit(BaseModel):
    """Toolkit exposing Robocorp Action Server provided actions as individual tools."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    url: str = Field(exclude=True)
    """Action Server URL"""
    api_key: str = Field(exclude=True, default="")
    """Action Server request API key"""
    additional_headers: dict = Field(exclude=True, default_factory=dict)
    """Additional headers to be passed to the Action Server"""
    report_trace: bool = Field(exclude=True, default=False)
    """Enable reporting Langsmith trace to Action Server runs"""
    _run_details: dict = PrivateAttr({})

    @field_validator("url")
    @classmethod
    def append_trailing_slash(cls, v: str) -> str:
        """Ensures that the url ends with a /."""
        # Action server url may not be a base url in the cloud environment.
        # It may be something like https://example.com/foo/bar. If the url
        # does not end with a /, urljoin will drop the last path component.
        # So "bar" will be dropped and replaced with whatever we are joining.
        if v and not v.endswith("/"):
            return v + "/"
        return v

    def get_tools(
        self,
        llm: Optional[BaseChatModel] = None,
        callback_manager: Optional[CallbackManager] = None,
    ) -> List[BaseTool]:
        """
        Get Action Server actions as a toolkit

        :param llm: Optionally pass a model to return single input tools
        :param callback_manager: Callback manager to be passed to tools
        """

        spec_url = urljoin(self.url, "openapi.json")
        try:
            response = requests.get(spec_url)
        except Exception:
            logger.exception(f"Failed to fetch OpenAPI schema - {spec_url}")
            raise ValueError(f"Failed to fetch OpenAPI schema - {spec_url}")

        if response.status_code != 200:
            logger.error(f"status code: {response.status_code}")
            logger.error(f"response: {response.text}")
            raise ValueError(f"Unexpected response from Action Server - {spec_url}")

        try:
            api_spec = reduce_openapi_spec(self.url, response.json())
        except Exception:
            logger.exception("Failed to reduce OpenAPI schema from Action Server")
            raise ValueError("Failed to reduce OpenAPI schema from Action Server")

        # Prepare request tools
        self._run_details: dict = {}

        # Prepare callback manager
        if callback_manager is None:
            callback_manager = CallbackManager([])
        callbacks: List[BaseCallbackHandler] = []

        if _tracing_v2_is_enabled():
            callbacks.append(RunDetailsCallbackHandler(self._run_details))

        for callback in callbacks:
            callback_manager.add_handler(callback)

        toolkit: List[BaseTool] = []

        # Prepare tools
        for endpoint, docs in api_spec.endpoints:
            if not endpoint.startswith("/api/actions"):
                continue

            tool_args: ToolArgs = {
                "name": docs["operationId"],
                "description": docs["description"],
                "callback_manager": callback_manager,
            }

            if llm:
                tool = self._get_unstructured_tool(endpoint, docs, tool_args, llm)
            else:
                tool = self._get_structured_tool(endpoint, docs, tool_args)

            toolkit.append(tool)

        return toolkit

    def _get_unstructured_tool(
        self,
        endpoint: str,
        docs: dict,
        tool_args: ToolArgs,
        llm: BaseChatModel,
    ) -> BaseTool:
        request_tool = ActionServerRequestTool(
            action_request=self._action_request, endpoint=endpoint
        )

        prompt_variables = {
            "api_url": self.url,
        }

        tool_name = tool_args["name"]
        tool_docs = json.dumps(docs, indent=4)
        prompt_variables["api_docs"] = f"{tool_name}: \n{tool_docs}"

        prompt = PromptTemplate(
            template=API_CONTROLLER_PROMPT,
            input_variables=["input"],
            partial_variables=prompt_variables,
        )

        chain: Runnable = (
            {"input": RunnablePassthrough()}
            | prompt
            | llm
            | StrOutputParser()
            | request_tool
        )

        return Tool(func=chain.invoke, args_schema=ToolInputSchema, **tool_args)

    def _get_structured_tool(
        self, endpoint: str, docs: dict, tools_args: ToolArgs
    ) -> BaseTool:
        fields = get_param_fields(docs)
        _DynamicToolInputSchema = create_model("DynamicToolInputSchema", **fields)

        def dynamic_func(*args: Any, _config: RunnableConfig, **kwargs: Any) -> str:
            tool_call_id = _config.get("configurable", {}).get("tool_call_id")
            return self._action_request(
                endpoint, tool_call_id, **to_jsonable_python(kwargs)
            )

        dynamic_func.__name__ = tools_args["name"]
        dynamic_func.__doc__ = tools_args["description"]

        return StructuredTool(
            func=dynamic_func,
            args_schema=_DynamicToolInputSchema,
            **tools_args,
        )

    def _action_request(
        self, endpoint: str, tool_call_id: Optional[str] = None, **data: dict[str, Any]
    ) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            **self.additional_headers,
        }
        if tool_call_id is not None:
            headers["x-action_invocation_id"] = tool_call_id

        try:
            if self.report_trace and "run_id" in self._run_details:
                client = Client()
                run = client.read_run(self._run_details["run_id"])
                if run.url:
                    headers[LLM_TRACE_HEADER] = run.url
        except Exception:
            pass

        url = self._get_endpoint_root_url(endpoint)

        response = requests.post(url, headers=headers, data=json.dumps(data))

        return response.text

    def _get_endpoint_root_url(self, endpoint: str) -> str:
        # Without lstrip("/"), if self.url contains a path (e.g. https://example.com/foo/bar/),
        # it gets overwritten by the endpoint (foo/bar gets lost).
        # self.url will always end with a /, ensured by the validator.
        return urljoin(self.url, endpoint.lstrip("/"))
