# Sema4AI Document Intelligence Core

A Python library for document intelligence operations including document extraction, data model management, layout processing, and content transformation.

## Overview

The Document Intelligence Core provides a unified service layer for:

- **Document Processing**: Extract and transform content from 30+ document formats
- **Data Model Management**: Create and manage document schemas and business views
- **Layout Management**: Generate translation schemas for mapping between different data formats
- **Content Extraction**: Leverage Reducto AI for intelligent document parsing
- **Validation**: Validate extracted content against quality rules

## Installation

```bash
pip install sema4ai-docint
```

## Getting Started

### Basic Setup

```python
from sema4ai.data import DataSource
from sema4ai_docint import build_di_service

# Build the document intelligence service
di_service = build_di_service(
    datasource=datasource,
    sema4_api_key="your-sema4-api-key",  # Optional: required for extraction operations
    disable_ssl_verification=False       # Optional: if you want to disable ssl when talking with the extraction client
)
```

### When to Use API Keys

#### `sema4_api_key` Parameter

- **Required for**: Document extraction operations
- **Used by**: `ExtractionService` and `DocumentService.ingest()` operations
- **If not provided**: Extraction service will be `None`, and document ingestion will fail

#### `disable_ssl_verification` Parameter

- **Required for**: Development environments or networks with SSL/proxy issues
- **Used by**: Reducto client connections to Sema4AI backend
- **Default**: `False` (SSL verification enabled)
- **When to set `True`**: Testing environments, behind corporate proxies, or SSL certificate issues

## API Reference

### DIService (Main Facade)

The `DIService` class provides access to all document intelligence operations through organized sub-services.

```python
# Access sub-services
di_service.document     # Document operations
di_service.data_model   # Data model operations
di_service.layout       # Layout operations
di_service.extraction   # Extraction operations (if sema4_api_key provided)
```

### DocumentService

Handles high-level document operations including ingestion, querying, and validation.

#### `ingest(file_name: str, data_model_name: str, layout_name: str) -> dict`

Ingest a document into the system using a specific data model and layout.

**Parameters:**

- `file_name` (str): Name of the PDF file to process
- `data_model_name` (str): Name of the data model to use
- `layout_name` (str): Name of the document layout for processing

**Returns:** Dict containing the processed document and validation information

**Requires:** `sema4_api_key` (uses ExtractionService)

```python
result = di_service.document.ingest(
    file_name="invoice.pdf",
    data_model_name="invoice_model",
    layout_name="standard_layout"
)
```

#### `query(document_id: str) -> dict`

Retrieve a document in data model format using business views.

**Parameters:**

- `document_id` (str): Document ID to retrieve

**Returns:** Dict with document data organized by view names

```python
document_data = di_service.document.query("doc_123")
```

#### `validate(data_model_name: str, document_id: str) -> dict`

Validate a document against quality checks.

**Parameters:**

- `data_model_name` (str): Name of the data model
- `document_id` (str): ID of the document to validate

**Returns:** Validation results with overall status and rule outcomes

```python
validation_result = di_service.document.validate("invoice_model", "doc_123")
```

### DataModelService

Manages data models, schemas, and business view generation.

#### `generate_from_file(file_name: str) -> dict`

Generate a data model schema from an uploaded document.

**Parameters:**

- `file_name` (str): Name of the file to analyze

**Returns:** Dict with generated schema and success message

**Uses:** AgentServerClient for AI-powered schema generation

```python
schema_result = di_service.data_model.generate_from_file("sample_invoice.pdf")
```

#### `create_from_schema(name: str, description: str, json_schema_text: str, prompt: str = None, summary: str = None) -> dict`

Create a new data model from a JSON schema.

**Parameters:**

- `name` (str): Name of the data model
- `description` (str): Description of the data model
- `json_schema_text` (str): JSON schema as string
- `prompt` (str, optional): Custom prompt for the data model
- `summary` (str, optional): Summary of the data model

**Returns:** Created data model as JSON

**Uses:** AgentServerClient for schema processing and summarization

