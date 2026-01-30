# SDM Hierarchical Data

> **For AI Assistants:** This is the complete feature specification. Use the [implementation guide](./sdm-hierarchical-data-implementation.md) for technical details.

**Status:** Proposed  
**Author:** Agent Platform Team  
**Date:** 2026-01-27

---

## Executive Summary

Extend SDM to support hierarchical JSON data structures (from Document Intelligence, API responses, JSON files) with semantic annotations, enabling natural language queries over JSON data.

**Key Capabilities:**

- **Schema definitions in SDM YAML:** Define JSON schemas with semantic annotations (synonyms, descriptions, sample values)
- **JQ transformations:** Declarative schema-to-schema transformations using JQ
- **JQ validations:** Business rules expressed as JQ predicates
- **Natural language queries:** LLM generates JQ queries for hierarchical data
- **LLM-inferred relationships:** LLM discovers schema relationships from semantic annotations

**Expected Impact:**

| Metric | Target |
| ------ | ------ |
| JSON data queryable via NL | 100% of defined schemas |
| DI extraction → SDM integration | Seamless (no manual translation) |
| JQ execution latency | < 500ms |

---

## Problem Statement

### 1. No Semantic Layer for JSON

SDM currently supports only tabular data (database tables, spreadsheets, data frames). JSON data from Document Intelligence extractions, API responses, and files cannot be queried via natural language.

### 2. Disconnected Document Intelligence

DI extracts structured JSON from documents but stores extraction schemas and translation rules outside SDM. DI outputs cannot be semantically described, queried, or transformed using the same tooling as tabular data.

### 3. No Declarative Transformations

Converting JSON between formats (e.g., vendor-specific invoice → canonical invoice) requires application code. There's no way to declare transformations in the data model.

---

## Solution Overview

Add schemas as first-class SDM elements, parallel to tables. At query time, the LLM generates JQ expressions (instead of SQL) to query schema data.

### Example SDM with Schemas

```yaml
name: Invoicing SDM

schemas:
  - name: generic_invoice
    description: 'Standard invoice format across all vendors'
    jsonschema: |
      {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "required": ["invoice_number", "invoice_date", "line_items", "total"],
        "properties": {
          "invoice_number": {
            "type": "string",
            "description": "Unique invoice identifier",
            "synonyms": ["Invoice ID", "Invoice No", "Bill Number"],
            "semantic_type": "dimension",
            "sample_values": ["INV-12345", "2024-001"]
          },
          "total": {
            "type": "number",
            "description": "Total invoice amount",
            "synonyms": ["Grand Total", "Total Amount"],
            "semantic_type": "metric",
            "sample_values": [1234.56, 567.89]
          }
        }
      }

  - name: anahau_invoice
    description: 'Anahau vendor-specific invoice format'
    jsonschema: |
      {
        "type": "object",
        "properties": {
          "id": {
            "type": "string",
            "description": "Anahau invoice identifier",
            "synonyms": ["Invoice ID", "Anahau ID"],
            "semantic_type": "dimension",
            "sample_values": ["ANA-001", "ANA-002"]
          },
          "total_amount": {
            "type": "number",
            "description": "Total invoice amount",
            "synonyms": ["Total", "Amount Due"],
            "semantic_type": "metric",
            "sample_values": [150.00, 299.99]
          }
        }
      }
    transformations:
      - target: generic_invoice
        description: 'Convert Anahau format to generic invoice'
        jq: |
          { invoice_number: .id, total: .total_amount }
    validations:
      - name: total_positive
        description: 'Total must be positive'
        jq: '.total_amount > 0'
```

### What's New

| Concept | Description |
| ------- | ----------- |
| **`schemas` element** | Top-level array in SDM YAML, parallel to `tables` |
| **`jsonschema` attribute** | JSON Schema with semantic annotations (synonyms, semantic_type) |
| **`transformations`** | JQ rules to convert between schema formats |
| **`validations`** | JQ-based business rules |
| **JQ query generation** | LLM generates JQ (in addition to SQL) |

### What's NOT Included (by design)

- **No `sources`** - Data is associated at runtime via DI extraction or MCP
- **No `parent_schema`** - LLM infers relationships from semantic annotations
- **No `related_schemas`** - LLM infers relationships from semantic context

### Data Flow

```mermaid
flowchart TD
    A[Define SDM] --> B[Validate]
    B --> C[Store]
    C --> D[User Question]
    D --> E[LLM]
    E --> F{Table or Schema?}
    F -->|Table| G[Generate SQL]
    F -->|Schema| H[Generate JQ]
    G --> I[Execute]
    H --> I
    I --> J[Results]
```

---

## Requirements

### Functional

