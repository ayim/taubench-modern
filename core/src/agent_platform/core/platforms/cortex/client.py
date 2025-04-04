from collections.abc import AsyncGenerator
from copy import deepcopy
from logging import getLogger
from typing import TYPE_CHECKING, Any, ClassVar, cast

from httpx import AsyncClient, AsyncHTTPTransport, Timeout, codes

from agent_platform.core.delta import GenericDelta
from agent_platform.core.delta.compute_delta import compute_generic_deltas
from agent_platform.core.platforms.base import (
    PlatformClient,
)
from agent_platform.core.platforms.cortex.configs import (
    CortexModelMap,
    CortexPlatformConfigs,
)
from agent_platform.core.platforms.cortex.converters import CortexConverters
from agent_platform.core.platforms.cortex.parameters import (
    CortexPlatformParameters,
)
from agent_platform.core.platforms.cortex.parsers import CortexParsers
from agent_platform.core.platforms.cortex.prompts import CortexPrompt
from agent_platform.core.responses.response import ResponseMessage

if TYPE_CHECKING:
    from snowflake.snowpark import Session

    from agent_platform.core.kernel import Kernel


logger = getLogger(__name__)


class CortexClient(
    PlatformClient[
        CortexConverters,
        CortexParsers,
        CortexPlatformParameters,
        CortexPlatformConfigs,
        CortexPrompt,
    ],
):
    """A client for the Cortex platform."""

    NAME: ClassVar[str] = "cortex"

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
        self._cortex_runtime_session = self._init_session(
            self._parameters,
        )

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

    def _init_configs(self) -> CortexPlatformConfigs:
        return CortexPlatformConfigs()

    def _init_session(
        self,
        parameters: CortexPlatformParameters,
    ) -> "Session":
        from snowflake.snowpark import Session

        from agent_platform.core.platforms.cortex.utils import (
            get_connection_details,
            safe_get_or_create_session,
        )

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

    def _get_or_refresh_token(self) -> str:
        """Get or refresh the token for the Cortex runtime session."""
        self._cortex_runtime_session = self._init_session(self._parameters)
        if not self._cortex_runtime_session.connection.rest:
            raise ValueError("No REST connection found for Cortex runtime session")
        token = self._cortex_runtime_session.connection.rest.token
        if not token:
            raise ValueError("No token found for Cortex runtime session")
        return token

    def _build_url(self) -> str:
        """Build the full URL for the completion endpoint."""
        cortex_completion_path = "/api/v2/cortex/inference:complete"

        completions_url = (
            f"https://{self._cortex_runtime_session.connection.host}"
            f"{cortex_completion_path}"
        )
        if "_" in completions_url:
            # Shouldn't happen, but just in case
            completions_url = completions_url.replace("_", "-")

        return completions_url

    def _build_headers(self, streaming: bool = False) -> dict[str, Any]:
        """Build the headers for the completion endpoint."""
        bearer_token = self._get_or_refresh_token()
        return {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "Authorization": f'Snowflake Token="{bearer_token}"',
        }

    async def _generate_response(
        self,
        request: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate a response from the Cortex platform.
        """
        transport = AsyncHTTPTransport(retries=2)
        timeout = Timeout(300.0)

        async with AsyncClient(
            transport=transport,
            timeout=timeout,
        ) as client:
            response = await client.post(
                self._build_url(),
                json=request,
                headers=self._build_headers(streaming=False),
            )
            # # Log the curl command to the console
            # curl_command = f"curl -X POST {self._build_url()}"
            # for header, value in self._build_headers(streaming=False).items():
            #     curl_command += f" -H '{header}: {value}'"
            # # Careful on the escaping here
            # curl_command += f" -d '{dumps(request)}'"
            # print(f"Curl command: {curl_command}")
            if response.status_code != codes.OK:
                try:
                    error_text = await response.aread()
                    error_detail = error_text.decode()
                except Exception as e:
                    error_detail = f"(Failed to read error response body: {e})"
                logger.error(
                    f"Cortex generate response call failed "
                    f"with status_code={response.status_code} "
                    f"response_headers={response.headers} "
                    f"body='{error_detail}' ",
                )
                response.raise_for_status()  # Re-raise after logging
            return response.json()

    async def _generate_stream_response(
        self,
        request: dict[str, Any],
    ) -> AsyncGenerator[str, None]:
        """Generate a stream response from the Cortex platform."""
        transport = AsyncHTTPTransport(retries=2)
        timeout = Timeout(300.0)

        async with AsyncClient(
            transport=transport,
            timeout=timeout,
        ) as client:
            # Get headers
            headers = self._build_headers(streaming=True)
            async with client.stream(
                "POST",
                self._build_url(),
                json=request,
                headers=headers,
                # timeout=None is handled by client-level timeout now
            ) as response:
                # Add more detailed error logging on failure
                if response.status_code != 200:  # noqa: PLR2004
                    try:
                        # Attempt to read the response body for detailed error
                        error_text = await response.aread()
                        error_detail = error_text.decode()
                    except Exception as e:
                        error_detail = f"(Failed to read error response body: {e})"
                    # Log details including request headers that were sent
                    logger.error(
                        f"Cortex stream call failed status_code={response.status_code} "
                        f"response_headers={response.headers} body='{error_detail}' "
                        f"request_headers_sent={headers}",
                    )
                    response.raise_for_status()  # Re-raise after logging

                # Original stream processing
                async for line in response.aiter_lines():
                    if line.strip():
                        yield line

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
        model_id = cast(str, CortexModelMap[model])
        request = prompt.as_platform_request(model_id)
        response = await self._generate_response(request)
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
            model_id = cast(str, CortexModelMap[model])
            span.add_event("streaming on model", {"model": model_id})

            request = prompt.as_platform_request(model_id, stream=True)
            span.add_event_with_artifacts(
                "request",
                ("platform-request.json", json.dumps(request, indent=2)),
            )

            # Initialize message state
            message: dict[str, Any] = {}
            last_message: dict[str, Any] = {}

            # Process each event through the parser to get deltas
            span.add_event("initiating stream")
            async for line in self._generate_stream_response(request):
                async for delta in self._parsers.parse_stream_event(
                    line,
                    message,
                    last_message,
                ):
                    yield delta

                # Update last message state after processing each event
                last_message = deepcopy(message)

            span.add_event("streaming complete")
            final_event = self._generate_platform_metadata()
            if "metadata" not in message:
                message["metadata"] = {}
            message["metadata"].update(final_event)

            span.add_event("sending final message deltas")
            for delta in compute_generic_deltas(last_message, message):
                yield delta

    async def _ensure_warehouse_selected(self) -> None:
        # Handle warehouse selection to prevent "No active warehouse selected" errors
        with self.kernel.otel.span("ensure_warehouse_selected") as span:
            span.add_event("checking if warehouse is specified")
            if self._parameters.snowflake_warehouse:
                logger.debug(
                    "Setting active warehouse to: "
                    f"{self._parameters.snowflake_warehouse}",
                )
                span.add_event(
                    "setting active warehouse",
                    {
                        "warehouse": self._parameters.snowflake_warehouse,
                    },
                )
                self._cortex_runtime_session.sql(
                    f"USE WAREHOUSE {self._parameters.snowflake_warehouse}",
                ).collect()
                span.add_event("warehouse set")
                return

            span.add_event("no warehouse specified, attempting to find one")
            logger.info(
                "No warehouse specified. Attempting to find an available warehouse...",
            )
            try:
                # Get list of warehouses the user has access to
                span.add_event("getting list of warehouses")
                warehouses_df = self._cortex_runtime_session.sql(
                    "SHOW WAREHOUSES",
                ).collect()
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
                        self._cortex_runtime_session.sql(
                            f"USE WAREHOUSE {selected_warehouse}",
                        ).collect()
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
                    "Cortex embeddings require a compute warehouse. "
                    "Operations may fail.",
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

            model_id = cast(str, CortexModelMap[model])
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
            df_input = self._cortex_runtime_session.create_dataframe(
                text_rows,
                schema=text_schema,
            )

            embed_udf_call = call_function(
                f"SNOWFLAKE.CORTEX.{func_name}",
                model_id,
                sp_col("text"),
            ).alias("embedding")

            df_embeds = df_input.select(embed_udf_call)
            rows = df_embeds.collect()
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
