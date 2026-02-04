#!/usr/bin/env python3
"""Exercise the DocumentService with a PDF and schema."""

import asyncio
import json
import os
from pathlib import Path


async def main() -> None:
    from dotenv import load_dotenv

    load_dotenv()

    api_key = os.environ.get("REDUCTO_API_KEY")
    if not api_key:
        raise SystemExit("REDUCTO_API_KEY not found in environment")

    pdf_path = Path("/Users/joshelsermbp14/CustomerData/snowflake_equipment_rentals/Manual_2022-02-01.pdf")
    file_content = pdf_path.read_bytes()

    schema_path = Path("/Users/joshelsermbp14/CustomerData/snowflake_equipment_rentals/schema.json")
    json_schema = json.loads(schema_path.read_text())

    from agent_platform.core.semantic_data_model.schemas import (
        DocumentExtraction,
        Schema,
    )

    schema = Schema(
        name="equipment_inspection",
        description="Equipment inspection form schema",
        json_schema=json_schema,
        document_extraction=DocumentExtraction(
            system_prompt="Extract equipment inspection data from this form.",
        ),
    )

    from agent_platform.core.semantic_data_model.service import DocumentService

    service = DocumentService(reducto_api_key=api_key)
    try:
        print("Uploading document...")
        file_id = await service.upload(file_content)
        print(f"  File ID: {file_id}")

        print("Starting parse...")
        parse_job = await service.start_parse(file_id)
        print(f"  Parse Job ID: {parse_job.job_id}")

        print("Starting extraction...")
        extract_job = await service.start_extract(parse_job, schema)
        print(f"  Extract Job ID: {extract_job.job_id}")

        print("Waiting for result...")
        schema_data = await extract_job.result()

        print("\n" + "=" * 60)
        print("EXTRACTED DATA")
        print("=" * 60)
        print(json.dumps(schema_data.data, indent=2))

        print("\n" + "=" * 60)
        print("LINEAGE")
        print("=" * 60)
        for i, event in enumerate(schema_data.history):
            print(f"\nEvent {i + 1}: {type(event).__name__}")
            print(f"  {event}")

        print(f"\nCurrent Schema: {schema_data.current_schema.name if schema_data.current_schema else 'None'}")
        print(f"Overall Valid: {schema_data.is_valid}")

    finally:
        await service.close()


if __name__ == "__main__":
    asyncio.run(main())

# USAGE:
# uv run --project agent_platform_server python scripts/exercise_document_service.py
