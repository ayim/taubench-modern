import asyncio
import json
import logging
from collections import defaultdict
from collections.abc import AsyncGenerator, Awaitable, Callable
from copy import deepcopy
from dataclasses import dataclass, field
from functools import lru_cache
from logging import getLogger
from typing import TYPE_CHECKING, Any, ClassVar, TypeVar

from httpx import AsyncClient as HTTPXAsyncClient
from httpx import HTTPStatusError, Response, Timeout, codes

from agent_platform.core.configurations import Configuration
from agent_platform.core.configurations.base import FieldMetadata
from agent_platform.core.delta import GenericDelta
from agent_platform.core.delta.compute_delta import compute_generic_deltas
from agent_platform.core.errors import ErrorCode, PlatformHTTPError
from agent_platform.core.platforms.base import (
    PlatformClient,
)
from agent_platform.core.platforms.configs import (
    PlatformModelConfigs,
    resolve_generic_model_id_to_platform_specific_model_id,
)
from agent_platform.core.platforms.cortex.converters import CortexConverters
from agent_platform.core.platforms.cortex.parameters import (
    CortexPlatformParameters,
)
from agent_platform.core.platforms.cortex.parsers import CortexParsers
from agent_platform.core.platforms.cortex.prompts import CortexPrompt
from agent_platform.core.responses.response import ResponseMessage
from agent_platform.core.utils.httpx_client import init_httpx_client

T = TypeVar("T")


if TYPE_CHECKING:
    from snowflake.snowpark import Session

    from agent_platform.core.kernel import Kernel


logger = getLogger(__name__)


class _SessionRefreshRequiredError(Exception):
    """Signal that the Snowflake session should be refreshed."""


DEFAULT_SNOWFLAKE_MODELS = {
    "anthropic": [
        "claude-3-5-sonnet",
        "claude-3-7-sonnet",
        "claude-4-opus",
        "claude-4-1-opus",
        "calude-4-sonnet",
        "calude-4-5-sonnet",
    ],
    "openai": [
        "openai-gpt-5",
        "openai-gpt-5-mini",
        "openai-o4-mini",
        "openai-gpt-4.1",
    ],
}


@dataclass(frozen=True)
class CortexRetryConfiguration(Configuration):
    """A configuration for the Cortex platform."""

    total: int = field(
        default=7,
        metadata=FieldMetadata(
            description="The maximum number of retries to attempt.",
        ),
    )

    backoff_factor: float = field(
        default=2.0,
        metadata=FieldMetadata(
            description="The initial delay between retries.",
        ),
    )

    backoff_max: float = field(
        default=300.0,
        metadata=FieldMetadata(
            description="The maximum delay between retries.",
        ),
    )

    # We want to retry 500 here... Cortex is a bad provider and
    # randomly throws 500s. (So let's retry to be more resilient.)
    status_forcelist: list[int] = field(
        default_factory=lambda: [429, 500, 502, 503, 504],
        metadata=FieldMetadata(
            description="The HTTP status codes that can be retried.",
        ),
    )
    timeout_seconds: float = field(
        default=300.0,
        metadata=FieldMetadata(
            description="The timeout for the Cortex platform.",
        ),
    )


