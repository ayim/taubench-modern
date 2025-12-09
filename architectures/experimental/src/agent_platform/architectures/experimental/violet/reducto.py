import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from reducto.types import ExtractRunParams, ParseRunParams
    from reducto.types.job_get_response import Result as JobResult
    from reducto.types.shared import ExtractResponse, ParseResponse, Upload


class VioletReductoClient:
    def __init__(self, api_url: str, api_key: str):
        from reducto import AsyncReducto

        self.client = AsyncReducto(
            # We have to set one, but we put our key in the headers
            api_key="unused",
            base_url=api_url,
        )
        # Set the API key in the client headers directly
        self.client._client.headers["X-API-Key"] = api_key

    async def upload(self, file: Path | tuple[str, bytes]) -> "Upload":
        return await self.client.upload(file=file)

    async def parse(
        self, parse_options: "ParseRunParams", uploaded_document: "Upload"
    ) -> "ParseResponse":
        """Parse a document into a structured format using Reducto."""
        from reducto import NOT_GIVEN
        from reducto.types.shared import ParseResponse

        def _pick(key: str):
            if parse_options and key in parse_options:
                value = parse_options[key]
                return value if value is not None else NOT_GIVEN
            return NOT_GIVEN

        parse_job_response = await self.client.parse.run_job(
            document_url=uploaded_document.file_id,
            options=_pick("options"),
            advanced_options=_pick("advanced_options"),
            experimental_options=_pick("experimental_options"),
        )

        result = await self._complete(parse_job_response.job_id)
        if not isinstance(result, ParseResponse):
            raise ValueError(f"Expected ParseResponse but got {type(result)}")
        return await self._fetch_remote_result(result)

    async def extract(
        self, extract_options: "ExtractRunParams", uploaded_document: "Upload"
    ) -> "ExtractResponse":
        """Extract structured data from a document using a JSON schema using Reducto."""
        from reducto import NOT_GIVEN
        from reducto.types.shared import ExtractResponse

        def _pick(key: str):
            if extract_options and key in extract_options:
                value = extract_options[key]
                return value if value is not None else NOT_GIVEN
            return NOT_GIVEN

        extract_job_response = await self.client.extract.run_job(
            document_url=uploaded_document.file_id,
            schema=_pick("schema"),
            options=_pick("options"),
            advanced_options=_pick("advanced_options"),
            experimental_options=_pick("experimental_options"),
            array_extract=_pick("array_extract"),
            generate_citations=_pick("generate_citations"),
            system_prompt=_pick("system_prompt"),
        )

        result = await self._complete(extract_job_response.job_id)
        if not isinstance(result, ExtractResponse):
            raise ValueError(f"Expected ExtractResponse but got {type(result)}")
        return result

    async def _complete(self, job_id: str) -> "JobResult":
        """
        Poll the Reducto Job until it is complete. The Sema4 hosted reducto
        is running behind an API gateway which times out after 30 seconds. It
        is important that any long-running calls to the service are done
        via polling and not via blocking.
        """
        while True:
            job_resp = await self.client.job.get(
                job_id=job_id,
            )
            match job_resp.status:
                case "Completed":
                    return job_resp.result
                case "Failed":
                    raise Exception(f"Job failed: {job_resp.model_dump_json()}")
                case "Pending":
                    await asyncio.sleep(3)
                case "Idle":
                    await asyncio.sleep(3)
                case _:
                    raise Exception(f"Unknown job status: {job_resp.status}")

    async def _fetch_remote_result(self, resp: "ParseResponse") -> "ParseResponse":
        """
        Conditionally fetch the remote results from a ResultURLResult in this ParseResponse.

        Args:
            resp: The ParseResponse to localize

        Returns:
            The parsed result as a ResultFullResult object
        """
        # Nothing to do, we have the full result
        if resp.result.type != "url":
            return resp

        try:
            from reducto.types.shared.parse_response import ResultFullResult

            from agent_platform.core.utils.httpx_client import init_httpx_client

            async with init_httpx_client(timeout=30.0) as client:
                fetch_response = await client.get(url=resp.result.url)
                fetch_response.raise_for_status()
                result_dict = fetch_response.json()
                resp.result = ResultFullResult(**result_dict)
                return resp
        except Exception as e:
            raise Exception(f"Error fetching result from URL: {e!s}") from e
