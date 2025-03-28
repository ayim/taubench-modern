"""Module contains custom responses and related for the FastAPI application."""

from typing import Any, Mapping

from fastapi import BackgroundTasks
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel, TypeAdapter


class PydanticResponse(ORJSONResponse):
    """Custom response that uses Pydantic to serialize data to JSON and
    orjson as a fallback.

    Note: The Pydantic method will only be used if this class is returned
    directly from the path operation function. You should define the
    response_model for documentation purposes and return this response. In
    such a case, FastAPI's automatic JSON serialization will be bypassed.

    Example usage in a path operation:

    ```python
    from sema4ai_agent_server.responses import PydanticResponse

    @app.get("/agent/{aid}", response_model=Agent, response_class=PydanticResponse)
    async def get_agent(aid: int):
        agent = await storage().get_agent(aid)
        return PydanticResponse(agent)
    ```
    """

    def __init__(
        self,
        content: BaseModel,
        ser_context: dict[str, Any] = None,
        *,
        status_code: int = 200,
        headers: Mapping[str, str] | None = None,
        media_type: str | None = None,
        background: BackgroundTasks | None = None,
    ):
        self.ser_context = ser_context
        super().__init__(
            content,
            status_code=status_code,
            headers=headers,
            media_type=media_type,
            background=background,
        )

    def render(self, content: Any) -> bytes:
        if hasattr(content, "model_dump_json"):
            return content.model_dump_json(context=self.ser_context).encode("utf-8")
        else:
            return super().render(content)


class TypeAdapterResponse(ORJSONResponse):
    """Custom response that uses a Pydantic type adapter to serialize data to
    JSON and orjson as a fallback.

    Note: The TypeAdapter method will only be used if this class is returned
    directly from the path operation function. You should define the
    response_model for documentation purposes and return this response. In
    such a case, FastAPI's automatic JSON serialization will be bypassed.

    Example usage in a path operation:

    ```python
    from sema4ai_agent_server.responses import TypeAdapterResponse
    from sema4ai_agent_server.type_adapters import AGENT_LIST_ADAPTER

    @app.get("/agents", response_model=List[Agent], response_class=TypeAdapterResponse)
    async def get_agents():
        agents = await storage().list_all_agents()
        return TypeAdapterResponse(agents, adapter=AGENT_LIST_ADAPTER)
    ```
    """

    def __init__(
        self,
        content: Any,
        adapter: Any,
        ser_context: dict[str, Any] | None = None,
        *,
        status_code: int = 200,
        headers: Mapping[str, str] | None = None,
        media_type: str | None = None,
        background: BackgroundTasks | None = None,
    ):
        self.adapter: TypeAdapter = adapter
        self.ser_context = ser_context
        super().__init__(
            content,
            status_code=status_code,
            headers=headers,
            media_type=media_type,
            background=background,
        )

    def render(self, content: Any) -> bytes:
        try:
            return self.adapter.dump_json(content, context=self.ser_context)
        except Exception:
            return super().render(content)
