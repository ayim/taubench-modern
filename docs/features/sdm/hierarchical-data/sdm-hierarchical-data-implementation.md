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

| Story | Description | Implementation Sections |
| ----- | ----------- | ----------------------- |
| A-1 | Define Schemas in SDM YAML | §6 Data Structures (Schema TypedDicts) |
| A-2 | Semantic Annotations in JSON Schema | §6 Data Structures (annotation parsing) |
| B-1 | Execute DI Extraction with SDM Schema | §8 Core Algorithm (DI integration) |
| C-1 | Execute JQ Transformations | §8 Core Algorithm (execute_transformation) |
| C-2 | Execute JQ Validations | §8 Core Algorithm (validate_schema_data) |
| D-1 | Include Schemas in LLM Prompts | §7 API Design (prompt builder extension) |
| D-2 | Generate and Execute JQ Queries | §8 Core Algorithm (JQ execution path) |

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


Data Flow (Runtime):

┌──────────────┐     ┌────────────┐     ┌───────────────────┐
│ Thread File  │ ──► │ DI Extract │ ──► │ Schema Enrichment │
└──────────────┘     │ w/ Schema  │     │ (stored w/ file)  │
                     └────────────┘     └───────────────────┘
```

**Components:**

| Component | Purpose | Technology | Location |
| --------- | ------- | ---------- | -------- |
| Schema TypedDicts | Define schema structure | Python/TypedDict | `semantic_data_model_types.py` |
| Prompt Builder | Add schema context | Python | `semantic_data_model.py` |
| JQ Executor | Run JQ queries | jq/pyjq | `_jq_transform.py` (existing) |
| DI Integration | Execute extractions | Python | `di_service.py` (existing) |

---

## Sequence Diagrams

### Schema Query Execution

```
User    Orchestrator    PromptBuilder    LLM    Storage    JQExecutor
 │           │               │            │        │            │
 │──query───▶│               │            │        │            │
 │           │──get_context─▶│            │        │            │
 │           │◀──tables+schemas──         │        │            │
 │           │──────────────prompt───────▶│        │            │
 │           │◀─────────────jq_query──────│        │            │
 │           │──get_enrichment────────────────────▶│            │
 │           │◀──json_data────────────────────────│            │
 │           │──execute_jq─────────────────────────────────────▶│
 │           │◀──result────────────────────────────────────────│
 │◀──result──│               │            │        │            │
```

**Steps:**
1. User submits natural language query
2. Orchestrator requests context from PromptBuilder (includes schemas)
3. LLM generates JQ query for schema data
4. Storage retrieves schema enrichment (extracted data) for thread file
5. JQExecutor runs JQ expression
6. Result returned to user

### DI Extraction with Schema

```
User    Orchestrator    DIService    Storage    Validator
 │           │               │           │           │
 │──extract with schema────▶│           │           │
 │           │──extract──────────────────▶│          │
 │           │◀──extracted_data──────────│           │
 │           │──validate─────────────────────────────────────▶│
 │           │◀──validation_result───────────────────────────│
 │           │──store_enrichment─────────────────────▶│       │
 │           │◀──stored────────────────────────────────│      │
 │◀──result──│               │           │           │
```

---

## Data Flow

```
YAML → Parse → Validate → Store → Query → Resolve → Execute → Result
         │        │         │       │        │         │
         ▼        ▼         ▼       ▼        ▼         ▼
      Schema   Pydantic   JSONB   Prompt   Source    JQ/SQL
      Types    Validation  DB     Builder   Data     Engine
