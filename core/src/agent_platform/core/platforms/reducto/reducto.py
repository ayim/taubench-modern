import asyncio
from pathlib import Path

from reducto import (
    NOT_GIVEN,
    AsyncReducto,
)
from reducto.types.job_get_response import Result as JobResult
from reducto.types.shared import (
    ExtractResponse,
    ParseResponse,
    Upload,
)

from agent_platform.core.platforms.reducto.prompts import ReductoPrompt


class PollingReductoClient:
    client: AsyncReducto

    def __init__(self, api_url: str, api_key: str):
        self.client = AsyncReducto(
            # We have to set one, but we put our key in the headers
            api_key="unused",
            base_url=api_url,
        )
        # Set the API key in the client headers directly
        self.client._client.headers["X-API-Key"] = api_key

    async def upload(self, file: Path | tuple[str, bytes]) -> Upload:
        return await self.client.upload(file=file)

    async def parse(
        self, prompt: ReductoPrompt, uploaded_document: Upload
    ) -> ParseResponse:
        parse_options = prompt.parse_options
        if parse_options is None:
            raise ValueError("Parse options are required for parse operation")

        parse_job_response = await self.client.parse.run_job(
            document_url=uploaded_document.file_id,
            options=(
                parse_options["options"]
                if parse_options and "options" in parse_options
                else NOT_GIVEN
            ),
            advanced_options=(
                parse_options["advanced_options"]
                if parse_options and "advanced_options" in parse_options
                else NOT_GIVEN
            ),
            experimental_options=(
                parse_options["experimental_options"]
                if parse_options and "experimental_options" in parse_options
                else NOT_GIVEN
            ),
        )

        result = await self._complete(parse_job_response.job_id)
        if not isinstance(result, ParseResponse):
            raise ValueError(f"Expected ParseResponse but got {type(result)}")
        return result

    async def extract(
        self, prompt: ReductoPrompt, uploaded_document: Upload
    ) -> ExtractResponse:
        extract_options = prompt.extract_options
        if extract_options is None:
            raise ValueError("Extract options are required for extract operation")

        extract_job_response = await self.client.extract.run_job(
            document_url=uploaded_document.file_id,
            schema=(
                extract_options["schema"]
                if extract_options and "schema" in extract_options
                else NOT_GIVEN
            ),
            options=(
                extract_options["options"]
                if extract_options and "options" in extract_options
                else NOT_GIVEN
            ),
            advanced_options=(
                extract_options["advanced_options"]
                if extract_options and "advanced_options" in extract_options
                else NOT_GIVEN
            ),
            experimental_options=(
                extract_options["experimental_options"]
                if extract_options and "experimental_options" in extract_options
                else NOT_GIVEN
            ),
        )

        result = await self._complete(extract_job_response.job_id)
        if not isinstance(result, ExtractResponse):
            raise ValueError(f"Expected ExtractResponse but got {type(result)}")
        return result

    async def _complete(self, job_id: str) -> JobResult:
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