class CortexClient(
    PlatformClient[
        CortexConverters,
        CortexParsers,
        CortexPlatformParameters,
        CortexPrompt,
    ],
):
    """A client for the Cortex platform."""

    NAME: ClassVar[str] = "cortex"
    _GLOBAL_AVAILABLE_MODELS_CACHE: ClassVar[dict[str, list[str]]] = {}
    _GLOBAL_AVAILABLE_MODELS_LOCK: ClassVar[asyncio.Lock] = asyncio.Lock()
    _RETRY_CONFIGURATION: ClassVar[CortexRetryConfiguration] = CortexRetryConfiguration()
    _DEFAULT_TIMEOUT_S: ClassVar[float] = _RETRY_CONFIGURATION.timeout_seconds
    _MAX_RETRY_ATTEMPTS: ClassVar[int] = _RETRY_CONFIGURATION.total
    _BACKOFF_BASE_S: ClassVar[float] = _RETRY_CONFIGURATION.backoff_factor
    _BACKOFF_MAX_S: ClassVar[float] = _RETRY_CONFIGURATION.backoff_max
    _RETRYABLE_STATUS: ClassVar[set[int]] = set(_RETRY_CONFIGURATION.status_forcelist)
    _UNAUTHORIZED_STATUS: ClassVar[set[int]] = {codes.UNAUTHORIZED, codes.FORBIDDEN}

    def __init__(
        self,
        *,
        kernel: "Kernel | None" = None,
        parameters: CortexPlatformParameters | None = None,
        **kwargs: Any,
    ):
        super().__init__(
            kernel=kernel,
            parameters=parameters,
            **kwargs,
        )
        self._cortex_runtime_session: Session | None = None
        self._session_lock: asyncio.Lock = asyncio.Lock()
        self._available_models_cache: dict[str, list[str]] = {}

    def _log_debug_payload(self, label: str, payload: Any) -> None:
        """Emit payload details when debug logging is enabled."""
        if not logger.isEnabledFor(logging.DEBUG):
            return

        if isinstance(payload, str):
            formatted_payload = payload
        else:
            try:
                formatted_payload = json.dumps(payload, indent=2, sort_keys=True)
            except (TypeError, ValueError):
                formatted_payload = repr(payload)

        logger.debug(f"Cortex {label}:\n{formatted_payload}")

    async def _read_error_detail(self, response: Response) -> Any:
        """Best-effort decode of an error payload for logging and surfacing."""
        try:
            body = await response.aread()
            text = body.decode()
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text
        except Exception as exc:  # pragma: no cover - logging safety
            return f"(Failed to read error response body: {exc})"

    async def _call_with_retries(
        self,
        call: Callable[[], Awaitable[T]],
        *,
        context: str,
    ) -> T:
        from agent_platform.core.platforms.retry import build_httpx_retry_decorator

        retry_deco = build_httpx_retry_decorator(
            logger=logger,
            provider_name="Cortex",
            context=context,
            max_attempts=self._MAX_RETRY_ATTEMPTS,
            base_backoff_s=self._BACKOFF_BASE_S,
            max_backoff_s=self._BACKOFF_MAX_S,
            retryable_status=self._RETRYABLE_STATUS,
        )

        @retry_deco
        async def _inner() -> T:
            return await call()

        try:
            return await _inner()
        except HTTPStatusError as exc:
            self._raise_platform_http_error(exc, context=context)
            raise  # pragma: no cover - _raise_platform_http_error always raises

    def _raise_platform_http_error(
        self,
        exc: HTTPStatusError,
        *,
        context: str,
    ) -> None:
        """Normalize HTTP errors from Cortex into PlatformHTTPError instances."""
        status_code = exc.response.status_code or 0
        request_id = exc.response.headers.get("x-snowflake-request-id")
        retry_after = exc.response.headers.get("retry-after")

        error_data: dict[str, Any] = {
            "status_code": status_code,
            "context": context,
        }
        if request_id:
            error_data["request_id"] = request_id
        if retry_after:
            error_data["retry_after"] = retry_after

        if status_code in self._UNAUTHORIZED_STATUS:
            raise PlatformHTTPError(
                error_code=ErrorCode.UNAUTHORIZED,
                message=(
                    "Cortex authentication failed or session token expired. "
                    "Please verify your Snowflake credentials."
                ),
                data=error_data,
            ) from exc

        if status_code == codes.TOO_MANY_REQUESTS:
            raise PlatformHTTPError(
                error_code=ErrorCode.TOO_MANY_REQUESTS,
                message=("Cortex rate limit reached. Please wait a moment and try again."),
                data=error_data,
            ) from exc

        if codes.is_server_error(status_code):
            raise PlatformHTTPError(
                error_code=ErrorCode.UNEXPECTED,
                message=(
                    "Cortex temporarily failed to process the request. Please try again shortly."
                ),
                data=error_data,
            ) from exc

        raise PlatformHTTPError(
            error_code=ErrorCode.UNEXPECTED,
            message="Cortex request failed.",
            data=error_data,
        ) from exc

    def _init_converters(self, kernel: "Kernel | None" = None) -> CortexConverters:
        converters = CortexConverters()
        if kernel is not None:
            converters.attach_kernel(kernel)
        return converters

    def _init_parameters(
        self,
        parameters: CortexPlatformParameters | None = None,
        **kwargs: Any,
    ) -> CortexPlatformParameters:
        if parameters is None:
            raise ValueError("Parameters are required for Cortex client")
        return parameters

    def _init_parsers(self) -> CortexParsers:
        return CortexParsers()

    def _init_session(
        self,
        parameters: CortexPlatformParameters,
    ) -> "Session":
        from snowflake.snowpark import Session

        from agent_platform.core.platforms.cortex.connect import (
            SnowflakeAuthenticationError,
            get_connection_details,
            safe_get_or_create_session,
        )

        try:
            # Use the get_connection_details utils to build final connection
            # details from the parameters
            connection_details = get_connection_details(
                role=parameters.snowflake_role,
                warehouse=parameters.snowflake_warehouse,
                database=parameters.snowflake_database,
                schema=parameters.snowflake_schema,
                username=parameters.snowflake_username,
                password=(
                    parameters.snowflake_password.get_secret_value()
                    if parameters.snowflake_password
                    else None
                ),
                account=parameters.snowflake_account,
            )

            # This is important, as it holds a lock during session creation
            # to patch over an issue with Snowflake's thread safety.
            return safe_get_or_create_session(
                Session.builder.configs(connection_details),
            )
        except SnowflakeAuthenticationError as e:
            if "Failed to read authentication config" in str(e):
                # We can give a touch more detail here because we know
                # it's a link file issue
                raise PlatformHTTPError(
                    error_code=ErrorCode.UNAUTHORIZED,
                    message=(
                        "Authentication failed for Snowflake Cortex: no linking details were found."
                    ),
                ) from e
            # This would be a much more nuanced/obscure scenario... so let's
            # give a generic message (not even sure if we _can_ hit this...
            # it'd be something like "we're running in SPCS but the token file
            # that is promised to be there isn't there or it's malformed")
            raise PlatformHTTPError(
                error_code=ErrorCode.UNAUTHORIZED,
                message="Authentication failed for Snowflake Cortex",
            ) from e

    async def _ensure_session(self) -> "Session":
        """Return an initialized Snowpark session, creating it on-demand."""
        session = self._cortex_runtime_session
        if session is not None:
            return session

        async with self._session_lock:
            session = self._cortex_runtime_session
            if session is None:
                session = await asyncio.to_thread(
                    self._init_session,
                    self._parameters,
                )
                self._cortex_runtime_session = session

        session = self._cortex_runtime_session
        if session is None:
            raise RuntimeError("Failed to initialize Cortex session")
        return session

    async def _refresh_session(self) -> "Session":
        """Recreate the Snowpark session and return it."""
        async with self._session_lock:
            session = await asyncio.to_thread(
                self._init_session,
                self._parameters,
            )
            self._cortex_runtime_session = session
            return session

    def _extract_session_token(self, session: "Session") -> str | None:
        """Retrieve the primary REST token from a Snowpark session."""
        rest_connection = getattr(session.connection, "rest", None)
        if rest_connection is None:
            raise ValueError("No REST connection found for Cortex runtime session")
        token = getattr(rest_connection, "token", None)
        if token:
            return token
        return None

    async def _get_or_refresh_token(self) -> tuple["Session", str]:
        """Get a valid token for the Cortex runtime session, refreshing if needed."""
        session = await self._ensure_session()
        token = self._extract_session_token(session)
        if token:
            return session, token

        session = await self._refresh_session()
        token = self._extract_session_token(session)
        if not token:
            raise ValueError("No token found for Cortex runtime session")
        return session, token

    def _build_authorization_value(self, session: "Session", token: str) -> str:
        """Format the Authorization header to mirror Snowflake's client behaviour."""
        connection = getattr(session, "connection", None)
        auth_class = getattr(connection, "auth_class", None) if connection else None

        auth_class_str: str = ""
        if isinstance(auth_class, str):
            auth_class_str = auth_class
        elif isinstance(auth_class, type):
            auth_class_str = auth_class.__name__
        elif auth_class is not None:
            auth_class_str = auth_class.__class__.__name__

        if "OAuth" in auth_class_str:
            return f"Bearer {token}"

        # Default to session-token semantics used by Snowflake's REST clients
        return f'Snowflake Token="{token}"'

    async def _build_url(self) -> str:
        """Build the full URL for the completion endpoint."""
        session = await self._ensure_session()
        cortex_completion_path = "/api/v2/cortex/inference:complete"

        completions_url = f"https://{session.connection.host}{cortex_completion_path}"
        if "_" in completions_url:
            # Shouldn't happen, but just in case
            completions_url = completions_url.replace("_", "-")

        return completions_url

    async def _build_headers(self, streaming: bool = False) -> dict[str, Any]:
        """Build the headers for the completion endpoint."""
        _ = streaming  # Header shape does not currently depend on streaming mode.
        session, token = await self._get_or_refresh_token()
        authorization_value = self._build_authorization_value(session, token)
        return {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "Authorization": authorization_value,
        }

    @staticmethod
    @lru_cache(maxsize=1)
    def _platform_specific_id_to_provider_map() -> dict[str, str]:
        """Build a lookup from platform-specific model IDs to providers."""
        config = PlatformModelConfigs()
        provider_lookup: dict[str, str] = {}
        for generic_id, platform_id in config.models_to_platform_specific_model_ids.items():
            if not generic_id.startswith("cortex/"):
                continue
            parts = generic_id.split("/", 2)
            if len(parts) != 3:  # noqa: PLR2004 (platform/provider/model)
                continue
            _, provider, _ = parts
            provider_lookup.setdefault(platform_id, provider.lower())
        return provider_lookup

    @classmethod
    def _infer_provider_for_model(cls, model_identifier: str) -> str:
        lookup = cls._platform_specific_id_to_provider_map()
        provider = lookup.get(model_identifier)
        if provider:
            return provider

        return "unknown"

    async def _list_models_via_show_models(self) -> dict[str, list[str]]:
        session = await self._ensure_session()
        try:
            rows = await asyncio.to_thread(
                lambda: session.sql("SHOW MODELS IN SCHEMA SNOWFLAKE.MODELS").collect(),
            )
        except Exception as exc:
            raise PlatformHTTPError(
                error_code=ErrorCode.UNAUTHORIZED,
                message=(
                    "Failed to list Cortex models via SHOW MODELS. "
                    "Verify the configured Snowflake role has permission to list models."
                ),
                data={"context": "SHOW MODELS IN SCHEMA SNOWFLAKE.MODELS"},
            ) from exc

        if not rows:
            logger.warning(
                "No Cortex models found via SHOW MODELS.\n"
                "User may need to run `CALL SNOWFALKE.MODELS.CORTEX_BASE_MODELS_REFRESH();`\n"
                "Or there may be an issue with permissions.\n"
                "Falling back to default model list."
            )
            return DEFAULT_SNOWFLAKE_MODELS

        provider_models: defaultdict[str, set[str]] = defaultdict(set)
        for row in rows or []:
            model_identifier = row.as_dict().get("name")
            if not model_identifier:
                continue
            model_identifier = model_identifier.lower().strip()
            provider = self._infer_provider_for_model(model_identifier)
            provider_models[provider].add(model_identifier)

        return {provider: sorted(models) for provider, models in provider_models.items() if models}

    async def get_available_models(self) -> dict[str, list[str]]:
        if self._available_models_cache:
            return deepcopy(self._available_models_cache)

        if self._GLOBAL_AVAILABLE_MODELS_CACHE:
            self._available_models_cache = deepcopy(self._GLOBAL_AVAILABLE_MODELS_CACHE)
            return deepcopy(self._available_models_cache)

        async with self._GLOBAL_AVAILABLE_MODELS_LOCK:
            if self._GLOBAL_AVAILABLE_MODELS_CACHE:
                self._available_models_cache = deepcopy(self._GLOBAL_AVAILABLE_MODELS_CACHE)
                return deepcopy(self._available_models_cache)

            models = await self._list_models_via_show_models()

            self._GLOBAL_AVAILABLE_MODELS_CACHE.clear()
            for provider, provider_models in models.items():
                self._GLOBAL_AVAILABLE_MODELS_CACHE[provider] = list(provider_models)

            self._available_models_cache = deepcopy(self._GLOBAL_AVAILABLE_MODELS_CACHE)
            return deepcopy(self._available_models_cache)

    def _raise_for_non_ok_response(
        self,
        *,
        response: Response,
        error_detail: Any,
        context: str,
    ) -> None:
        """Log and raise for non-successful Cortex responses."""
        logger.error(
            f"Cortex {context} failed with status_code={response.status_code} "
            f"response_headers={response.headers} body='{error_detail}'"
        )
        status_code = response.status_code or 0

        if status_code in self._RETRYABLE_STATUS or codes.is_server_error(status_code):
            response.raise_for_status()

        if status_code == codes.BAD_REQUEST:
            error_dict = error_detail if isinstance(error_detail, dict) else {}
            message = error_dict.get("message", str(error_detail))
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST,
                message=message,
                data={"status_code": status_code},
            )
        if status_code in self._UNAUTHORIZED_STATUS:
            raise PlatformHTTPError(
                error_code=ErrorCode.UNAUTHORIZED,
                message=(
                    "Cortex authentication failed or session token expired. "
                    "Please verify your Snowflake credentials."
                ),
                data={"status_code": status_code, "context": context},
                status_code=status_code,
            )
        if codes.is_success(status_code):
            raise PlatformHTTPError(
                error_code=ErrorCode.UNEXPECTED,
                message=(
                    "Cortex returned an unexpected success status while processing the request."
                ),
                data={"status_code": status_code, "context": context},
            )
        response.raise_for_status()

    async def _generate_response(
        self,
        request: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate a response from the Cortex platform with retry logic."""
        timeout = Timeout(self._DEFAULT_TIMEOUT_S)

        async def _request() -> dict[str, Any]:
            async with init_httpx_client(timeout=timeout) as client:
                url = await self._build_url()
                headers = await self._build_headers(streaming=False)

                response = await client.post(
                    url,
                    json=request,
                    headers=headers,
                )

                if response.status_code == codes.OK:
                    return response.json()

                error_detail = await self._read_error_detail(response)
                self._raise_for_non_ok_response(
                    response=response,
                    error_detail=error_detail,
                    context="generate request",
                )

            # Need this for the type checker
            raise AssertionError("Should be unreachable")

        for refresh_attempt in range(2):
            try:
                return await self._call_with_retries(
                    _request,
                    context="generate request",
                )
            except PlatformHTTPError as exc:
                if exc.response.error_code == ErrorCode.UNAUTHORIZED and refresh_attempt == 0:
                    logger.info(
                        "Cortex session returned unauthorized; refreshing session and retrying",
                    )
                    await self._refresh_session()
                    continue
                raise

        raise PlatformHTTPError(
            error_code=ErrorCode.UNAUTHORIZED,
            message="Cortex authentication failed after session refresh attempt.",
            status_code=codes.UNAUTHORIZED,
        )

    async def _iter_stream_response_once(
        self,
        *,
        request: dict[str, Any],
        timeout: Timeout,
    ) -> AsyncGenerator[str, None]:
        async with init_httpx_client(timeout=timeout) as client:
            url = await self._build_url()
            headers = await self._build_headers(streaming=True)

            async with client.stream(
                "POST",
                url,
                json=request,
                headers=headers,
            ) as response:
                if response.status_code != codes.OK:
                    error_detail = await self._read_error_detail(response)
                    self._raise_for_non_ok_response(
                        response=response,
                        error_detail=error_detail,
                        context="stream request",
                    )

                async for line in response.aiter_lines():
                    if line.strip():
                        yield line

    async def _iter_stream_with_backoff(
        self,
        *,
        request: dict[str, Any],
        timeout: Timeout,
    ) -> AsyncGenerator[str, None]:
        from agent_platform.core.platforms.retry import build_httpx_async_retrying

        retrying = build_httpx_async_retrying(
            logger=logger,
            provider_name="Cortex",
            context="stream request",
            max_attempts=self._MAX_RETRY_ATTEMPTS,
            base_backoff_s=self._BACKOFF_BASE_S,
            max_backoff_s=self._BACKOFF_MAX_S,
            retryable_status=self._RETRYABLE_STATUS,
        )

        async for attempt in retrying:
            with attempt:
                try:
                    async for line in self._iter_stream_response_once(
                        request=request,
                        timeout=timeout,
                    ):
                        yield line
                except PlatformHTTPError as exc:
                    # Tenacity only retries HTTPStatusError/RequestError.
                    # Translate auth failures into a refresh signal but
                    # surface other platform errors unchanged so callers see
                    # the final failure.
                    if exc.response.error_code == ErrorCode.UNAUTHORIZED:
                        raise _SessionRefreshRequiredError from exc
                    raise

    async def _generate_stream_response(
        self,
        request: dict[str, Any],
    ) -> AsyncGenerator[str, None]:
        """Generate a stream response from the Cortex platform with retry logic."""
        timeout = Timeout(self._DEFAULT_TIMEOUT_S)

        for refresh_attempt in range(2):
            try:
                async for line in self._iter_stream_with_backoff(
                    request=request,
                    timeout=timeout,
                ):
                    yield line
                return
            except _SessionRefreshRequiredError as refresh_exc:
                if refresh_attempt == 0:
                    logger.info(
                        "Cortex stream returned unauthorized; refreshing session and retrying",
                    )
                    await self._refresh_session()
                    continue
                raise PlatformHTTPError(
                    error_code=ErrorCode.UNAUTHORIZED,
                    message=(
                        "Cortex streaming authentication failed after session refresh attempt."
                    ),
                    status_code=codes.UNAUTHORIZED,
                ) from refresh_exc

    async def generate_response(
        self,
        prompt: CortexPrompt,
        model: str,
    ) -> ResponseMessage:
        """Generate a complete response from the Cortex platform.

        Args:
            prompt: The prompt to send to the model.
            model: The model to use to generate the response.
        Returns:
            The complete model response.
        """
        model_id = await resolve_generic_model_id_to_platform_specific_model_id(self, model)
        request = prompt.as_platform_request(model_id)
        self._log_debug_payload("generate request", request)
        response = await self._generate_response(request)

        if not response:
            logger.warning(
                f"Cortex generate returned empty response model={model_id}",
            )

        self._log_debug_payload("generate response", response)
        return self.parsers.parse_response(response)

    async def generate_stream_response(
        self,
        prompt: CortexPrompt,
        model: str,
    ) -> AsyncGenerator[GenericDelta, None]:
        """Stream a response from the Cortex platform.

        Args:
            prompt: The prompt to send to the model.
            model: The model to use to generate the response.

        Yields:
            GenericDeltas that update the ResponseMessage.
        """
        import json

        with self.kernel.otel.span("generate_stream_response") as span:
            model_id = await resolve_generic_model_id_to_platform_specific_model_id(self, model)
            span.add_event("streaming on model", {"model": model_id})

            request = prompt.as_platform_request(model_id, stream=True)
            span.add_event_with_artifacts(
                "request",
                ("platform-request.json", json.dumps(request, indent=2)),
            )
            self._log_debug_payload("stream request", request)

            # Initialize message state
            message: dict[str, Any] = {}
            last_message: dict[str, Any] = {}

            # Process each event through the parser to get deltas
            span.add_event("initiating stream")
            stream_lines_seen = False
            deltas_emitted = False
            async for line in self._generate_stream_response(request):
                stream_lines_seen = True
                self._log_debug_payload("stream line", line)
                async for delta in self._parsers.parse_stream_event(
                    line,
                    message,
                    last_message,
                ):
                    deltas_emitted = True
                    yield delta

                # Update last message state after processing each event
                last_message = deepcopy(message)

            span.add_event("streaming complete")
            final_event = self._generate_platform_metadata()
            if "metadata" not in message:
                message["metadata"] = {}
            message["metadata"].update(final_event)

            span.add_event("sending final message deltas")
            self._log_debug_payload("stream final message", message)
            for delta in compute_generic_deltas(last_message, message):
                deltas_emitted = True
                yield delta

            if not stream_lines_seen:
                logger.warning(
                    f"Cortex stream returned no content model={model_id}",
                )
            elif not deltas_emitted:
                logger.warning(
                    f"Cortex stream produced no deltas model={model_id}",
                )

    async def _ensure_warehouse_selected(self) -> None:
        # Handle warehouse selection to prevent "No active warehouse selected" errors
        with self.kernel.otel.span("ensure_warehouse_selected") as span:
            span.add_event("checking if warehouse is specified")
            session = await self._ensure_session()
            if self._parameters.snowflake_warehouse:
                logger.debug(
                    f"Setting active warehouse to: {self._parameters.snowflake_warehouse}",
                )
                span.add_event(
                    "setting active warehouse",
                    {
                        "warehouse": self._parameters.snowflake_warehouse,
                    },
                )
                use_stmt = session.sql(
                    f"USE WAREHOUSE {self._parameters.snowflake_warehouse}",
                )
                await asyncio.to_thread(use_stmt.collect)
                span.add_event("warehouse set")
                return

            span.add_event("no warehouse specified, attempting to find one")
            logger.info(
                "No warehouse specified. Attempting to find an available warehouse...",
            )
            try:
                # Get list of warehouses the user has access to
                span.add_event("getting list of warehouses")
                warehouses_query = session.sql(
                    "SHOW WAREHOUSES",
                )
                warehouses_df = await asyncio.to_thread(warehouses_query.collect)
                if warehouses_df and len(warehouses_df) > 0:
                    # Extract warehouse names (Snowflake returns
                    # column names in uppercase)
                    available_warehouses = [row["name"] for row in warehouses_df]
                    if available_warehouses:
                        selected_warehouse = available_warehouses[0]
                        logger.info(
                            f"Automatically selected warehouse: {selected_warehouse}",
                        )
                        span.add_event(
                            "using automatically selected warehouse",
                            {"warehouse": selected_warehouse},
                        )
                        selected_stmt = session.sql(
                            f"USE WAREHOUSE {selected_warehouse}",
                        )
                        await asyncio.to_thread(selected_stmt.collect)
                        # Save for future reference
                        self._parameters = self._parameters.model_copy(
                            update={"snowflake_warehouse": selected_warehouse},
                        )
                    else:
                        logger.warning(
                            "No warehouses found that the user has access to.",
                        )
                        span.add_event("no warehouses found")
                else:
                    logger.warning(
                        "Failed to retrieve warehouse list. Embeddings may fail.",
                    )
                    span.add_event("failed to retrieve warehouse list")
            except Exception as e:
                span.add_event("error when trying to automatically select a warehouse")
                logger.warning(
                    f"Error when trying to automatically select a warehouse: {e}",
                )
                logger.warning(
                    "Cortex embeddings require a compute warehouse. Operations may fail.",
                )

    async def create_embeddings(
        self,
        texts: list[str],
        model: str,
    ) -> dict[str, Any]:
        """Create embeddings using a Cortex embedding model.

        Args:
            texts: List of text strings to create embeddings for.
            model: The model to use to generate embeddings.

        Returns:
            A dictionary containing the embeddings and any
            additional model-specific information.
        """
        with self.kernel.otel.span("create_embeddings") as span:
            from snowflake.snowpark.functions import call_function
            from snowflake.snowpark.functions import col as sp_col
            from snowflake.snowpark.types import StringType, StructField, StructType

            # First, we need to ensure that a warehouse is selected
            span.add_event("ensuring warehouse is selected")
            await self._ensure_warehouse_selected()

            model_id = await resolve_generic_model_id_to_platform_specific_model_id(self, model)
            span.add_event("embedding on model", {"model": model_id})

            if not texts:
                span.add_event("no texts provided to embed; returning empty list")
                return {
                    "embeddings": [],
                    "model": model,
                    "usage": {"total_tokens": 0},
                }

            func_name = "EMBED_TEXT_768"
            if model_id in {
                "snowflake-arctic-embed-l-v2.0",
                "voyage-multilingual-2",
            }:
                func_name = "EMBED_TEXT_1024"

            logger.debug(
                f"Embedding batch of texts in Snowflake. model={model_id}, "
                f"batch_size={len(texts)}, sql_function={func_name}",
            )

            text_rows = [(t,) for t in texts]
            text_schema = StructType([StructField("text", StringType())])
            session = await self._ensure_session()
            df_input = session.create_dataframe(
                text_rows,
                schema=text_schema,
            )

            embed_udf_call = call_function(
                f"SNOWFLAKE.CORTEX.{func_name}",
                model_id,
                sp_col("text"),
            ).alias("embedding")

            df_embeds = df_input.select(embed_udf_call)
            rows = await asyncio.to_thread(df_embeds.collect)
            logger.debug(f"Collected embeddings from Snowflake. row_count={len(rows)}")

            embeddings = []
            for r in rows:
                emb = list(r["EMBEDDING"])  # Convert Snowflake Vector to a Python list
                embeddings.append(emb)

            # Estimate tokens since we don't get real count; tokens is roughly
            # the number of characters // 4
            total_tokens = sum(len(t) // 4 for t in texts)
            return {
                "embeddings": embeddings,
                "model": model,
                "usage": {"total_tokens": total_tokens},
            }


PlatformClient.register_platform_client("cortex", CortexClient)
AsyncClient = HTTPXAsyncClient  # Compat: tests patch this symbol directly
