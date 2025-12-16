# Document Intelligence UI Guide

## Overview

The Document Intelligence (DocIntel) feature allows you to parse and extract structured data from documents (PDFs, images, etc.) within conversational agents. There are two primary modes: **Parse** and **Extract**.

## Getting Started

### Configuration (Admin)

Before using Document Intelligence, an administrator must configure the service:

1. Navigate to **Configuration** in the sidebar
2. Select the **Document Intelligence** tab
3. Configure the following settings:
   - **Document Intelligence Endpoint**: The backend service URL (e.g., `https://backend.sema4.ai/reducto`)
   - **Document Intelligence API Key**: Your API key for the document processing service
   - **Bring your Own Database**: Configure database storage for extracted data (e.g., "Local DB")

### Accessing DocIntel

1. Navigate to a conversational agent that supports Document Intelligence
   - To enable Document Intelligence, create an agent in Studio and check "Enable Document Intelligence" in the agent settings
2. Upload or select a document from the conversation files panel (right side)
3. The agent will automatically process the document based on your instructions

## Features & Modes

### 1. Parse Mode (`di-parse-only`)

**Purpose:** Parse documents into structured chunks without extraction schema.

**Use Cases:**

- Quick document analysis
- Viewing document structure and content
- Extracting text from images or PDFs

**How to Use:**

1. Upload a document to the conversation
2. Ask the agent to "parse" the document or select "Parse" from document options
3. View the parsed results in the right panel

**What You Get:**

- Document chunks with text content
- Metadata about the document
- Visual highlighting on the document (if PDF)
- Raw JSON view (toggle available)

**Actions Available:**

- **View as JSON:** Toggle to see raw JSON output
- **Close:** Close the parse dialog

---

### 2. Extract Mode (`di-extract-only`)

**Purpose:** Extract structured data from documents using a customizable schema.

**Use Cases:**

- Extracting invoice details (payer, payee, amounts, dates)
- Processing forms with specific fields
- Structured data extraction with custom schemas

**How to Use:**

#### Step 1: Initial Setup

1. Upload a document to the conversation
2. Ask the agent to extract specific information (e.g., "Extract payment details from this invoice")
3. The system automatically generates a schema based on your request

#### Step 2: Configuration Tab

The Configuration tab allows you to:

**View & Edit Schema:**

- See the generated extraction schema
- View in table format or raw JSON (toggle "View as JSON")
- Each field shows:
  - **Name:** Field identifier (e.g., `payer`, `bank_details`)
  - **Type:** Data type (`text`, `object`, `array`)
  - **Description:** What the field represents

**Schema Management:**

- **Add Field:** Click "+ Add Field" to add new fields manually
- **Delete Field:** Click trash icon next to any field
- **Edit Fields:** Click field names or descriptions to edit
- **Restore Field:** Accidentally deleted? Use "Restore Field" button
- **Expand/Collapse:** Click arrows next to `object` or `array` types to view nested fields

**Schema Regeneration:**

- Click **"Regenerate"** button to generate a new schema
- Provide custom instructions in the dialog
- Useful if initial schema doesn't match your needs

**Changes Tracking:**

- Orange indicator shows "Changes pending" when schema is modified
- Green checkmark indicates configuration is up to date
- Must click "Re-Run Extract" to apply changes

#### Step 3: Re-Run Extract

After making schema changes:

1. Click **"Re-Run Extract"** button (bottom right)
2. System processes document with updated schema
3. Wait for extraction to complete
4. Results automatically appear in Results tab

#### Step 4: Results Tab

View extraction results:

**Visual Highlighting:**

- Extracted fields are highlighted on the document (left panel)
- Click highlighted regions to see corresponding data (right panel)
- Click data blocks (right panel) to highlight source location (left panel)

**Results Panel:**

- Structured display of extracted data
- Expandable/collapsible sections for nested objects
- Click any block to locate on document

**Actions Available:**

- **View as JSON:** Toggle to see raw JSON output
- **Use in Conversation:** Send results back to agent thread
- **Regenerate:** Generate new schema and re-extract
- **Close:** Close the extract dialog

---

## Interface Layout

### Document Viewer (Left Panel)

- **PDF/Image Display:** Visual representation of your document
- **Page Navigation:** Navigate multi-page documents
- **Zoom Controls:** Zoom in/out on document
- **Highlighted Regions:** Visual indicators for extracted/parsed content
- **Interactive:** Click highlighted regions to see data details

### Results Panel (Right Panel)

- **Resizable:** Drag the center handle to resize
- **Tabbed Interface (Extract mode):**
  - **Configuration Tab:** Schema editing and configuration
  - **Results Tab:** Extracted data display
- **Footer Controls:** Toggle JSON view, action buttons

---

## Common Workflows

### Workflow 1: Quick Invoice Extraction

1. Upload invoice PDF
2. Tell agent: "Extract key payment details from this invoice"
3. Review auto-generated schema in Configuration tab
4. Click Results tab to view extracted data
5. Click "Use in Conversation" to continue working with data

### Workflow 2: Custom Schema Extraction

1. Upload document
2. Tell agent: "Extract data from this form"
3. Go to Configuration tab
4. Click "Regenerate" and provide specific instructions
5. Review and edit generated schema as needed
6. Add/remove fields manually if required
7. Click "Re-Run Extract" to apply changes
8. Review results in Results tab

### Workflow 3: Parse Only

1. Upload document
2. Tell agent: "Parse this document"
3. Review parsed chunks in results panel
4. Toggle JSON view if needed
5. Use parsed data in conversation