| ID | Requirement | Priority |
| -- | ----------- | -------- |
| FR-1 | Define schemas in SDM YAML with semantic annotations | P0 |
| FR-2 | Execute Reducto Extraction with SDM Schema | P1 |
| FR-3 | Query schemas via natural language (LLM generates JQ) | P1 |
| FR-4 | Execute JQ transformations between schemas | P2 |
| FR-5 | Execute JQ validations on schema data | P2 |

### Non-Functional

| ID | Requirement | Target |
| -- | ----------- | ------ |
| NFR-1 | JQ execution latency | < 500ms |
| NFR-2 | Schema parsing latency | < 10ms |

### Expectations

| Name | Expectation |
| ---- | ----------- |
| Max size of input JSON (xform) | 50MB |

---

## Epics & Stories

### Epic A: Schema Definition

**Goals:** Enable schema definitions in SDM YAML with semantic annotations.

---

**Story A-1: Define Schemas in SDM YAML**

> As a data engineer, I want to define JSON schemas in SDM YAML so that hierarchical data has semantic metadata alongside tabular data.

**Context:**

Today, SDM only supports tabular data through the `tables:` array. When Document Intelligence extracts JSON from invoices, receipts, or contracts, that data lives outside the semantic layer. Data engineers must maintain separate metadata for JSON structures, and users cannot query this data using natural language.

By adding a `schemas:` array to SDM YAML, we bring JSON data into the same semantic framework as tables. Each schema includes a JSON Schema definition with embedded semantic annotations (synonyms, descriptions, sample values) that help the LLM understand the data structure. This enables a unified experience where users can query both tabular and hierarchical data.

The design follows the existing SDM pattern: schemas are first-class elements defined declaratively in YAML, validated at parse time, and stored in the database alongside tables and relationships.

**Scope:**

*What this story produces:*
- `Schema` TypedDict in `semantic_data_model_types.py` with fields: `name`, `description`, `jsonschema`, `transformations`, `validations`
- `schemas: list[Schema]` field added to `SemanticDataModel` Pydantic model
- YAML parsing that handles the new `schemas:` array
- Pydantic validation for schema definitions

*What this enables:*
- Data engineers can define JSON schemas in SDM YAML
- Schemas are stored in database alongside tables
- Schema represents the structure of the object (no validation)
- Foundation for DI integration, transformations, and NL queries
- Validations over the object can be expressed in natural language (implemented as JQ exprs)

**Acceptance Criteria:**

- [ ] `schemas` array parsed from SDM YAML without errors
- [ ] Required fields enforced: `name`, `jsonschema`
- [ ] Optional fields supported: `description`, `transformations`, `validations`
- [ ] Invalid schemas rejected with clear error messages
- [ ] Existing SDMs without schemas continue to work (backward compatible)
- [ ] Schema definitions stored in database via existing `set_semantic_data_model()`

**Performance Target:** Schema parsing adds < 10ms to SDM load time

**Edge Cases:**

- Empty `schemas:` array: Treated as no schemas defined
- Duplicate schema names: Rejected with validation error
- Invalid JSON Schema syntax: Rejected with parse error including line number

**Dependencies:** None (builds on existing SDM infrastructure)

---

**Story A-2: Semantic Annotations in JSON Schema**

> As a data engineer, I want to add semantic annotations (synonyms, descriptions, sample values) to JSON Schema properties so that the LLM can understand and query the data.

**Context:**

Standard JSON Schema defines structure (types, required fields) but lacks semantic metadata. When an LLM sees a field named `inv_no`, it may not understand this means "Invoice Number." Similarly, without sample values, the LLM cannot generate accurate filters or understand data patterns.

We extend JSON Schema by allowing semantic annotations directly in property definitions: `synonyms` (alternative names), `description` (what the field represents), `semantic_type` (dimension/measure/attribute), and `sample_values` (example data). These annotations are preserved during parsing and passed to the LLM prompt builder.

This approach keeps schema definitions self-contained—all metadata lives in the JSON Schema rather than scattered across separate files. It also mirrors how we annotate columns in table definitions.

**Scope:**

*What this story produces:*
- JSON Schema parser that preserves custom annotation fields
- Validation that annotations have correct types (arrays, strings)
- Example schema with full annotations in documentation

*What this enables:*
- LLM understands field semantics for accurate query generation
- Users can search by synonyms ("show me Invoice IDs" matches `inv_no`)
- Sample values help LLM generate valid filter expressions

**Acceptance Criteria:**

- [ ] `synonyms` array preserved in parsed schema
- [ ] `description` string preserved in parsed schema
- [ ] `semantic_type` enum (dimension/measure/attribute) preserved
- [ ] `sample_values` array preserved in parsed schema
- [ ] Annotations accessible in prompt builder via schema properties
- [ ] Missing annotations default to empty/null (not errors)

**Edge Cases:**

