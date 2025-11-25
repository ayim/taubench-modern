from typing import Literal

MIME_TYPE_JPEG = "image/jpeg"
MIME_TYPE_PNG = "image/png"
MIME_TYPE_GIF = "image/gif"
MIME_TYPE_WEBP = "image/webp"
MIME_TYPE_PDF = "application/pdf"
MIME_TYPE_TXT = "text/plain"
MIME_TYPE_CSV = "text/csv"
MIME_TYPE_TSV = "text/tab-separated-values"
MIME_TYPE_MD = "text/markdown"
MIME_TYPE_HTML = "text/html"
MIME_TYPE_XLS = "application/vnd.ms-excel"
MIME_TYPE_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MIME_TYPE_DOC = "application/msword"
MIME_TYPE_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MIME_TYPE_ODS = "application/vnd.oasis.opendocument.spreadsheet"

TABULAR_DATA_MIME_TYPES: list[str] = [
    MIME_TYPE_CSV,
    MIME_TYPE_TSV,
    MIME_TYPE_XLS,
    MIME_TYPE_XLSX,
    MIME_TYPE_ODS,
]

EXCEL_MIME_TYPES: list[str] = [MIME_TYPE_XLS, MIME_TYPE_XLSX, MIME_TYPE_ODS]

PromptDocumentMimeTypeLiteral = Literal[
    "application/pdf",
    "text/plain",
    "text/csv",
    "text/tab-separated-values",
    "text/markdown",
    "text/html",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
]
