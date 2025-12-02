from typing import Literal

# Image formats
MIME_TYPE_JPEG = "image/jpeg"
MIME_TYPE_PNG = "image/png"
MIME_TYPE_GIF = "image/gif"
MIME_TYPE_WEBP = "image/webp"
MIME_TYPE_BMP = "image/bmp"
MIME_TYPE_TIFF = "image/tiff"
MIME_TYPE_PCX = "image/x-pcx"
MIME_TYPE_PPM = "image/x-portable-pixmap"
MIME_TYPE_APNG = "image/apng"
MIME_TYPE_PSD = "image/vnd.adobe.photoshop"
MIME_TYPE_ICO = "image/x-icon"
MIME_TYPE_MS_ICO = "image/vnd.microsoft.icon"
MIME_TYPE_DCX = "image/x-dcx"
MIME_TYPE_HEIC = "image/heic"
MIME_TYPE_HEIF = "image/heif"

# Documents
MIME_TYPE_PDF = "application/pdf"
MIME_TYPE_TXT = "text/plain"
MIME_TYPE_MD = "text/markdown"
MIME_TYPE_HTML = "text/html"
MIME_TYPE_RTF = "application/rtf"
MIME_TYPE_RTF_TEXT = "text/rtf"
MIME_TYPE_WORDPERFECT = "application/vnd.wordperfect"
MIME_TYPE_DOC = "application/msword"
MIME_TYPE_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MIME_TYPE_DOCX_TEMPLATE = "application/vnd.openxmlformats-officedocument.wordprocessingml.template"

# Spreadsheets
MIME_TYPE_CSV = "text/csv"
MIME_TYPE_TSV = "text/tab-separated-values"
MIME_TYPE_XLS = "application/vnd.ms-excel"
MIME_TYPE_XLSM = "application/vnd.ms-excel.sheet.macroEnabled.12"
MIME_TYPE_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MIME_TYPE_XLSX_TEMPLATE = "application/vnd.openxmlformats-officedocument.spreadsheetml.template"
MIME_TYPE_XLTM = "application/vnd.ms-excel.template.macroEnabled.12"
MIME_TYPE_ODS = "application/vnd.oasis.opendocument.spreadsheet"

# Presentations
MIME_TYPE_PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
MIME_TYPE_PPT = "application/vnd.ms-powerpoint"

# MIME types supported by Reducto for document processing
DOCUMENT_MIME_TYPES: set[str] = {
    # Image Formats
    MIME_TYPE_PNG,
    MIME_TYPE_JPEG,
    MIME_TYPE_BMP,
    MIME_TYPE_TIFF,
    MIME_TYPE_PCX,
    MIME_TYPE_PPM,
    MIME_TYPE_APNG,
    MIME_TYPE_PSD,
    MIME_TYPE_ICO,
    MIME_TYPE_MS_ICO,
    MIME_TYPE_DCX,
    MIME_TYPE_HEIC,
    MIME_TYPE_HEIF,
    # PDF
    MIME_TYPE_PDF,
    # Spreadsheets
    MIME_TYPE_CSV,
    MIME_TYPE_XLSX,
    MIME_TYPE_XLSM,
    MIME_TYPE_XLS,
    MIME_TYPE_XLSX_TEMPLATE,
    MIME_TYPE_XLTM,
    # Presentations
    MIME_TYPE_PPTX,
    MIME_TYPE_PPT,
    # Text Documents
    MIME_TYPE_DOCX,
    MIME_TYPE_DOC,
    MIME_TYPE_DOCX_TEMPLATE,
    MIME_TYPE_WORDPERFECT,
    MIME_TYPE_TXT,
    MIME_TYPE_RTF,
    MIME_TYPE_RTF_TEXT,
    # Additional text formats
    MIME_TYPE_MD,
    MIME_TYPE_HTML,
}

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