- Non-standard annotations (typos like `synonms`): Ignored, not rejected
- Very long descriptions (>1000 chars): Truncated in LLM prompts

**Dependencies:** Story A-1 (schema definition)

---

### Epic B: DI Integration

**Goals:** Execute DI extractions using SDM schemas and store extracted data.

---

**Story B-1: Execute DI Extraction with SDM Schema**

> As a developer, I want to run DI extractions using SDM schemas so that extracted data is automatically associated with the schema.

**Context:**

Document Intelligence extracts JSON from uploaded documents (PDFs, images). Currently this data is accessible only through DI-specific APIs. A thread file can be enriched with DI extractions, where each extraction references the SDM schema used. Multiple DI extractions (using different schemas) can be performed on the same thread file.

MCP servers can interact with external APIs and use Schemas to interpret the API responses. This is useful for integrating with systems that expose JSON APIs. The implementation reuses the existing MCP servers infrastructure.

**Scope:**

*What this story produces:*
- Enrichments of thread files with Schema and extracted data
- DI service integration for executing extractions with a specific schema

*What this enables:*
- Extract data from thread files using known SDM Schemas
- Interpret external API responses via known SDM Schemas

**Acceptance Criteria:**

- [ ] Run extractions using different schemas against one file, interact with all outputs
- [ ] Fetch JSON data via MCP, interpret resulting object as an SDM schema
- [ ] Multiple extractions stored per thread file
- [ ] Extracted data queryable via NL

**Performance Target:** TBD

**Edge Cases:**

- API returns non-JSON: Error with content-type info
- DI extraction fails: Error with extraction details

**Dependencies:** Story A-1 (schema definition), DI service API (existing)

---

### Epic C: Transformations & Validations

**Goals:** Execute JQ transformations and validations with clear error messages.

---

**Story C-1: Execute JQ Transformations**

> As a data engineer, I want to define JQ transformations between schemas so that I can convert data formats declaratively.

**Context:**

Different systems use different JSON structures for the same concepts. A Costco receipt has different fields than an Amazon invoice, but both represent purchase data. Today, converting between formats requires application code that's hard to maintain and not visible in the data model.

JQ transformations let data engineers declare conversions in the schema definition. When a query needs data in a target schema format, the system automatically applies the transformation. This keeps conversion logic visible, testable, and versioned alongside the data model.

We reuse the existing `apply_jq_transform()` function from the orchestrator, which handles JQ execution safely with timeout and error handling.

**Scope:**

*What this story produces:*
- `SchemaTransformation` TypedDict with `target`, `description`, `jq` fields
- `execute_transformation()` function using existing `apply_jq_transform()`
- Transformation chaining (A → B → C)

*What this enables:*
- Declarative format conversions in SDM
- Automatic transformation during queries
- Visible, testable conversion logic

**Acceptance Criteria:**

- [ ] Transformations execute via `apply_jq_transform()`
- [ ] Target schema name validated against defined schemas
- [ ] Transformation errors include JQ expression and input sample
- [ ] Chained transformations execute in order
- [ ] Circular transformation chains detected and rejected

**Performance Target:** < 500ms for single transformation

**Edge Cases:**

- JQ syntax error: Clear error with expression and position
- JQ produces invalid JSON for target schema: Validation error
- Empty input: Return empty output (not error)

**Dependencies:** Story A-1 (schema definition), Existing `apply_jq_transform()` (no changes needed)

---

**Story C-2: Execute JQ Validations**

> As a data engineer, I want to define JQ validation rules so that I can enforce business rules on schema data.

**Context:**

Business rules like "invoice total must equal sum of line items" or "date must be in the past" are hard to enforce without application code. JQ validations let data engineers express these rules as JQ predicates that return true/false. Validations should strive to include context as to the reason for the failure.

Validations run when data is resolved. Failed validations can be configured to warn or reject. The validation results are available in query responses so users understand data quality issues.

**Scope:**

*What this story produces:*
- `SchemaValidation` TypedDict with `name`, `description`, `jq` fields
- `validate_schema_data()` function returning list of failures
- Validation mode: `warn` (log and continue) or `reject` (error)

*What this enables:*
- Declarative business rules in SDM
- Data quality visibility in query responses
- Consistent validation across all data sources

**Acceptance Criteria:**

- [ ] Validations execute as JQ predicates
- [ ] Failed validations return rule name and description
- [ ] `warn` mode logs failures but returns data
- [ ] `reject` mode returns error with all failures listed
- [ ] Validation timeout prevents infinite loops (default 5s)

**Performance Target:** < 100ms per validation rule

**Edge Cases:**

- JQ returns non-boolean: Treated as failure
- Multiple failures: All reported, not just first
- Validation on empty data: Skip validation, return success