```

**Transformations:**

| Stage | Input | Output | Component |
| ----- | ----- | ------ | --------- |
| Parse | YAML string | Schema dict | YAML parser |
| Validate | Schema dict | Validated Schema | Pydantic |
| Store | SemanticDataModel | JSONB row | PostgreSQL |
| Query | NL question | JQ expression | LLM |
| Resolve | SchemaSource | JSON data | SourceResolver |
| Execute | JQ + JSON | Query result | JQExecutor |

---

## Design Decisions

### Decision 1: Schemas as First-Class SDM Elements

**Problem:** How to represent hierarchical JSON data in SDM?

**Options:**

| Option | Pros | Cons |
| ------ | ---- | ---- |
| A: Extend tables with JSON type | Consistent with existing | Loses hierarchical structure |
| B: Separate `schemas:` array | Clear separation | More complex SDM |
| C: Metadata-only (no querying) | Simple | Can't query JSON data |

**Chosen:** Option B - Separate `schemas:` array

**Rationale:** Schemas are fundamentally different from tables (hierarchical vs flat). A parallel structure makes both first-class citizens and allows schema-specific features (transformations, validations) without cluttering table definitions.

---

### Decision 2: JQ for Transformations

**Problem:** How to express schema-to-schema transformations?

**Options:**

| Option | Pros | Cons |
| ------ | ---- | ---- |
| A: Custom DSL | Tailored to use case | Learning curve, maintenance |
| B: JQ | Powerful, standard, existing infra | JQ syntax complexity |
| C: JSONPath + templates | Simpler syntax | Limited transformation power |

**Chosen:** Option B - JQ

**Rationale:** JQ is already used in the codebase (`_jq_transform.py`), is industry-standard for JSON transformations, and is powerful enough for complex mappings. The syntax complexity is offset by excellent documentation and LLM familiarity.

---

### Decision 3: Semantic Annotations in JSON Schema

**Problem:** How to add semantic metadata (synonyms, descriptions) to schema fields?

**Chosen:** Embed annotations directly in JSON Schema properties

**Rationale:** JSON Schema allows custom keywords. Embedding `synonyms`, `semantic_type`, and `sample_values` directly in property definitions keeps schema definitions self-contained. This mirrors how column annotations work in table definitions.

---

## Data Structures

### Existing Infrastructure to Reuse

| Component | Location | How to reuse |
| --------- | -------- | ------------ |
| SDM types | `core/.../semantic_data_model_types.py` | Add `schemas: list[Schema]` |
| SDM storage | `server/.../storage/base.py` | Stores JSONB (schemas included) |
| Prompt builder | `server/.../kernel/semantic_data_model.py` | Extend for schemas |
| JQ execution | `server/.../orchestrator/_jq_transform.py` | Use directly |
| DI service | `document-intelligence/.../services/` | Execute extractions with schema |
| Thread enrichments | `server/.../storage/base.py` | Store extracted data with files |

### New Types

Add to `core/src/agent_platform/core/data_frames/semantic_data_model_types.py`:

```python
class SchemaTransformation(TypedDict):
    target: str
    description: NotRequired[str]
    jq: str

class SchemaValidation(TypedDict):
    name: str
    description: NotRequired[str]
    jq: str

class Schema(TypedDict, total=False):
    name: Required[str]
    description: str
    jsonschema: Required[dict]
    transformations: list[SchemaTransformation]
    validations: list[SchemaValidation]
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

### DI Integration

Data is associated with schemas at runtime, not via static source definitions. The primary mechanism is DI extraction:

```python
async def execute_extraction_with_schema(
    thread_file: ThreadFile,
    schema: Schema,
    di_service: DIService,
) -> ExtractionResult:
    """Execute DI extraction using a specific SDM schema."""
    
    # Convert SDM schema to DI extraction schema
    extraction_schema = schema["jsonschema"]
    
    # Execute extraction via DI service
    result = await di_service.extract(
        file_id=thread_file.file_id,
        schema=extraction_schema,
    )
    
    return ExtractionResult(
        schema_name=schema["name"],
        data=result.extracted_data,
        validation_results=await validate_schema_data(
            result.extracted_data, 
            schema.get("validations", [])
        ),
    )
```

### Schema Data Storage

Extracted data is stored as enrichments on thread files:

```python
class SchemaEnrichment(TypedDict):
    schema_name: str
    extracted_data: dict
    extraction_timestamp: str
    validation_results: list[ValidationResult]

# Multiple extractions can be stored per file
# e.g., same receipt extracted with different schemas
```

### JQ Execution

```python
from agent_platform.orchestrator._jq_transform import apply_jq_transform

def execute_transformation(data: JsonValue, transformation: SchemaTransformation) -> JsonValue:
    """Execute JQ transformation."""
    return apply_jq_transform(data, transformation["jq"])

def validate_schema_data(data: JsonValue, validations: list[SchemaValidation]) -> list[str]:
    """Run JQ validations, return list of failed validation names."""
    failures = []
    for rule in validations:
        result = apply_jq_transform(data, rule["jq"])
        if not result or not result[0]:
            failures.append(rule["name"])
    return failures
```

---

## Migration Strategy

### Phases

**Phase 1: Types & Parsing**
- [ ] Add Schema TypedDicts to `semantic_data_model_types.py`
- [ ] Add `schemas` field to `SemanticDataModel`
- [ ] Unit tests for schema parsing

**Phase 2: DI Integration**
- [ ] Implement extraction with SDM schema
- [ ] Store schema enrichments on thread files
- [ ] Integration tests for DI extraction

**Phase 3: NL Integration**
- [ ] Extend `summarize_data_model()` for schemas
- [ ] Wire up JQ execution for schema queries
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

No migrations required. Schemas stored in existing SDM JSONB column.

---

## References

- [Feature Specification](./sdm-hierarchical-data.md) - Requirements, design, and examples
- [JQ Manual](https://jqlang.github.io/jq/manual/)
