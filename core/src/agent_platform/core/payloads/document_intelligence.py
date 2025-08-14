from __future__ import annotations

from dataclasses import dataclass

from agent_platform.core.document_intelligence.document_layout import DocumentLayoutBridge
from agent_platform.core.files import UploadedFile


@dataclass(frozen=True)
class GenerateLayoutResponsePayload:
    layout: DocumentLayoutBridge
    file: UploadedFile | None = None