**Dependencies:** Story A-1 (schema definition), Existing `apply_jq_transform()` (no changes needed)

---

### Epic D: Natural Language Queries

**Goals:** Include schema context in LLM prompts and generate JQ queries.

---

**Story D-1: Include Schemas in LLM Prompts**

> As a developer, I want schema context included in LLM prompts so that the LLM can generate queries for hierarchical data.

**Context:**

The prompt builder (`summarize_data_model()`) currently includes only table metadata. For the LLM to query schemas, it needs schema context: field names, descriptions, types, and semantic annotations.

We extend the prompt builder to include a "JSON Schemas" section listing each schema with its fields and annotations. This gives the LLM enough context to understand what data is available and how to query it.

**Scope:**

*What this story produces:*
- Extension to `summarize_data_model()` in `kernel/semantic_data_model.py`
- Schema summary format: name, description, field list with types
- Semantic annotations included in field descriptions

*What this enables:*
- LLM understands available schemas
- LLM can generate JQ queries for schema data
- Unified prompt with tables and schemas

**Acceptance Criteria:**

- [ ] Schemas appear in prompt under "## JSON Schemas" section
- [ ] Each schema lists name and description
- [ ] Schema fields listed with types and semantic annotations
- [ ] Prompt size increase < 500 tokens per schema
- [ ] Empty schemas array produces no schema section

**Performance Target:** < 10ms added to prompt generation

**Edge Cases:**

- Very large schema (100+ fields): Truncate to top 50 fields
- Deeply nested schema: Flatten to 2 levels in prompt
- No annotations: Use field name as description

**Dependencies:** Story A-1 (schema definition), Story A-2 (semantic annotations)

---

**Story D-2: Generate and Execute JQ Queries**

> As a user, I want to ask questions about JSON data in natural language so that I can query hierarchical data without writing JQ.

**Context:**

When the user provides JSON data without a known/matched schema, the Agent should implicitly be able to create a Schema from that object.

For all JSON objects with Schemas, the LLM can generate JQ queries to answer user questions. The execution path mirrors SQL: LLM generates JQ, system executes it against resolved schema data, results returned to user.

The LLM must decide whether a question targets tables (generate SQL) or schemas (generate JQ). This decision is based on entity mentions in the question matched against table/schema names and field names.

Users can see generated schemas, edit them, and save the schema in an SDM for future use.

**Scope:**

*What this story produces:*
- JQ query execution path in orchestrator
- LLM prompt instruction for JQ generation
- Entity matching to determine SQL vs JQ
- Implicit schema generation from JSON objects

*What this enables:*
- Natural language queries over JSON data
- Unified query experience for tables and schemas
- Complete hierarchical data support in SDM

**Acceptance Criteria:**

- [ ] LLM generates valid JQ for schema questions (unsaved in SDM)
- [ ] JQ queries execute against resolved schema data
- [ ] Results formatted consistently with SQL results
- [ ] Mixed questions (table + schema) generate appropriate query type
- [ ] Invalid JQ returns error with LLM retry
- [ ] Generated Schemas can be saved in an SDM

**Performance Target:** End-to-end query < 3s (including LLM)

**Edge Cases:**

- Ambiguous question (could be table or schema): Prefer table (existing behavior)
- JQ produces no results: Return empty with explanation
- JQ produces too many results (>1000): Truncate with warning

**Dependencies:** Story D-1 (schema context in prompts), Story B-1 (DI integration)

---

## Use Cases

### Use Case 1: Schema Definition

**Actor:** Data Engineer  
**Goal:** Define a schema for Costco receipts

1. Engineer creates SDM YAML with `costco_receipt` schema
2. System validates and stores SDM
3. Engineer can query: _"Show Costco receipts over $500"_

---

### Use Case 2: Schema Transformation

**Actor:** Data Engineer  
**Goal:** Transform vendor-specific invoice to generic format

1. DI extracts JSON matching `anahau_invoice` schema
2. User asks: _"Show all invoices over $1000"_
3. LLM applies transformation to `generic_invoice` format
4. Results include transformed Anahau data

---

### Use Case 3: Implicit Schema Generation

**Actor:** Business User  
**Goal:** Query JSON without pre-defining a schema

1. User uploads `purchase_order.json`
2. User asks: _"What's the total value?"_
3. LLM creates implicit schema and generates JQ query
4. User can save generated schema to SDM

---

## Success Metrics

| Metric | Baseline | Target |
| ------ | -------- | ------ |
| JSON data queryable via NL | 0% | 100% of defined schemas |
| JQ execution latency | N/A | < 500ms p95 |
| DI → SDM integration time | Manual (hours) | Declarative (minutes) |

---

## References

- [Implementation Guide](./sdm-hierarchical-data-implementation.md) - Technical implementation details
