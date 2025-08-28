from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from agent_platform.core.files.files import UploadedFile


@dataclass(frozen=True)
class DocumentLayoutSummary:
    name: str
    data_model: str
    summary: str | None = None


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            # Leave unparsed strings as None to avoid raising hard errors
            return None
    return None


@dataclass(frozen=True)
class IngestDocumentResponse:
    document: dict[str, Any]
    uploaded_file: UploadedFile | None = None

    @classmethod
    def model_validate(
        cls,
        data: dict[str, Any],
        uploaded_file: UploadedFile | None = None,
    ) -> IngestDocumentResponse:
        return cls(document=data, uploaded_file=uploaded_file)