```python
data_model = di_service.data_model.create_from_schema(
    name="Invoice Model",
    description="Schema for processing invoices",
    json_schema_text='{"type": "object", "properties": {...}}',
    prompt="Extract invoice data accurately"
)
```

#### `create_business_views(data_model_name: str) -> dict`

Create SQL views for a data model in the database.

**Parameters:**

- `data_model_name` (str): Name of the data model

**Returns:** Success message

```python
views_result = di_service.data_model.create_business_views("invoice_model")
```

### LayoutService

Handles document layout operations and translation schema generation.

#### `generate_translation_schema(data_model_name: str, layout_schema: str) -> dict`

Create translation rules to map layout schema to data model schema.

**Parameters:**

- `data_model_name` (str): Name of the target data model
- `layout_schema` (str): Source extraction schema as JSON string

**Returns:** Dict containing translation mapping rules

**Uses:** AgentServerClient for intelligent mapping generation

```python
translation_schema = di_service.layout.generate_translation_schema(
    data_model_name="invoice_model",
    layout_schema='{"type": "object", "properties": {...}}'
)
```

### ExtractionService

Provides document extraction capabilities using Reducto AI.

**Note:** Only available when `sema4_api_key` is provided to `build_di_service()`.

#### `extract(file_path: Path, extraction_schema: Union[str, dict], data_model_prompt: str = None, extraction_config: dict = None, document_layout_prompt: str = None) -> dict`

Extract structured data from a document.

**Parameters:**

- `file_path` (Path): Path to the document file
- `extraction_schema` (str | dict): Schema defining what to extract
- `data_model_prompt` (str, optional): Custom prompt for extraction
- `extraction_config` (dict, optional): Reducto configuration options
- `document_layout_prompt` (str, optional): Layout-specific prompt

**Returns:** Extracted data as dictionary

**Requires:** `sema4_api_key`

```python
# Only available if sema4_api_key was provided
if di_service.extraction:
    extracted_data = di_service.extraction.extract(
        file_path=Path("document.pdf"),
        extraction_schema={"type": "object", "properties": {...}},
        data_model_prompt="Extract key business information"
    )
```

#### `reducto` Property

Access to the underlying Reducto client for advanced operations.

```python
# Direct access to Reducto client
if di_service.extraction:
    reducto_client = di_service.extraction.reducto
```

## Usage Examples

### Complete Document Processing Workflow

```python
from sema4ai.data import DataSource
from sema4ai_docint import build_di_service

# Setup
di_service = build_di_service(
    datasource=datasource,
    sema4_api_key="your-sema4-api-key"
)

# 1. Generate schema from sample document
schema_result = di_service.data_model.generate_from_file("sample.pdf")
print("Generated schema:", schema_result["schema"])

# 2. Create data model
data_model = di_service.data_model.create_from_schema(
    name="Contract Model",
    description="Schema for processing contracts",
    json_schema_text=json.dumps(schema_result["schema"])
)

# 3. Process a document
result = di_service.document.ingest(
    file_name="contract.pdf",
    data_model_name="contract_model",
    layout_name="default"
)

# 4. Query the processed document
document_data = di_service.document.query(result["document"]["id"])

# 5. Validate the document
validation = di_service.document.validate(
    "contract_model",
    result["document"]["id"]
)
```

### Working Without Extraction Service

```python
# For operations that don't require document extraction
di_service = build_di_service(datasource=datasource)
# No sema4_api_key provided

# These operations still work:
# - Query existing documents
# - Create data models from existing schemas
# - Generate translation schemas
# - Validate documents

# This will be None:
assert di_service.extraction is None

# Document ingestion will fail without extraction service
```

## Error Handling

The library defines custom exceptions for different service operations:

```python
from sema4ai_docint.services import (
    DocumentServiceError,
    DataModelServiceError,
    LayoutServiceError,
    ExtractionServiceError
)

try:
    result = di_service.document.ingest(
        file_name="document.pdf",
        data_model_name="model",
        layout_name="layout"
    )
except DocumentServiceError as e:
    print(f"Document processing failed: {e}")
except ExtractionServiceError as e:
    print(f"Extraction failed: {e}")
```
