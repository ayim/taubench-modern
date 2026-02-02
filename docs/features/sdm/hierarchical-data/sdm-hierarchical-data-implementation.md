# Implementation Guide: SDM Hierarchical Data

> **For AI Assistants:** Map stories to implementation. Follow `python-guidelines` skill. Reuse existing SDM infrastructure for schemas, JQ for transformations.

**Date:** 2026-01-27
**Specification:** See [feature specification](./sdm-hierarchical-data.md) for requirements, design, and examples

---

## Table of Contents

1. [Story-to-Implementation Mapping](#story-to-implementation-mapping)
2. [System Architecture](#system-architecture)
3. [Sequence Diagrams](#sequence-diagrams)
4. [Data Flow](#data-flow)
5. [Design Decisions](#design-decisions)
6. [Data Structures](#data-structures)
7. [API Design](#api-design)
8. [Core Algorithm](#core-algorithm)
9. [Migration Strategy](#migration-strategy)
10. [References](#references)

---

## Story-to-Implementation Mapping

### Epic Order: A → C → B → D

The extraction pipeline (Epic B) uses transform/validate engines from Epic C, so Epic C must be implemented first.

| Story | Description                           | Implementation Sections                     |
| ------- | --------------------------------------- | --------------------------------------------- |
| A-1   | Define Schemas in SDM YAML            | §6 Data Structures (Schema TypedDicts)     |
| A-2   | Semantic Annotations in JSON Schema   | §6 Data Structures (annotation parsing)    |
| C-1   | Execute JQ Transformations            | §8 Core Algorithm (execute_transformation) |
| C-2   | Execute JQ Validations                | §8 Core Algorithm (validate_schema_data)   |
| B-1   | DI Extraction with Reducto            | §8 Core Algorithm (Reducto integration)    |
| B-2   | MCP/API Response Handling             | §8 Core Algorithm (API data packaging)     |
| B-3   | Extraction Pipeline Orchestration     | §8 Core Algorithm (pipeline orchestration) |
| D-1   | Include Schemas in LLM Prompts        | §7 API Design (prompt builder extension)   |
| D-2   | Generate and Execute JQ Queries       | §8 Core Algorithm (JQ execution path)      |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     SDM YAML Definition                      │
│  ┌─────────────────┐              ┌─────────────────┐       │
│  │    tables:      │              │    schemas:     │       │
│  │   (existing)    │              │     (NEW)       │       │
│  └─────────────────┘              └────────┬────────┘       │
└────────────────────────────────────────────┼────────────────┘
                                             │
                                             ▼
                    ┌─────────────────────────────────────────────────┐
                    │              Schema Definition                   │
                    │  ┌─────────────────────────────────────────┐    │
                    │  │ jsonschema + annotations + transforms   │    │
                    │  │ + validations                           │    │
                    │  └─────────────────────────────────────────┘    │
                    └────────────────────────┬────────────────────────┘
                                             │
                                             ▼
                    ┌─────────────────────────────────────────────────┐
                    │              Prompt Builder                      │
                    │  Tables + Schemas → LLM Context                  │
                    └────────────────────────┬────────────────────────┘
                                             │
                                             ▼
                    ┌─────────────────────────────────────────────────┐
                    │                   LLM                            │
                    │  NL Query → SQL (tables) or JQ (schemas)        │
                    │  Infers schema relationships from annotations   │
                    └────────────────────────┬────────────────────────┘
                                             │
                         ┌───────────────────┴───────────────────┐
                         ▼                                       ▼
              ┌─────────────────────┐              ┌─────────────────────┐
              │   SQL Execution     │              │    JQ Execution     │
              │   (existing)        │              │    (NEW path)       │
              └─────────────────────┘              └─────────────────────┘


Data Flow (Runtime - Data Acquisition Pipeline):

┌───────────────┐                     ┌───────────────┐
│   Document    │                     │   API/MCP     │
└───────┬───────┘                     └───────┬───────┘
        │                                     │
        ▼                                     ▼
┌───────────────┐                     ┌───────────────┐
│ B-1: Reducto  │                     │ B-2: Receive  │
│   Extract     │                     │   JSON        │
└───────┬───────┘                     └───────┬───────┘
        │ raw JSON                            │ raw JSON
        └─────────────────┬───────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │   B-3: Pipeline       │
              │ ┌───────────────────┐ │
              │ │ C-1: Transform    │ │
              │ │ (source→generic)  │ │
              │ └─────────┬─────────┘ │
              │           ▼           │
              │ ┌───────────────────┐ │
              │ │ C-2: Validate     │ │
              │ │ (run JQ rules)    │ │
              │ └─────────┬─────────┘ │
              │           ▼           │
              │ ┌───────────────────┐ │
              │ │ Store Enrichment  │ │
              │ │ (thread metadata) │ │
              │ └───────────────────┘ │
              └───────────────────────┘
```

**Components:**


| Component         | Purpose                   | Technology       | Location                       |
| ------------------- | --------------------------- | ------------------ | -------------------------------- |
| Schema Models     | Define schema structure   | Python/Pydantic  | `semantic_data_model_types.py` |
| Prompt Builder    | Add schema context        | Python           | `semantic_data_model.py`       |
| JQ Executor       | Run JQ queries            | jq/pyjq          | `_jq_transform.py` (existing)  |
| B-1 DI Extract    | Reducto extraction        | Python           | `di_service.py` (existing)     |
| B-2 API Receive   | Package API JSON          | Python           | NEW                            |
| B-3 Pipeline      | Orchestrate extract flow  | Python           | NEW                            |
| Enrichment Store  | Store runtime data        | AgentServer DB (thread metadata) | Thread metadata       |

---

## Sequence Diagrams

### Schema Query Execution (Epic D)

```
User    Orchestrator    PromptBuilder    LLM    Storage    JQExecutor
 │           │               │            │        │            │
 │──query───▶│               │            │        │            │
 │           │──get_context─▶│            │        │            │
 │           │◀──tables+schemas──         │        │            │
 │           │──────────────prompt───────▶│        │            │
 │           │◀─────────────jq_query──────│        │            │
 │           │──get_enrichment────────────────────▶│            │
 │           │◀──json_data────────────────────────-│            │
 │           │──execute_jq─────────────────────────────────────▶│
 │           │◀──result──────────────────────────────────-──────│
 │◀──result──│               │            │        │            │
```

**Steps:**

1. User submits natural language query
2. Orchestrator requests context from PromptBuilder (includes schemas)
3. LLM generates JQ query for schema data
4. Storage retrieves schema enrichment (extracted data) for thread file
5. JQExecutor runs JQ expression
6. Result returned to user

### Extraction Pipeline (Epic B)

```
Agent    B1_Reducto    B2_API    B3_Pipeline    C1_Transform    C2_Validate    Storage
  │           │           │           │              │               │            │
  │──doc+schema──────────▶│           │              │               │            │
  │           │──parse────▶│           │              │               │            │
  │           │──extract──▶│           │              │               │            │
  │           │◀──raw_json─│           │              │               │            │
  │◀──raw_json─│           │           │              │               │            │
  │                        │           │              │               │            │
  │ ─── OR ───             │           │              │               │            │
  │                        │           │              │               │            │
  │──api_json+schema──────────────────▶│              │               │            │
  │◀──raw_schema_data──────────────────│              │               │            │
  │                        │           │              │               │            │
  │ ─── THEN ───           │           │              │               │            │
  │                        │           │              │               │            │
  │──raw_data─────────────────────────▶│              │               │            │
  │           │           │            │──transform──▶│               │            │
  │           │           │            │◀──transformed│               │            │
  │           │           │            │──validate────────────────────▶│            │
  │           │           │            │◀──results────────────────────│            │
  │           │           │            │──store_enrichment────────────────────────▶│
  │           │           │            │◀──stored─────────────────────────────────│
  │◀──enrichment───────────────────────│              │               │            │
```

**Pipeline Steps:**

1. B-1 (Reducto) or B-2 (API) produces raw JSON
2. B-3 Pipeline receives raw data
3. C-1 Transform applies source→generic transformation (if defined)
4. C-2 Validate runs JQ validation rules
5. Store enrichment in thread metadata
6. Return SchemaEnrichment to agent

---

## Data Flow

```
YAML → Parse → Validate → Store → Query → Resolve → Execute → Result
         │        │         │       │        │         │
         ▼        ▼         ▼       ▼        ▼         ▼
      Schema   Pydantic   SDM    Prompt   Source    JQ/SQL
      Types    Validation  JSONB  Builder   Data     Engine
```

**Transformations:**


| Stage    | Input             | Output           | Component                    |
| ---------- | ------------------- | ------------------ | ------------------------------ |
| Parse    | YAML string       | Schema dict      | YAML parser                  |
| Validate | Schema dict       | Validated Schema | Pydantic                     |
| Store    | SemanticDataModel | SDM JSONB row    | AgentServer DB (SDM table)   |
| Query    | NL question       | JQ expression    | LLM                          |
| Resolve  | SchemaSource      | JSON data        | SourceResolver               |
| Execute  | JQ + JSON         | Query result     | JQExecutor                   |

---

## Design Decisions

### Decision 1: Schemas as First-Class SDM Elements

**Problem:** How to represent hierarchical JSON data in SDM?

**Options:**


| Option                          | Pros                     | Cons                         |
| --------------------------------- | -------------------------- | ------------------------------ |
| A: Extend tables with JSON type | Consistent with existing | Loses hierarchical structure |
| B: Separate`schemas:` array     | Clear separation         | More complex SDM             |
| C: Metadata-only (no querying)  | Simple                   | Can't query JSON data        |

**Chosen:** Option B - Separate `schemas:` array

**Rationale:** Schemas are fundamentally different from tables (hierarchical vs flat). A parallel structure makes both first-class citizens and allows schema-specific features (transformations, validations) without cluttering table definitions.

---

### Decision 2: JQ for Transformations

**Problem:** How to express schema-to-schema transformations?

**Options:**


| Option                  | Pros                               | Cons                         |
| ------------------------- | ------------------------------------ | ------------------------------ |
| A: Custom DSL           | Tailored to use case               | Learning curve, maintenance  |
| B: JQ                   | Powerful, standard, existing infra | JQ syntax complexity         |
| C: JSONPath + templates | Simpler syntax                     | Limited transformation power |

**Chosen:** Option B - JQ

**Rationale:** JQ is already used in the codebase (`_jq_transform.py`), is industry-standard for JSON transformations, and is powerful enough for complex mappings. The syntax complexity is offset by excellent documentation and LLM familiarity.

---

### Decision 3: Semantic Annotations in JSON Schema

**Problem:** How to add semantic metadata (synonyms, descriptions) to schema fields?

**Chosen:** Embed annotations directly in JSON Schema properties

**Rationale:** JSON Schema allows custom keywords. Embedding `synonyms`, `semantic_type`, and `sample_values` directly in property definitions keeps schema definitions self-contained. This mirrors how column annotations work in table definitions.

---

## Data Structures

**TypedDict policy:** Do not use `TypedDict` or raw dictionaries for domain models or pipeline objects. Use Pydantic `BaseModel` (preferred) or `@dataclass` to enforce invariants and validation. This follows the Python guidelines.

### Existing Infrastructure to Reuse


| Component          | Location                                   | How to reuse                     |
| -------------------- | -------------------------------------------- | ---------------------------------- |
| SDM types          | `core/.../semantic_data_model_types.py`    | Add `schemas: list[Schema]`      |
| SDM storage        | `server/.../storage/base.py`               | Stores SDM in AgentServer DB (JSONB) |
| Prompt builder     | `server/.../kernel/semantic_data_model.py` | Extend for schemas               |
| JQ execution       | `server/.../orchestrator/_jq_transform.py` | Use directly for C-1, C-2        |
| DI service         | `document-intelligence/.../services/`      | B-1: Extract with SDM schema     |
| Thread metadata    | `server/.../storage/base.py`               | B-3: Store enrichments (NEW)     |
| MCP infrastructure | Existing                                   | B-2: Receive API JSON            |

### New Types

Add to `core/src/agent_platform/core/data_frames/semantic_data_model_types.py`:

```python
from pydantic import BaseModel, Field

class SchemaTransformation(BaseModel):
    target: str
    description: str | None = None
    jq: str

class SchemaValidation(BaseModel):
    name: str
    description: str | None = None
    jq: str

class Schema(BaseModel):
    name: str
    description: str | None = None
    jsonschema: dict[str, object] = Field(description="JSON Schema document")
    transformations: list[SchemaTransformation] = Field(default_factory=list)
    validations: list[SchemaValidation] = Field(default_factory=list)
```

**Note:** Schemas do not have explicit `sources`, `parent_schema`, or `related_schemas` fields. Data is associated with schemas at runtime via DI extraction or MCP. The LLM infers relationships between schemas from semantic annotations.

Update `SemanticDataModel`:

```python
class SemanticDataModel(BaseModel):
    name: str
    tables: list[LogicalTable] = Field(default_factory=list)
    schemas: list[Schema] = Field(default_factory=list)  # NEW
    relationships: list[Relationship] | None = None
```

### Runtime Types (Epic B-3)

```python
JsonValue = dict[str, object] | list[object] | str | int | float | bool | None

@dataclass
class RawSchemaData:
    """Input to pipeline from B-1 or B-2."""
    source_type: Literal["file", "api"]
    source_id: str
    source_metadata: dict | None
    schema_name: str
    sdm_name: str
    raw_data: JsonValue

@dataclass
class ValidationResult:
    """Result of a single validation rule."""
    rule_name: str
    passed: bool
    message: str | None
    mode: Literal["warn", "reject"]

@dataclass
class SchemaEnrichment:
    """Runtime data linking transformed JSON to an SDM schema.
    
    Stored in thread/workflow metadata, NOT in the SDM.
    """
    enrichment_id: str
    thread_id: str
    source_type: Literal["file", "api"]
    source_id: str
    source_metadata: dict | None
    source_schema_name: str      # Original schema (e.g., costco_receipt)
    target_schema_name: str      # Final schema (e.g., generic_receipt)
    sdm_name: str
    extracted_data: JsonValue    # Final transformed data
    extraction_timestamp: datetime
    validation_results: list[ValidationResult]
```

**Key Principle: Design Time vs Runtime**

| Aspect | SDM (Design Time) | Enrichments (Runtime) |
|--------|------------------|----------------------|
| **What** | Schema definitions | Extracted data per file |
| **Volume** | 10s of schemas | 1000s of files |
| **Lifecycle** | Long-lived | Tied to thread |
| **Storage** | SDM YAML → AgentServer DB (JSONB in SDM table) | AgentServer thread metadata (not external DB) |

Enrichments reference SDM schemas by name. They are NOT stored in the SDM itself.

---

## API Design

### Prompt Builder Extension

Extend `summarize_data_model()` in `server/.../kernel/semantic_data_model.py`:

```python
def summarize_data_model(model: SemanticDataModel, engine: str) -> str:
    # ... existing table summarization ...

    # NEW: Add schema summarization
    if schemas := model.get("schemas"):
        output += "\n## JSON Schemas (queryable with JQ)\n"
        for schema in schemas:
            output += f"\n### {schema['name']}\n"
            if desc := schema.get("description"):
                output += f"{desc}\n"
            if props := schema.get("jsonschema", {}).get("properties"):
                output += f"Fields: {', '.join(props.keys())}\n"
  
    return output
```

### No REST API Changes

Schema definitions are part of SDM YAML, stored via existing `set_semantic_data_model()`. No new REST endpoints needed.

---

## Core Algorithm

### Story B-1: DI Extraction with Reducto

Extracts raw JSON from documents using Reducto. Does NOT transform or validate.

```python
async def di_extract(
    file_id: str,
    schema_name: str,
    sdm_name: str,
) -> dict:
    """Extract data from document using Reducto.
    
    Returns raw extracted JSON (no transformation).
    Pipeline processing happens in Story B-3.
    """
    # Get schema from SDM
    schema = await get_schema(schema_name, sdm_name)
    jsonschema = schema["jsonschema"]
    
    # Parse document with Reducto
    parsed_doc = await reducto.parse(file_id)
    
    # Extract with schema
    raw_data = await reducto.extract(jsonschema, parsed_doc)
    
    return raw_data  # Raw, no transformation
```

### Story B-2: MCP/API Response Handling

Receives JSON from APIs and packages for pipeline processing.

```python
@dataclass
class RawSchemaData:
    """Input to pipeline from B-1 or B-2."""
    source_type: Literal["file", "api"]
    source_id: str
    source_metadata: dict | None
    schema_name: str
    sdm_name: str
    raw_data: dict

async def receive_api_response(
    json_data: dict,
    schema_name: str,
    sdm_name: str,
    source_metadata: dict | None = None,
) -> RawSchemaData:
    """Package API response for pipeline processing."""
    # Validate schema exists
    await get_schema(schema_name, sdm_name)  # Raises if not found
    
    return RawSchemaData(
        source_type="api",
        source_id=str(uuid.uuid4()),
        source_metadata=source_metadata,
        schema_name=schema_name,
        sdm_name=sdm_name,
        raw_data=json_data,
    )
```

### Story B-3: Extraction Pipeline Orchestration

Orchestrates transform → validate → store.

```python
@dataclass
class SchemaEnrichment:
    """Runtime data linking transformed JSON to an SDM schema."""
    enrichment_id: str
    thread_id: str
    source_type: Literal["file", "api"]
    source_id: str
    source_metadata: dict | None
    source_schema_name: str      # e.g., costco_receipt
    target_schema_name: str      # e.g., generic_receipt
    sdm_name: str
    extracted_data: dict         # Final transformed data
    extraction_timestamp: datetime
    validation_results: list[ValidationResult]

async def process_pipeline(
    thread_id: str,
    raw_data: RawSchemaData,
) -> SchemaEnrichment:
    """Process raw data through transform/validate/store pipeline."""
    
    # 1. Get schema definition
    schema = await get_schema(raw_data.schema_name, raw_data.sdm_name)
    
    # 2. Transform (if defined)
    transformed_data, target_schema_name = await _apply_transformation(
        raw_data.raw_data, 
        schema
    )
    
    # 3. Validate
    validation_results = await _run_validations(
        transformed_data, 
        schema.get("validations", [])
    )
    
    # Check for reject-mode failures
    rejects = [r for r in validation_results if not r.passed and r.mode == "reject"]
    if rejects:
        raise ValidationRejectError(f"Validation rejected: {rejects}")
    
    # 4. Store enrichment
    enrichment = await create_enrichment(
        thread_id=thread_id,
        source_type=raw_data.source_type,
        source_id=raw_data.source_id,
        source_metadata=raw_data.source_metadata,
        source_schema_name=raw_data.schema_name,
        target_schema_name=target_schema_name,
        sdm_name=raw_data.sdm_name,
        extracted_data=transformed_data,
        validation_results=validation_results,
    )
    
    return enrichment
```

### Story C-1 & C-2: JQ Execution

Transform and validate engines used by B-3 pipeline.

```python
from agent_platform.orchestrator._jq_transform import apply_jq_transform

async def _apply_transformation(
    data: dict, 
    schema: Schema
) -> tuple[dict, str]:
    """Apply transformation if defined.
    
    Returns (transformed_data, target_schema_name).
    If no transformation, returns (data, source_schema_name).
    """
    transformations = schema.get("transformations", [])
    if not transformations:
        return data, schema["name"]
    
    # Apply first transformation (could extend to chain)
    transform = transformations[0]
    transformed = apply_jq_transform(data, transform["jq"])
    return transformed, transform["target"]

async def _run_validations(
    data: dict, 
    validations: list[SchemaValidation]
) -> list[ValidationResult]:
    """Run JQ validations, return list of results."""
    results = []
    for rule in validations:
        jq_result = apply_jq_transform(data, rule["jq"])
        passed = bool(jq_result and jq_result[0])
        results.append(ValidationResult(
            rule_name=rule["name"],
            passed=passed,
            message=None if passed else rule.get("description"),
            mode=rule.get("mode", "warn"),
        ))
    return results
```

---

## Migration Strategy

### Phases (follows Epic Order: A → C → B → D)

**Phase 1: Schema Definition (Epic A)**

- [ ] Add Schema TypedDicts to `semantic_data_model_types.py`
- [ ] Add `schemas` field to `SemanticDataModel`
- [ ] Semantic annotation parsing
- [ ] Unit tests for schema parsing

**Phase 2: Transform & Validate Engines (Epic C)**

- [ ] Implement `execute_transformation()` using `apply_jq_transform()`
- [ ] Implement `validate_schema_data()` with warn/reject modes
- [ ] Unit tests for transform and validate

**Phase 3: Data Acquisition Pipeline (Epic B)**

- [ ] B-1: Reducto integration with SDM schemas
- [ ] B-2: API response handling
- [ ] B-3: Pipeline orchestration (transform → validate → store)
- [ ] `SchemaEnrichment` dataclass and storage
- [ ] Integration tests for extraction pipeline

**Phase 4: NL Queries (Epic D)**

- [ ] Extend `summarize_data_model()` for schemas
- [ ] Wire up JQ execution for schema queries
- [ ] Implicit schema generation
- [ ] End-to-end tests for schema queries

### Feature Flag

```python
ENABLE_SCHEMA_QUERIES = os.getenv("ENABLE_SCHEMA_QUERIES", "false").lower() == "true"
```

### Rollback

1. Set `ENABLE_SCHEMA_QUERIES=false`
2. Schema queries return "not supported" error
3. Schema definitions still stored (backward compatible)

### Database Migrations

No migrations required. Schemas stored in existing SDM table (JSONB) in AgentServer DB.

---

## References

- [Feature Specification](./sdm-hierarchical-data.md) - Requirements, design, and examples
- [JQ Manual](https://jqlang.github.io/jq/manual/)
