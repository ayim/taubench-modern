from dataclasses import dataclass


@dataclass(frozen=True)
class DocumentLayoutSummary:
    name: str
    data_model: str
    summary: str | None = None