---

## Current Capabilities

### ✅ What Works

- **Automatic schema generation** based on natural language instructions
- **Manual schema editing** (add, edit, delete fields)
- **Re-extraction** with modified schemas
- **Visual highlighting** of extracted data on documents
- **Bidirectional selection** (click document ↔ click results)
- **JSON view toggle** for raw data inspection
- **Results to conversation** integration
- **Multi-page PDF support**
- **Parse mode** for unstructured extraction
- **Schema regeneration** with custom instructions

### 🚧 Known Limitations

- **Annotation mode temporarily disabled** - Feature existed but is currently inactive
- **Escape key disabled** in dialogs to prevent accidental closure
- **Configuration tab locked during processing** - Cannot edit while generating or extracting
- **No undo/redo** for schema changes (must manually revert)
- **Results tab disabled during processing** - Cannot switch tabs while generating schema or extracting

---

## Tips & Best Practices

### Schema Design

- **Be specific** in field descriptions - helps extraction accuracy
- **Use nested objects** for related data (e.g., `payer.name`, `payer.address`)
- **Use arrays** for repeated items (e.g., `line_items`, `invoice_list`)
- **Use descriptive field names** (snake_case recommended)

### Extraction Accuracy

- **Provide clear instructions** when requesting extractions
- **Review generated schema** before accepting results
- **Regenerate if needed** - first attempt may not be perfect
- **Add missing fields** manually if auto-generation missed them

### Performance

- **Large documents** may take longer to process
- **Complex schemas** (many fields) increase processing time
- **Re-extraction** is faster than initial extraction
- **Parse mode** is faster than Extract mode

---

## Troubleshooting

### Issue: Schema doesn't match my needs

- **Solution:** Click "Regenerate" and provide more specific instructions
- **Alternative:** Manually edit schema fields in Configuration tab

### Issue: Extraction results are incomplete

- **Solution:** Check if schema has all required fields
- **Action:** Add missing fields and click "Re-Run Extract"

### Issue: Changes pending indicator stuck

- **Solution:** Click "Re-Run Extract" to apply changes
- **Note:** Dialog warns if you try to close with unsaved changes

### Issue: Cannot switch to Results tab

- **Cause:** Schema generation or extraction in progress
- **Solution:** Wait for processing to complete

### Issue: Visual highlights don't match data

- **Cause:** Re-extraction needed after schema changes
- **Solution:** Click "Re-Run Extract" to refresh

---

## Keyboard & Mouse

### Mouse Actions

- **Click highlighted region:** View corresponding data
- **Click data block:** Highlight source location
- **Drag resize handle:** Adjust panel width
- **Click field row:** Expand/collapse nested fields

### Current Keyboard Behavior

- **Escape key:** Currently disabled in dialogs (prevents accidental closure)
- **Standard editing:** Works in text fields for schema editing

---

## Feature Status

| Feature             | Status           | Notes                         |
| ------------------- | ---------------- | ----------------------------- |
| Parse Mode          | ✅ Working       | Fully functional              |
| Extract Mode        | ✅ Working       | Fully functional              |
| Schema Generation   | ✅ Working       | AI-powered                    |
| Schema Editing      | ✅ Working       | Manual editing supported      |
| Re-extraction       | ✅ Working       | Applies schema changes        |
| Visual Highlighting | ✅ Working       | Bidirectional selection       |
| JSON View           | ✅ Working       | Toggle available              |
| Use in Conversation | ✅ Working       | Sends results to thread       |
| Regenerate Schema   | ✅ Working       | Custom instructions supported |
| Annotation Mode     | ❌ Disabled      | Temporarily unavailable       |
| Undo/Redo           | ❌ Not Available | Manual revert only            |

---

## API Endpoints Used

- **Parse:** `/api/v2/document-intelligence/documents/parse`
- **Generate Schema:** `/api/v2/document-intelligence/documents/generate-schema`
- **Extract:** `/api/v2/document-intelligence/documents/extract`

---

## Developer Notes

### File Structure

```
DocIntel/
├── ParseOnly/           # Parse mode components
├── ExtractOnly/         # Extract mode components
│   ├── ConfigurationPanel.tsx
│   ├── ExtractResultsPanel.tsx
│   ├── SchemaEditor.tsx
│   └── hooks/
└── shared/              # Shared components & utilities
    ├── components/
    ├── hooks/
    ├── utils/
    └── types.ts
```

### Key Components

- `ExtractOnlyDialog` - Main extract mode dialog
- `ParseOnlyDialog` - Main parse mode dialog
- `DocumentViewer` - PDF/image viewer with highlighting
- `SchemaEditor` - Schema configuration interface
- `ConfigurationPanel` - Extract configuration tab
- `ExtractResultsPanel` - Extract results tab

### State Management

- Uses React hooks for local state
- `useExtractDialogState` - Manages extract workflow
- `useResizablePanel` - Panel resizing logic
- `useResultsSelection` - Bidirectional selection
- `usePdfAnnotations` - (Disabled) Annotation features

---

## Future Enhancements

- Re-enable annotation mode for manual field selection
- Add undo/redo for schema changes
- Support for more document types (Word, Excel, etc.)
- Batch processing multiple documents
- Save/load custom schemas
- Schema templates library
- Export results to various formats

---

## Support

For issues or questions:

1. Check this documentation
2. Review agent-specific capabilities
3. Consult codebase at `workroom/spar-ui/src/components/DocIntel/`
4. Check console for error messages (View as JSON can help debug)
