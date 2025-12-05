"""
Data Transfer Objects (DTOs) for the services layer.

This module contains data models that represent the structure of data
being transferred between different layers of the application.
"""

import json
from typing import Annotated

from pydantic import BaseModel, Field, field_validator


class KnowledgeBaseQueryResult(BaseModel):
    """Represents a single result from a knowledge base query."""

    id: Annotated[
        str | None,
        Field(description="Unique identifier of the document for the result"),
    ] = None
    metadata: Annotated[
        dict | None,
        Field(description="Additional metadata associated with the result"),
    ] = None
    chunk_content: Annotated[
        str | None,
        Field(
            description="The actual text content of the knowledge base chunk that matched the query"
        ),
    ] = None
    relevance: Annotated[
        float | None,
        Field(
            description=(
                "Relevance score indicating how well this result matches the query "
                "(higher is more relevant)"
            )
        ),
    ] = None
    distance: Annotated[
        float | None,
        Field(
            description=(
                "Vector distance from the query embedding (lower distance means more similar)"
            )
        ),
    ] = None

    # Enhanced fields from full data parsed documents table
    page_number: Annotated[
        int | None,
        Field(
            description=(
                "The page number in the source document where this content was first found. "
                "The chunk can be present on multiple pages."
            )
        ),
    ] = None
    chunk: Annotated[
        dict | None,
        Field(
            description=(
                "The chunk where the answer was found containing structured information "
                "about text positioning and formatting. It also contains the page number "
                "and bounding box information."
            )
        ),
    ] = None
    document_name: Annotated[
        str | None,
        Field(description="The name of the source document"),
    ] = None

    @field_validator("metadata", "chunk", mode="before")
    @classmethod
    def parse_json_fields(cls, v: str | dict | list | None) -> dict | list | None:
        """Parse JSON string fields (metadata, chunk) if needed."""
        if v is None:
            return None
        if isinstance(v, dict | list):
            return v
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return {"raw_value": v} if v.strip() else None
        return v
