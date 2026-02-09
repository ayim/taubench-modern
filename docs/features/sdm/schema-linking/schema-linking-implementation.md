# Implementation Guide: Schema Linking for NL2xQL

> **For AI Assistants:** Map each user story to implementation sections. Include ASCII diagrams for architecture/flows, design decisions with rationale, data structures with code, and deployment steps. Keep it concise.

**Date:** 2026-01-31
**Specification:** See [schema-linking-specification.md](./schema-linking-specification.md) for requirements

**Plan Version:** v2 (supersedes v1; clarifies SDM scoping, score normalization, strict-mode ordering, budgets, and artifact regeneration)

---

## Table of Contents

1. [Story-to-Implementation Mapping](#story-to-implementation-mapping)
2. [System Architecture](#system-architecture)
3. [Sequence Diagrams](#sequence-diagrams)
4. [Data Flow](#data-flow)
5. [Design Decisions](#design-decisions)
6. [Data Structures](#data-structures)
7. [API Design](#api-design)
8. [Core Algorithms](#core-algorithms)
9. [Migration Strategy](#migration-strategy)

---

## Story-to-Implementation Mapping

### Phase 1: Core MVP (BM25 Only, Zero LLM)

| Story                         | Implementation Sections                                                                    |
| ----------------------------- | ------------------------------------------------------------------------------------------ |
| A-1: Schema Graph             | §6.1 Database Schema, §6.2 Domain Models (`SchemaGraph`, `JoinEdge`)                       |
| A-2: Card Generation          | §6.2 Domain Models (`Card`, `TableCard`, `ColumnCard`, `MetricCard`), §8.1 Card Generation |
| D-1: Basic Retrieval          | §8.2 BM25 Search, §7 API Design                                                            |
| D-2: Basic Refinement         | §8.3 Closure Algorithms (Membership, FK-Key, Metric)                                       |
| D-3: Two-Stage Linking        | §8.4 Two-Stage Linking Algorithm                                                           |
| F-0: Confidence Scoring       | §8.5 Confidence Calculation                                                                |
| F-1: Simple Fallback          | §8.6 Fallback Strategy                                                                     |
| G-1: Schema Slice Output      | §6.2 Domain Models (`SchemaSlice`), §7 API Design                                          |
| B-1: Policy Filter (optional) | §8.7 Entitlement Filtering                                                                 |

### Phase 2: Accuracy & Scale (Embeddings + LLM)

| Story                        | Implementation Sections                                        |
| ---------------------------- | -------------------------------------------------------------- |
| A-3: Caching                 | §6.1 Database Schema (artifact caching), §8.8 Cache Management |
| D-4: Hybrid Retrieval        | §8.9 Hybrid Retrieval (BM25 + Embeddings + RRF)                |
| D-5: Bidirectional Retrieval | §8.10 Bidirectional Search                                     |
| D-6: Connector Minimization  | §8.11 Greedy Connector Algorithm                               |
| E-1: Query Understanding     | §8.12 LLM Query Understanding                                  |
| E-2: Recovery Loop           | §8.13 Recovery with Query Rewriting                            |
| G-2: Linking Trace           | §6.2 Domain Models (`LinkingTrace`)                            |

### Phase 2.1: Hierarchical Schemas

| Story                  | Implementation Sections                                              |
| ---------------------- | -------------------------------------------------------------------- |
| H-1: JSON Schema Cards | §6.2 Domain Models (`FieldCard`), §8.14 Hierarchical Card Generation |

### Phase 3: Enterprise

| Story                       | Implementation Sections          |
| --------------------------- | -------------------------------- |
| B-1: Policy Filter          | §8.7 Entitlement Filtering       |
| C-1: Database Selection     | §8.15 Catalog Router             |
| E-3: Ambiguity Resolution   | §8.16 Ambiguity Handling         |
| E-4a: Cross-SDM Suggestions | §8.17 Offline Cross-SDM Analysis |
| E-4b: Cross-SDM Hints       | §8.18 Runtime Cross-SDM Hints    |

### Phase 4: Cross-Domain

| Story                 | Implementation Sections            |
| --------------------- | ---------------------------------- |
| I-1: Unified SQL + JQ | §8.19 Unified Cross-Domain Linking |

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              SCHEMA LINKER                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌──────────────────┐    ┌─────────────────────────┐    │
│  │   Input     │───▶│  Query           │───▶│  Retrieval              │    │
│  │   Handler   │    │  Normalizer      │    │  Engine                 │    │
│  └─────────────┘    └──────────────────┘    └───────────┬─────────────┘    │
│                                                         │                   │
│                     ┌───────────────────────────────────┘                   │
│                     ▼                                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    REFINEMENT PIPELINE                               │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────────┐  │   │
│  │  │ Membership │─▶│  FK-Key    │─▶│  Metric    │─▶│  Connector   │  │   │
│  │  │ Closure    │  │  Closure   │  │  Closure   │  │  Minimization│  │   │
│  │  └────────────┘  └────────────┘  └────────────┘  └──────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                     │                                                       │
│                     ▼                                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    OUTPUT PIPELINE                                   │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────────┐  │   │
│  │  │  Policy    │─▶│  Budget    │─▶│ Confidence │─▶│  Schema      │  │   │
│  │  │  Filter    │  │  Enforcer  │  │ Scoring    │  │  Slice       │  │   │
│  │  └────────────┘  └────────────┘  └────────────┘  └──────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
                    ┌─────────────────────────────────────┐
                    │        Schema Slice (Physical)       │
                    │  • Tables, Columns, Joins, Metrics   │
                    │  • Confidence Score                  │
                    │  • Connectivity Status               │
                    └─────────────────────────────────────┘
```

### Component Responsibilities

| Component            | Purpose                                    | Technology                       |
| -------------------- | ------------------------------------------ | -------------------------------- |
| Input Handler        | Parse request, validate inputs             | FastAPI, Pydantic                |
| Query Normalizer     | Tokenize, lowercase, expand synonyms       | Python (deterministic)           |
| Retrieval Engine     | BM25 + embedding search over cards         | PostgreSQL (tsvector + pgvector) |
| Refinement Pipeline  | Closure algorithms, connector minimization | NetworkX graph algorithms        |
| Confidence Scoring   | Compute deterministic confidence           | Pure Python                      |
| Policy Filter        | Entitlement-based filtering                | Rule engine                      |
| Budget Enforcer      | Apply slice limits, truncate               | Pure Python                      |
| Schema Slice Builder | Construct output with physical refs        | Pydantic serialization           |

### Storage Architecture

All schema linking tables are stored in the **AgentServer PostgreSQL database**. The schema graph is loaded into memory at startup for fast path-finding operations.

**Versioning (v2):** All artifacts (cards, graph, embeddings) are keyed by `(sdm_id, sdm_version)`. Online requests must resolve the effective version (explicit request `sdm_version`, else the SDM's active version) and only read artifacts for that pair. This prevents cross-version contamination and makes rollbacks safe.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    POSTGRESQL (AgentServer Database)                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────────────┐    ┌───────────────────────────────────────┐    │
│  │  Schema Graph Tables   │    │         Card Index                    │    │
│  │  ────────────────────  │    │  ─────────────────────────────────── │    │
│  │  • sdm_linking_nodes   │    │  • sdm_linking_cards (tsvector/GIN)   │    │
│  │  • sdm_linking_edges   │    │  • sdm_linking_card_embeddings        │    │
│  │  (loaded into memory)  │    │    (pgvector for Phase 2+)            │    │
│  └───────────────────────┘    └───────────────────────────────────────┘    │
│                                                                             │
│  ┌───────────────────────┐    ┌───────────────────────────────────────┐    │
│  │   Artifact Cache       │    │         Entitlements                  │    │
│  │  ────────────────────  │    │  ─────────────────────────────────── │    │
│  │  • sdm_linking_        │    │  • sdm_user_permissions               │    │
│  │    artifacts           │    │                                       │    │
│  └───────────────────────┘    └───────────────────────────────────────┘    │
│                                                                             │
│  Note: Schema graph tables are the source of truth. The SchemaGraph        │
│  Python object is built from these tables at startup/cache-refresh and     │
│  held in memory for fast BFS path-finding (<100ms for 500 tables).         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Sequence Diagrams

### Phase 1: Basic Linking Flow (No LLM)

```
Client      API       Normalizer   Retriever   Refiner    Output
  │          │            │            │           │          │
  │──req────▶│            │            │           │          │
  │          │──normalize─▶│            │           │          │
  │          │            │──tokens────▶│           │          │
  │          │            │            │──tables───▶│          │
  │          │            │            │◀──columns──│          │
  │          │            │            │           │──closures─▶│
  │          │            │            │           │◀──slice────│
  │◀──resp───│            │            │           │          │
```

**Steps:**

1. Client sends NL question + user context
2. Normalizer tokenizes query (§5.4.1 deterministic normalization)
3. Retriever performs two-stage BM25 search (tables → columns)
4. Refiner applies membership, FK-key, metric closures
5. Output pipeline scores confidence, filters by policy, enforces budgets
6. Returns physical schema slice

### Phase 2: Linking with Recovery Loop

```
Client      API       QueryUnderstand   Retriever   Refiner   Recovery
  │          │              │               │           │          │
  │──req────▶│              │               │           │          │
  │          │──question───▶│               │           │          │
  │          │◀─parsed──────│               │           │          │
  │          │──search terms────────────────▶│           │          │
  │          │              │               │──refine──▶│          │
  │          │              │               │◀─result───│          │
  │          │              │               │           │          │
  │          │────────────(if confidence < 0.6)─────────▶│          │
  │          │              │               │           │◀─rewrite─│
  │          │              │               │◀──────────────retry──│
  │          │              │               │──refine──▶│          │
  │          │◀─merge results────────────────────────────│          │
```

---

## Data Flow

```
SDM Update                                 NL Question
    │                                           │
    ▼                                           ▼
┌───────────────┐                      ┌───────────────┐
│ Card Generator│                      │ Query Parser  │
│ (Offline)     │                      │ (Online)      │
└───────┬───────┘                      └───────┬───────┘
        │                                      │
        ▼                                      ▼
┌───────────────┐                      ┌───────────────┐
│ Card Index    │◀─────────search──────│ Search Terms  │
│ (BM25/Vector) │                      │               │
└───────┬───────┘                      └───────────────┘
        │
        ▼
┌───────────────┐
│ Candidate     │
│ Cards         │
└───────┬───────┘
        │
        ▼
┌───────────────────────────────────────────────────────┐
│                  REFINEMENT                            │
│  Membership → Metric → Connector → FK-Key → Entitlements → Budgets → Confidence │
└───────────────────────────┬───────────────────────────┘
                            │
                            ▼
                   ┌───────────────┐
                   │ Schema Slice  │
                   │ (Physical)    │
                   └───────────────┘
```

**Transformations:**

- SDM → Cards: Extract physical refs, build searchable text with SDM enrichment
- Question → Terms: Tokenize, normalize, expand synonyms (deterministic)
- Terms → Candidates: BM25 + embedding search, ranked by score
- Candidates → Slice: Apply closures, minimize connectors, enforce budgets

---

## Design Decisions

### Decision 1: Physical-First Card Indexing

**Problem:** Should cards be indexed by logical (SDM) names or physical (database) names?

**Options:**

| Option            | Pros                              | Cons                                          |
| ----------------- | --------------------------------- | --------------------------------------------- |
| A: Logical names  | Human-readable, matches SDM       | Requires translation layer for SQL generation |
| B: Physical names | Direct use in SQL, no translation | Less readable in debugging                    |

**Chosen:** Option B (Physical-First)

**Rationale:** The generator produces SQL/JQ that uses physical identifiers. By indexing cards by physical names and returning physical references, we eliminate an entire translation layer. SDM enrichment (synonyms, descriptions) is included in searchable text to maintain search quality. See spec §5.1.

---

### Decision 2: Greedy vs Steiner Tree for Connector Minimization

**Problem:** How to find minimal connector tables to join selected tables?

**Options:**

| Option                             | Pros                            | Cons                          |
| ---------------------------------- | ------------------------------- | ----------------------------- |
| A: Steiner tree approximation      | Optimal for large terminal sets | Complex implementation, O(n³) |
| B: Greedy shortest-path attachment | Simple, deterministic, fast     | May add 1-2 extra connectors  |

**Chosen:** Option B (Greedy)

**Rationale:** For NL2xQL, terminal sets are typically 6-12 tables. Greedy performs well on small sets, is simpler to implement and debug, and is deterministic. If future benchmarks show a consistent need for Steiner, implement it as a **separate, independently-tested strategy** (not a dormant feature flag in the MVP) to avoid complexity and drift. See spec §5.4.3.

---

### Decision 3: Entitlement Enforcement Mode

**Problem:** Should schema elements be filtered by user permissions at link time or at query time?

**Options:**

| Option                          | Pros                | Cons                                         |
| ------------------------------- | ------------------- | -------------------------------------------- |
| A: Strict (link-time filtering) | Zero schema leakage | Requires permission lookups on every request |
| B: Passthrough (DB enforcement) | Simpler, faster     | Schema structure visible in traces           |

**Chosen:** Configurable (default: passthrough)

**Rationale:** Multi-tenant SaaS deployments need strict mode. Internal deployments can use passthrough for performance. In **strict** mode, filtering must be applied _before returning, logging, or sending schema context to downstream components_, and must be applied in a way that is not sensitive to closure order:

- **Strict-mode ordering (v2):** apply entitlements immediately after retrieval _and again after closures_ (metric/connector/FK-key) because closures can introduce new tables/columns. After filtering, recompute connectivity + budgets on the filtered slice to avoid returning “impossible” joins.
- **Trace redaction:** full traces are admin-only; otherwise omit/redact physical identifiers in strict mode.

Made configurable via `entitlements.mode` setting. See spec §5.4.5.

---

### Decision 4: Confidence Score Formula

**Problem:** How to compute a single confidence scalar for gating decisions?

**Chosen:** Geometric mean of table dominance and column selection mass, with connectivity penalty.

**Rationale:**

- Table dominance (top score / sum of top-2) captures retrieval certainty
- Column selection mass captures how much of the candidate pool was selected
- Geometric mean balances both factors
- Penalty for disconnected graphs triggers recovery

**Critical implementation note (v2):** PostgreSQL `ts_rank` is not guaranteed to be in a stable `[0,1]` range. To keep confidence thresholds meaningful and stable across SDMs/queries:

- Normalize scores **per retrieval result set** (tables/columns/metrics independently) by dividing by the top raw score in that set (clamped to `[0,1]`).
- If there is exactly **one** table candidate, set `table_conf = 1.0` (spec explicitly calls this out).

See spec §5.4.4 for the formula contract.

---

### Decision 5: Query Normalization Strategy

**Problem:** How to prepare queries for BM25 search?

**Chosen:** Deterministic normalization (split, lowercase, strip, stopwords, optional synonym expansion)

**Rationale:** BM25 works best with tokenized queries. Deterministic normalization ensures reproducible results. Synonym expansion uses SDM-provided synonyms, not LLM. See spec §5.4.1.

---

## Data Structures

**TypedDict policy:** Do not use `TypedDict` or raw dictionaries for domain models or pipeline objects in the schema linker. Use Pydantic `BaseModel` (preferred) or `@dataclass` to enforce invariants and validation. This follows the Python guidelines.

### Database Schema

```sql
-- Schema Graph Tables (sdm_linking_ prefix for linking-specific tables)
CREATE TABLE sdm_linking_nodes (
    id TEXT PRIMARY KEY,                    -- "table:sales_dw.cust_mstr"
    node_type TEXT NOT NULL,                -- "table" | "column" | "metric"
    physical_name TEXT NOT NULL,            -- "sales_dw.cust_mstr"
    sdm_id TEXT NOT NULL,
    sdm_version TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_sdm_linking_nodes_sdm ON sdm_linking_nodes(sdm_id, sdm_version);
CREATE INDEX idx_sdm_linking_nodes_physical ON sdm_linking_nodes(physical_name);

CREATE TABLE sdm_linking_edges (
    id SERIAL PRIMARY KEY,
    source_table TEXT NOT NULL,             -- Physical table name
    target_table TEXT NOT NULL,             -- Physical table name
    source_column TEXT NOT NULL,            -- Physical column name
    target_column TEXT NOT NULL,            -- Physical column name
    cardinality TEXT,                       -- "one_to_many", "many_to_many"
    sdm_id TEXT NOT NULL,
    sdm_version TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_sdm_linking_edges_source ON sdm_linking_edges(source_table);
CREATE INDEX idx_sdm_linking_edges_target ON sdm_linking_edges(target_table);
CREATE INDEX idx_sdm_linking_edges_sdm ON sdm_linking_edges(sdm_id, sdm_version);

-- Card Index Tables (using PostgreSQL tsvector for full-text search)
CREATE TABLE sdm_linking_cards (
    id SERIAL PRIMARY KEY,
    card_id TEXT UNIQUE NOT NULL,           -- "table:sales_dw.cust_mstr"
    card_type TEXT NOT NULL,                -- "table" | "column" | "metric" | "field"
    searchable_text TEXT NOT NULL,          -- Physical + logical + synonyms + description
    searchable_tsvector TSVECTOR            -- Auto-generated for full-text search
        GENERATED ALWAYS AS (to_tsvector('english', searchable_text)) STORED,
    physical_ref TEXT NOT NULL,             -- Physical table/column reference
    physical_table TEXT,                    -- For columns: parent table
    data_type TEXT,                         -- For columns: varchar, integer, etc.
    dependencies JSONB,                     -- For metrics: physical_dependencies
    sdm_context JSONB,                      -- Logical name, description, synonyms
    sdm_id TEXT NOT NULL,
    sdm_version TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- GIN index for fast full-text search (BM25-like ranking via ts_rank)
CREATE INDEX idx_sdm_linking_cards_fts ON sdm_linking_cards USING GIN(searchable_tsvector);
CREATE INDEX idx_sdm_linking_cards_sdm ON sdm_linking_cards(sdm_id, sdm_version);
CREATE INDEX idx_sdm_linking_cards_type ON sdm_linking_cards(card_type);
CREATE INDEX idx_sdm_linking_cards_table ON sdm_linking_cards(physical_table);

-- Embedding Storage (Phase 2+ - requires pgvector extension)
-- Run: CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE sdm_linking_card_embeddings (
    card_id TEXT PRIMARY KEY REFERENCES sdm_linking_cards(card_id),
    embedding VECTOR(1536),                 -- OpenAI ada-002 dimension
    model_version TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- HNSW index for fast approximate nearest neighbor search
CREATE INDEX idx_sdm_linking_embeddings_vec ON sdm_linking_card_embeddings
    USING hnsw (embedding vector_cosine_ops);

-- Artifact Cache
CREATE TABLE sdm_linking_artifacts (
    id SERIAL PRIMARY KEY,
    sdm_id TEXT NOT NULL,
    sdm_version TEXT NOT NULL,
    artifact_type TEXT NOT NULL,            -- "schema_graph" | "cards" | "embeddings"
    status TEXT NOT NULL,                   -- "building" | "ready" | "stale"
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(sdm_id, sdm_version, artifact_type)
);

-- User Entitlements (sdm_ prefix - shared across SDM features)
CREATE TABLE sdm_user_permissions (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    sdm_id TEXT NOT NULL,
    permission_type TEXT NOT NULL,          -- "read" | "admin"
    table_patterns TEXT[],                  -- Allowed table patterns (glob)
    column_exclusions TEXT[],               -- Denied column patterns
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_sdm_user_permissions_user ON sdm_user_permissions(user_id, sdm_id);
```

### Domain Models

```python
from pydantic import BaseModel, Field
from typing import Literal
from enum import Enum


class CardType(str, Enum):
    """Card type enumeration."""

    TABLE = "table"
    COLUMN = "column"
    METRIC = "metric"
    FIELD = "field"  # Phase 2.1: hierarchical


class Card(BaseModel):
    """Base card structure for search indexing.

    Cards are indexed by physical names and return physical references.
    SDM metadata enriches searchable text but is not the source of identifiers.
    """

    id: str = Field(description="Card ID: {type}:{physical_ref}")
    type: CardType
    text: str = Field(description="Searchable text: physical + logical + synonyms + description")
    physical_ref: str = Field(description="Physical reference returned to caller")
    sdm_context: dict | None = Field(
        default=None,
        description="SDM metadata for debugging only"
    )
    score: float = Field(default=0.0, description="Retrieval score")


class TableCard(Card):
    """Card representing a physical table."""

    type: Literal[CardType.TABLE] = CardType.TABLE
    physical_table: str


class ColumnCard(Card):
    """Card representing a physical column."""

    type: Literal[CardType.COLUMN] = CardType.COLUMN
    physical_column: str
    physical_table: str
    data_type: str | None = None


class MetricCard(Card):
    """Card representing a metric with physical dependencies."""

    type: Literal[CardType.METRIC] = CardType.METRIC
    metric_name: str
    physical_dependencies: list[dict] = Field(
        default_factory=list,
        description="List of {table, column} physical references"
    )
    expression_hint: str | None = None


class FieldCard(Card):
    """Card representing a JSON schema field (Phase 2.1)."""

    type: Literal[CardType.FIELD] = CardType.FIELD
    physical_path: str  # e.g., "events.user.address.city"
    data_type: str | None = None


class JoinEdge(BaseModel):
    """Edge in the schema join graph."""

    source_table: str
    target_table: str
    source_column: str
    target_column: str
    cardinality: str | None = None


class SchemaGraph(BaseModel):
    """In-memory representation of joinable tables."""

    tables: set[str] = Field(default_factory=set)
    edges: list[JoinEdge] = Field(default_factory=list)

    def get_neighbors(self, table: str) -> list[str]:
        """Return tables directly joinable to the given table."""
        neighbors = []
        for edge in self.edges:
            if edge.source_table == table:
                neighbors.append(edge.target_table)
            elif edge.target_table == table:
                neighbors.append(edge.source_table)
        return neighbors

    def get_edge(self, table1: str, table2: str) -> JoinEdge | None:
        """Return the join edge between two tables if it exists."""
        for edge in self.edges:
            if (edge.source_table == table1 and edge.target_table == table2) or \
               (edge.source_table == table2 and edge.target_table == table1):
                return edge
        return None


class ColumnRef(BaseModel):
    """Physical column reference."""

    column: str
    type: str | None = None
    primary_key: bool = False


class TableSlice(BaseModel):
    """Table with selected columns in the schema slice."""

    table: str
    columns: list[ColumnRef] = Field(default_factory=list)


class JoinRef(BaseModel):
    """Join reference in the schema slice."""

    from_ref: str = Field(alias="from", description="schema.table.column")
    to_ref: str = Field(alias="to", description="schema.table.column")
    type: str = "inner"


class MetricRef(BaseModel):
    """Metric reference in the schema slice."""

    name: str
    expression: str


class SliceLimits(BaseModel):
    """Budget limits for schema slice."""

    max_tables: int = 10
    max_columns_per_table: int = 25
    max_total_columns: int = 80


class Connectivity(str, Enum):
    """Connectivity status of the schema slice."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    UNKNOWN = "unknown"


class MissingLink(BaseModel):
    """Information about tables that could not be connected."""

    table1: str
    table2: str
    reason: str


class SchemaSlice(BaseModel):
    """Output schema slice with physical references.

    This is the primary output of the schema linker. All references
    are physical database identifiers that can be used directly in SQL.
    """

    limits: SliceLimits = Field(default_factory=SliceLimits)
    truncated: bool = False
    tables: list[TableSlice] = Field(default_factory=list)
    joins: list[JoinRef] = Field(default_factory=list)
    metrics: list[MetricRef] = Field(default_factory=list)
    connectivity: Connectivity = Connectivity.UNKNOWN
    components: list[list[str]] = Field(
        default_factory=list,
        description="Connected components if disconnected"
    )
    missing_links: list[MissingLink] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    cross_sdm_join_hints: list[dict] = Field(default_factory=list)


class ConfidenceBreakdown(BaseModel):
    """Detailed confidence calculation for debugging."""

    table_conf: float
    col_conf: float
    conn_factor: float
    final: float


class QueryUnderstandingResult(BaseModel):
    """Output of LLM query understanding (Phase 2+).

    MUST NOT contain schema identifiers. Only search signals.
    """

    search_tokens: list[str]
    entities: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    filters: list[dict] = Field(default_factory=list)


class RetrievalMatch(BaseModel):
    """Single retrieval match for tracing."""

    card_id: str
    score: float


class LinkingTrace(BaseModel):
    """Full linking trace for debugging (Phase 2+)."""

    input_question: str
    query_understanding: QueryUnderstandingResult | None = None
    retrieval_method: str
    retrieval_matches: list[RetrievalMatch] = Field(default_factory=list)
    refinement_algorithm: str
    connectors_added: list[str] = Field(default_factory=list)
    confidence_breakdown: ConfidenceBreakdown | None = None
    output_tables: list[str] = Field(default_factory=list)
    output_confidence: float = 0.0


class ErrorCode(str, Enum):
    """Standard error codes for schema linking."""

    SDM_NOT_FOUND = "sdm_not_found"
    ENTITLEMENT_DENIED = "entitlement_denied"
    NO_MATCHES = "no_matches"
    TIMEOUT = "timeout"
    INTERNAL_ERROR = "internal_error"


class LinkingError(BaseModel):
    """Structured error response."""

    code: ErrorCode
    message: str
    details: dict | None = None
    trace_id: str


class LinkingRequest(BaseModel):
    """Input request for schema linking."""

    question: str
    sdm_id: str
    sdm_version: str | None = None
    user_id: str
    conversation_history: list[dict] = Field(default_factory=list)
    limits: SliceLimits | None = None


class LinkingResponse(BaseModel):
    """Output response from schema linking."""

    schema_slice: SchemaSlice | None = None
    confidence: float = 0.0
    connectivity: Connectivity = Connectivity.UNKNOWN
    trace: LinkingTrace | None = None
    error: LinkingError | None = None
```

---

## API Design

### REST Endpoints

**POST /api/v1/schema-link**

Request:

> `sdm_version` may be omitted/null to use the currently active version for `sdm_id` (resolved server-side).

```json
{
  "question": "Show sales by customer for last month",
  "sdm_id": "sales-analytics",
  "sdm_version": "v2.3.1",
  "user_id": "user-123",
  "conversation_history": [],
  "limits": {
    "max_tables": 10,
    "max_columns_per_table": 25,
    "max_total_columns": 80
  }
}
```

Response (success):

```json
{
  "schema_slice": {
    "limits": {
      "max_tables": 10,
      "max_columns_per_table": 25,
      "max_total_columns": 80
    },
    "truncated": false,
    "tables": [
      {
        "table": "sales_dw.cust_mstr",
        "columns": [
          { "column": "cust_id", "type": "integer", "primary_key": true },
          { "column": "cust_nm", "type": "varchar", "primary_key": false }
        ]
      },
      {
        "table": "sales_dw.orders",
        "columns": [
          { "column": "order_id", "type": "integer", "primary_key": true },
          { "column": "cust_id", "type": "integer", "primary_key": false },
          { "column": "amount", "type": "decimal", "primary_key": false },
          { "column": "order_date", "type": "date", "primary_key": false }
        ]
      }
    ],
    "joins": [
      {
        "from": "sales_dw.cust_mstr.cust_id",
        "to": "sales_dw.orders.cust_id",
        "type": "inner"
      }
    ],
    "metrics": [
      {
        "name": "total_revenue",
        "expression": "SUM(sales_dw.orders.amount)"
      }
    ],
    "connectivity": "connected",
    "components": [],
    "missing_links": [],
    "confidence": 0.85,
    "cross_sdm_join_hints": []
  },
  "confidence": 0.85,
  "connectivity": "connected",
  "trace": null,
  "error": null
}
```

Response (error):

```json
{
  "schema_slice": null,
  "confidence": 0.0,
  "connectivity": "unknown",
  "trace": null,
  "error": {
    "code": "sdm_not_found",
    "message": "SDM 'sales-analytics' version 'v2.3.1' not found",
    "details": {
      "sdm_id": "sales-analytics",
      "sdm_version": "v2.3.1"
    },
    "trace_id": "abc123-def456"
  }
}
```

### Internal Service Interface

```python
from typing import Protocol


class SchemaLinker(Protocol):
    """Protocol for schema linking service."""

    async def link(
        self,
        question: str,
        sdm_id: str,
        user_id: str,
        sdm_version: str | None = None,
        conversation_history: list[dict] | None = None,
        limits: SliceLimits | None = None,
    ) -> LinkingResponse:
        """Link a natural language question to schema elements.

        Args:
            question: Natural language question
            sdm_id: Semantic Data Model identifier
            user_id: User identifier for entitlement checks
            sdm_version: Optional specific SDM version (if None, resolve and use the active version for sdm_id)
            conversation_history: Optional conversation context (Phase 2+)
            limits: Optional budget limits override

        Returns:
            LinkingResponse with schema slice or error

        Raises:
            Never raises - errors returned in response.error
        """
        ...

    async def regenerate_artifacts(
        self,
        sdm_id: str,
        sdm_version: str,
    ) -> None:
        """Regenerate cards and graph for an SDM version.

        Called on SDM update. Runs via a tracked job/task runner (no fire-and-forget). The active version should only be flipped after all artifacts for the new `(sdm_id, sdm_version)` are built and validated (atomic activation). Online requests continue using the previous active version until activation.
        """
        ...
```

---

## Core Algorithms

### 8.1 Card Generation

```python
async def generate_cards_from_sdm(sdm: "SemanticDataModel") -> list[Card]:
    """Generate search-optimized cards from SDM.

    Cards are indexed by physical names but include SDM enrichment
    in searchable text for better matching.

    Args:
        sdm: The semantic data model to process

    Returns:
        List of cards (table, column, metric) ready for indexing
    """
    cards: list[Card] = []

    # Generate table cards
    for table in sdm.tables:
        searchable_text = _build_searchable_text(
            physical_name=table.physical_table,
            logical_name=table.logical_name,
            description=table.description,
            synonyms=table.synonyms,
        )

        card = TableCard(
            id=f"table:{table.physical_table}",
            text=searchable_text,
            physical_ref=table.physical_table,
            physical_table=table.physical_table,
            sdm_context={
                "logical_name": table.logical_name,
                "description": table.description,
                "synonyms": table.synonyms,
            },
        )
        cards.append(card)

        # Generate column cards for this table
        for column in table.columns:
            col_searchable = _build_searchable_text(
                physical_name=column.physical_column,
                logical_name=column.logical_name,
                description=column.description,
                synonyms=column.synonyms,
                parent_physical=table.physical_table,
            )

            col_card = ColumnCard(
                id=f"column:{table.physical_table}.{column.physical_column}",
                text=col_searchable,
                physical_ref=f"{table.physical_table}.{column.physical_column}",
                physical_column=column.physical_column,
                physical_table=table.physical_table,
                data_type=column.data_type,
                sdm_context={
                    "logical_name": column.logical_name,
                    "description": column.description,
                    "synonyms": column.synonyms,
                },
            )
            cards.append(col_card)

    # Generate metric cards
    for metric in sdm.metrics:
        deps = _parse_metric_dependencies(metric.expression)
        metric_searchable = _build_searchable_text(
            physical_name=metric.name,
            logical_name=metric.logical_name,
            description=metric.description,
            synonyms=metric.synonyms,
            dependencies=deps,
        )

        metric_card = MetricCard(
            id=f"metric:{metric.name}",
            text=metric_searchable,
            physical_ref=metric.name,
            metric_name=metric.name,
            physical_dependencies=deps,
            expression_hint=metric.expression,
            sdm_context={
                "logical_name": metric.logical_name,
                "description": metric.description,
                "synonyms": metric.synonyms,
            },
        )
        cards.append(metric_card)

    return cards


def _build_searchable_text(
    physical_name: str,
    logical_name: str | None = None,
    description: str | None = None,
    synonyms: list[str] | None = None,
    parent_physical: str | None = None,
    dependencies: list[dict] | None = None,
) -> str:
    """Build searchable text from physical and SDM metadata."""
    parts = [
        physical_name.replace(".", " ").replace("_", " "),
        logical_name or "",
        description or "",
        " ".join(synonyms or []),
    ]

    if parent_physical:
        parts.append(parent_physical.replace(".", " "))

    if dependencies:
        for dep in dependencies:
            parts.append(dep.get("table", "").replace(".", " "))
            parts.append(dep.get("column", ""))

    return " ".join(filter(None, parts))


def _parse_metric_dependencies(expression: str) -> list[dict]:
    """Extract physical table.column references from metric expression.

    Simple regex-based extraction. Handles: SUM(table.column), table.column.
    """
    import re

    pattern = r"([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)+)"
    matches = re.findall(pattern, expression)

    deps = []
    for match in matches:
        parts = match.rsplit(".", 1)
        if len(parts) == 2:
            deps.append({"table": parts[0], "column": parts[1]})

    return deps
```

### 8.2 Query Normalization

```python
import re

# Default stopwords for BM25
DEFAULT_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
    "be", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "must", "shall", "can", "need",
    "show", "me", "give", "get", "find", "list", "display", "what",
}


def normalize_query(
    query: str,
    stopwords: set[str] | None = None,
    synonym_dict: dict[str, list[str]] | None = None,
) -> list[str]:
    """Normalize query into stable search tokens.

    Deterministic normalization per spec §5.4.1:
    - Split on ., _, -, and camelCase
    - Lowercase, strip punctuation
    - Drop configurable stopwords
    - Optional: deterministic synonym expansion

    Args:
        query: Raw natural language query
        stopwords: Words to remove (default: DEFAULT_STOPWORDS)
        synonym_dict: SDM-provided synonym mappings for expansion

    Returns:
        List of normalized search tokens
    """
    if stopwords is None:
        stopwords = DEFAULT_STOPWORDS

    # Split camelCase
    query = re.sub(r"([a-z])([A-Z])", r"\1 \2", query)

    # Split on delimiters
    query = re.sub(r"[._\-/]", " ", query)

    # Remove punctuation except alphanumeric and spaces
    query = re.sub(r"[^a-zA-Z0-9\s]", "", query)

    # Lowercase and split
    tokens = query.lower().split()

    # Remove stopwords
    tokens = [t for t in tokens if t not in stopwords and len(t) > 1]

    # Optional synonym expansion (deterministic)
    if synonym_dict:
        expanded = []
        for token in tokens:
            expanded.append(token)
            if token in synonym_dict:
                expanded.extend(synonym_dict[token])
        tokens = expanded

    return tokens
```

### 8.3 BM25 Search

```python
async def bm25_search(
    search_terms: list[str],
    *,
    sdm_id: str,
    sdm_version: str,
    card_type: str | None = None,
    table_filter: list[str] | None = None,
    k: int = 10,
    db: "AsyncSession" = None,
) -> list[Card]:
    """Perform full-text search over card index using PostgreSQL tsvector.

    v2 criticals:
    - ALWAYS scope by (sdm_id, sdm_version) to avoid cross-version contamination.
    - Normalize returned scores to [0,1] *within this result set* so downstream
      confidence thresholds are stable.

    Uses ts_rank for BM25-like relevance ranking.

    Args:
        search_terms: Normalized search tokens
        sdm_id: SDM identifier
        sdm_version: SDM version (resolved before calling)
        card_type: Optional filter by card type
        table_filter: Optional filter by physical_table (for two-stage)
        k: Number of results to return
        db: Database session

    Returns:
        List of cards sorted by normalized relevance score descending
    """
    from sqlalchemy import text

    # Convert search terms to tsquery format (AND all terms)
    query_text = " & ".join(search_terms)

    # Build PostgreSQL full-text search query (parameterized)
    sql = """
        SELECT
            card_id,
            card_type,
            searchable_text,
            physical_ref,
            physical_table,
            data_type,
            dependencies,
            sdm_context,
            ts_rank(searchable_tsvector, to_tsquery('english', :query)) as raw_score
        FROM sdm_linking_cards
        WHERE
            sdm_id = :sdm_id
            AND sdm_version = :sdm_version
            AND searchable_tsvector @@ to_tsquery('english', :query)
    """

    params: dict = {
        "query": query_text,
        "sdm_id": sdm_id,
        "sdm_version": sdm_version,
        "k": k,
    }

    if card_type:
        sql += " AND card_type = :card_type"
        params["card_type"] = card_type

    if table_filter:
        sql += " AND physical_table = ANY(:tables)"
        params["tables"] = table_filter

    sql += " ORDER BY raw_score DESC LIMIT :k"

    result = await db.execute(text(sql), params)
    rows = result.fetchall()

    max_raw = max((float(r.raw_score) for r in rows), default=0.0)

    cards: list[Card] = []
    for row in rows:
        card_cls = _get_card_class(row.card_type)
        norm_score = (float(row.raw_score) / max_raw) if max_raw > 0 else 0.0
        norm_score = max(0.0, min(norm_score, 1.0))

        card = card_cls(
            id=row.card_id,
            text=row.searchable_text,
            physical_ref=row.physical_ref,
            score=norm_score,
            sdm_context=row.sdm_context,
            **({"physical_table": row.physical_table} if row.physical_table else {}),
            **({"data_type": row.data_type} if row.data_type else {}),
            **({"physical_dependencies": row.dependencies} if row.dependencies else {}),
        )
        cards.append(card)

    return cards


def _get_card_class(card_type: str):
    """Return the appropriate card class for a type."""
    return {
        "table": TableCard,
        "column": ColumnCard,
        "metric": MetricCard,
        "field": FieldCard,
    }.get(card_type, Card)
```

### 8.4 Two-Stage Linking

```python
async def two_stage_link(
    question: str,
    sdm_id: str,
    sdm_version: str,
    db: "AsyncSession",
    k_tables: int = 10,
    k_columns: int = 30,
) -> tuple[list[TableCard], list[ColumnCard], list[MetricCard]]:
    """Two-stage linking: tables first, then columns within those tables.

    v2 criticals:
    - BM25 retrieval is ALWAYS scoped to (sdm_id, sdm_version).
    - Returned scores are normalized to [0,1] within each result set (tables/columns/metrics)
      so confidence thresholds are stable.

    Args:
        question: Natural language question
        sdm_id: SDM identifier
        sdm_version: SDM version
        db: Database session
        k_tables: Number of tables to retrieve
        k_columns: Number of columns to retrieve

    Returns:
        Tuple of (table_cards, column_cards, metric_cards)
    """
    search_terms = normalize_query(question)

    # Stage 1: Find relevant tables
    table_cards = await bm25_search(
        search_terms=search_terms,
        sdm_id=sdm_id,
        sdm_version=sdm_version,
        card_type="table",
        k=k_tables,
        db=db,
    )

    candidate_tables = [card.physical_table for card in table_cards if card.physical_table]

    # Stage 2: Find columns within those tables (plus a small global top-N to catch column-only queries)
    scoped_columns = await bm25_search(
        search_terms=search_terms,
        sdm_id=sdm_id,
        sdm_version=sdm_version,
        card_type="column",
        table_filter=candidate_tables,
        k=k_columns,
        db=db,
    )
    global_columns = await bm25_search(
        search_terms=search_terms,
        sdm_id=sdm_id,
        sdm_version=sdm_version,
        card_type="column",
        table_filter=None,
        k=max(10, k_columns // 3),
        db=db,
    )

    # Deduplicate by card_id while preserving best score
    by_id: dict[str, ColumnCard] = {}
    for c in scoped_columns + global_columns:
        prev = by_id.get(c.id)
        if prev is None or c.score > prev.score:
            by_id[c.id] = c
    column_cards = sorted(by_id.values(), key=lambda c: (-c.score, c.physical_table or "", c.physical_ref))

    # Also find metrics (cheap)
    metric_cards = await bm25_search(
        search_terms=search_terms,
        sdm_id=sdm_id,
        sdm_version=sdm_version,
        card_type="metric",
        k=5,
        db=db,
    )

    return table_cards, column_cards, metric_cards
```

### 8.5 Closure Algorithms

```python
def apply_membership_closure(
    selected_columns: list[ColumnCard],
    selected_tables: set[str],
) -> set[str]:
    """Add tables that own selected columns.

    If column orders.amount is selected, table orders must be in the slice.
    """
    tables = set(selected_tables)
    for col in selected_columns:
        if col.physical_table:
            tables.add(col.physical_table)
    return tables


def apply_metric_closure(
    selected_metrics: list[MetricCard],
    selected_tables: set[str],
    columns_by_table: dict[str, set[str]],
) -> tuple[set[str], dict[str, set[str]], dict[str, set[str]]]:
    """Add tables/columns referenced by selected metrics.

    Returns:
        tables: updated tables
        columns_by_table: updated columns (includes metric deps)
        metric_required_cols: metric deps only (used as "required" for budgets)
    """
    tables = set(selected_tables)
    cols = {t: set(v) for t, v in columns_by_table.items()}
    metric_required_cols: dict[str, set[str]] = {}

    for metric in selected_metrics:
        for dep in metric.physical_dependencies:
            table = dep.get("table")
            column = dep.get("column")

            if not table:
                continue

            tables.add(table)
            cols.setdefault(table, set())

            if column:
                cols[table].add(column)
                metric_required_cols.setdefault(table, set()).add(column)

    return tables, cols, metric_required_cols


def apply_fk_key_closure(
    join_refs: list[JoinRef],
    columns_by_table: dict[str, set[str]],
) -> dict[str, set[str]]:
    """Ensure join key columns exist in the slice.

    Post-step required by spec §5.4.3: after connector minimization (which decides join paths),
    add join columns for the joins on those paths.

    Returns:
        join_required_cols: join keys only (used as "required" for budgets)
    """
    join_required_cols: dict[str, set[str]] = {}

    for j in join_refs:
        from_t, from_c = _split_ref(j.from_ref)
        to_t, to_c = _split_ref(j.to_ref)

        join_required_cols.setdefault(from_t, set()).add(from_c)
        join_required_cols.setdefault(to_t, set()).add(to_c)

        columns_by_table.setdefault(from_t, set()).add(from_c)
        columns_by_table.setdefault(to_t, set()).add(to_c)

    return join_required_cols
```

### 8.6 Confidence Calculation

```python
from math import sqrt


def compute_confidence(
    table_candidates: list[Card],
    column_candidates: list[Card],
    selected_column_ids: set[str],
    is_connected: bool,
) -> tuple[float, ConfidenceBreakdown]:
    """Compute deterministic confidence score for gating.

    v2 critical: assumes candidate scores are already normalized to [0,1]
    (see bm25_search). That keeps confidence thresholds stable.

    Formula per spec §5.4.4:
    - Table confidence: dominance of top match (s1 / (s1 + s2)), OR 1.0 if only 1 candidate
    - Column confidence: mass of selected vs all candidates
    - Combined: geometric mean * connectivity penalty

    Args:
        table_candidates: Ranked table cards with normalized scores
        column_candidates: Ranked column cards with normalized scores
        selected_column_ids: IDs of columns actually selected into slice
        is_connected: Whether the slice is connected

    Returns:
        Tuple of (confidence, breakdown)
    """
    # Table confidence: dominance of top match
    if len(table_candidates) >= 2:
        s1 = table_candidates[0].score
        s2 = table_candidates[1].score
        table_conf = s1 / (s1 + s2) if (s1 + s2) > 0 else 0.0
    elif len(table_candidates) == 1:
        table_conf = 1.0
    else:
        table_conf = 0.0

    table_conf = max(0.0, min(table_conf, 1.0))

    # Column confidence: mass of selected vs all candidates
    selected_mass = sum(
        c.score for c in column_candidates
        if c.id in selected_column_ids
    )
    candidate_mass = sum(c.score for c in column_candidates)
    col_conf = (selected_mass / candidate_mass) if candidate_mass > 0 else 0.0
    col_conf = max(0.0, min(col_conf, 1.0))

    # Connectivity penalty
    conn_factor = 1.0 if is_connected else 0.7

    # Combined confidence (geometric mean)
    final = sqrt(table_conf * col_conf) * conn_factor

    breakdown = ConfidenceBreakdown(
        table_conf=round(table_conf, 3),
        col_conf=round(col_conf, 3),
        conn_factor=conn_factor,
        final=round(final, 3),
    )

    return final, breakdown
```

### 8.7 Greedy Connector Minimization

```python
from collections import deque


def find_connectors_and_joins(
    schema_graph: SchemaGraph,
    terminals: set[str],
    table_scores: dict[str, float] | None = None,
) -> tuple[set[str], list[JoinRef], list[list[str]], list[MissingLink]]:
    """Greedy connector minimization + join extraction.

    Algorithm per spec §5.4.3:
    1. Seed with highest-scoring terminal table
    2. Repeatedly attach nearest remaining terminal via shortest path to the current component
    3. Add all tables on each selected path (connectors) to the slice
    4. Deterministic tie-breaks: path length → terminal score → lexical

    v2 criticals:
    - If disconnected, we do NOT fabricate connectors. We return components + missing_links.
    - We include all terminals in the returned table set (even if isolated) so the caller
      can surface disconnection explicitly.

    Returns:
        selected_tables: terminals ∪ connector tables found
        join_refs: joins along the selected attachment paths (deduped)
        components: connected components within selected_tables
        missing_links: terminal pairs that could not be connected (with reason)
    """
    if len(terminals) <= 1:
        tables = set(terminals)
        return tables, [], [sorted(tables)] if tables else [], []

    table_scores = table_scores or {}

    # Deterministic seed selection: highest score, then lexical
    seed = max(terminals, key=lambda t: (table_scores.get(t, 0.0), t))

    connected_component = {seed}
    remaining = terminals - {seed}

    selected_paths: list[list[str]] = []

    while remaining:
        best_t: str | None = None
        best_path: list[str] | None = None
        best_len = 10**9
        best_score = -1.0

        for t in sorted(remaining):
            path = _bfs_shortest_path_to_component(schema_graph, t, connected_component)
            if path is None:
                continue

            path_len = len(path)
            t_score = table_scores.get(t, 0.0)

            # Tie-break: shorter path → higher score → lexical
            if (
                path_len < best_len
                or (path_len == best_len and t_score > best_score)
                or (path_len == best_len and t_score == best_score and t < (best_t or ""))
            ):
                best_t = t
                best_path = path
                best_len = path_len
                best_score = t_score

        if best_path is None:
            # Remaining terminals cannot be attached (disconnected)
            break

        selected_paths.append(best_path)
        connected_component.update(best_path)
        remaining.remove(best_t)

    # Include all terminals (even unattached) + any connectors discovered
    selected_tables = set(terminals) | set(connected_component)

    # Extract join refs from the chosen paths (FK-key closure will add the columns)
    join_refs = _paths_to_join_refs(schema_graph, selected_paths)

    # Compute components within selected_tables
    components = _compute_components(schema_graph, selected_tables)

    # missing_links must be terminal pairs (spec §5.4.2).
    missing_links: list[MissingLink] = []
    if len(components) > 1:
        # Pick a deterministic representative terminal from each component
        reps: list[str] = []
        for comp in components:
            comp_terms = sorted([t for t in comp if t in terminals])
            reps.append(comp_terms[0] if comp_terms else comp[0])

        anchor = reps[0]
        for r in reps[1:]:
            missing_links.append(MissingLink(
                table1=anchor,
                table2=r,
                reason="No join path exists in schema graph",
            ))

    return selected_tables, join_refs, components, missing_links


def _paths_to_join_refs(schema_graph: SchemaGraph, paths: list[list[str]]) -> list[JoinRef]:
    """Convert selected table paths into join refs (deduped, deterministic)."""
    join_map: dict[tuple[str, str], JoinRef] = {}

    for path in paths:
        for a, b in zip(path, path[1:]):
            edge = schema_graph.get_edge(a, b)
            if edge is None:
                continue  # Should not happen if graph is consistent

            # Use canonical ordering for dedupe key
            key = tuple(sorted([a, b]))

            # Prefer a stable direction: edge as stored
            from_ref = f"{edge.source_table}.{edge.source_column}"
            to_ref = f"{edge.target_table}.{edge.target_column}"

            join_type = getattr(edge, "join_type", "inner")
            join_map[key] = JoinRef(from_ref=from_ref, to_ref=to_ref, type=join_type)

    # Stable ordering
    return [join_map[k] for k in sorted(join_map.keys())]


def _bfs_shortest_path_to_component(
    schema_graph: SchemaGraph,
    start: str,
    component: set[str],
) -> list[str] | None:
    """BFS to find a shortest path from start to any node in component.

    Determinism:
    - neighbors are iterated in sorted order
    - we return the first found shortest path (stable because of ordering)
    """
    if start in component:
        return [start]

    queue = deque([(start, [start])])
    visited = {start}

    while queue:
        current, path = queue.popleft()

        for neighbor in sorted(schema_graph.get_neighbors(current)):
            if neighbor in component:
                return path + [neighbor]

            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor]))

    return None


def _compute_components(schema_graph: SchemaGraph, tables: set[str]) -> list[list[str]]:
    """Compute connected components within the selected tables (deterministic)."""
    remaining = set(tables)
    components: list[list[str]] = []

    while remaining:
        start = min(remaining)  # Deterministic component seed
        component: set[str] = set()
        queue = deque([start])

        while queue:
            current = queue.popleft()
            if current in component:
                continue
            component.add(current)

            for neighbor in schema_graph.get_neighbors(current):
                if neighbor in remaining and neighbor not in component:
                    queue.append(neighbor)

        components.append(sorted(component))
        remaining -= component

    # Deterministic component ordering
    components.sort(key=lambda comp: comp[0] if comp else "")
    return components
```

### 8.8 Budget Enforcement

Budgets are **hard caps** (spec §5.4.6). v2 clarifies what is _required_ vs _droppable_ so budget trimming never produces an invalid slice.

**Required columns (never drop):**

1. Join key columns used by `joins` (from/to column refs)
2. Metric dependency columns (from metric closure)

**Droppable columns:**

- Additional “nice-to-have” columns selected via retrieval.

If the table budget is exceeded, we deterministically drop the lowest-priority terminals (by score, tie-break lexical) and **re-run connector minimization** on the reduced terminal set so joins remain consistent.

```python
def enforce_budgets(
    *,
    terminals: set[str],
    selected_tables: set[str],
    join_refs: list[JoinRef],
    metric_required_cols: dict[str, set[str]],
    column_candidates: list[ColumnCard],
    table_scores: dict[str, float],
    limits: SliceLimits,
    schema_graph: SchemaGraph,
) -> tuple[list[TableSlice], list[JoinRef], bool, list[MissingLink]]:
    """Apply hard budgets deterministically.

    Returns:
        tables: list[TableSlice] (with columns trimmed)
        joins: list[JoinRef] (may shrink if table budget forces recompute)
        truncated: bool
        missing_links_extra: optional missing_links entries with reason="budget_exceeded"
    """
    truncated = False
    missing_links_extra: list[MissingLink] = []

    # 1) Table budget (deterministic). Prefer keeping terminals.
    # Keep terminals sorted by score desc, then lexical.
    terminals_sorted = sorted(terminals, key=lambda t: (-table_scores.get(t, 0.0), t))

    if len(selected_tables) > limits.max_tables:
        truncated = True

        # Reduce terminal set first (drop lowest-priority terminals).
        keep_terms = set(terminals_sorted[: max(1, min(len(terminals_sorted), limits.max_tables))])

        # Re-run connector minimization on the reduced set.
        # Note: this may still exceed max_tables if the join graph is “wide”.
        reduced_tables, reduced_joins, components, missing = find_connectors_and_joins(
            schema_graph=schema_graph,
            terminals=keep_terms,
            table_scores=table_scores,
        )

        selected_tables = reduced_tables
        join_refs = reduced_joins

        # If still exceeds max_tables, keep terminals first, then connectors.
        if len(selected_tables) > limits.max_tables:
            keep = set(keep_terms)
            remaining_slots = limits.max_tables - len(keep)

            # If terminals alone exceed max_tables, drop lowest-priority terminals.
            if remaining_slots < 0:
                keep = set(terminals_sorted[: limits.max_tables])
                remaining_slots = 0

            connectors = sorted(selected_tables - keep)
            keep.update(connectors[:remaining_slots])

            dropped = sorted(selected_tables - keep)
            selected_tables = keep
            join_refs = [j for j in join_refs if _join_tables(j).issubset(keep)]

            # Mark dropped tables as budget-exceeded (including dropped terminals).
            anchor = min(keep) if keep else ""
            for t in dropped:
                missing_links_extra.append(MissingLink(
                    table1=anchor,
                    table2=t,
                    reason="budget_exceeded",
                ))

    # 2) Column budgets: keep required cols first, then fill by retrieval score.
    # Build per-table ranked candidate list.
    cols_by_table: dict[str, list[ColumnCard]] = {}
    for c in column_candidates:
        if c.physical_table in selected_tables:
            cols_by_table.setdefault(c.physical_table, []).append(c)
    for t in cols_by_table:
        cols_by_table[t].sort(key=lambda c: (-c.score, c.physical_ref))

    # Required join columns from join refs
    required_join: dict[str, set[str]] = {}
    for j in join_refs:
        # JoinRef stores "schema.table.column"
        from_t, from_c = _split_ref(j.from_ref)
        to_t, to_c = _split_ref(j.to_ref)
        required_join.setdefault(from_t, set()).add(from_c)
        required_join.setdefault(to_t, set()).add(to_c)

    # Assemble columns deterministically
    tables_out: list[TableSlice] = []
    total_cols = 0

    for t in sorted(selected_tables):
        required = set()
        required |= required_join.get(t, set())
        required |= metric_required_cols.get(t, set())

        # Start with required columns
        picked: list[str] = sorted(required)

        # Fill with top-scoring candidates (droppable) until per-table limit
        for c in cols_by_table.get(t, []):
            col_name = c.physical_ref.split(".")[-1]
            if col_name in required:
                continue
            if len(picked) >= limits.max_columns_per_table:
                break
            picked.append(col_name)

        # Enforce total column budget globally (drop droppable only)
        remaining_budget = limits.max_total_columns - total_cols
        if remaining_budget <= 0:
            truncated = True
            break

        if len(picked) > remaining_budget:
            truncated = True
            # Keep required cols within the remaining budget first
            req_sorted = sorted(required)
            droppable = [c for c in picked if c not in required]
            picked = req_sorted[:remaining_budget]
            if len(picked) < remaining_budget:
                picked += droppable[: remaining_budget - len(picked)]

        total_cols += len(picked)

        tables_out.append(TableSlice(
            table=t,
            columns=[ColumnRef(column=c) for c in picked],
        ))

    return tables_out, join_refs, truncated, missing_links_extra


def _split_ref(ref: str) -> tuple[str, str]:
    # "schema.table.column" or "table.column" depending on your physical naming
    parts = ref.split(".")
    if len(parts) >= 3:
        table = ".".join(parts[:-1])
        col = parts[-1]
        return table, col
    return parts[0], parts[-1]


def _join_tables(j: JoinRef) -> set[str]:
    return {_split_ref(j.from_ref)[0], _split_ref(j.to_ref)[0]}
```

### 8.9 Entitlement Filtering

In **passthrough** mode, schema linking returns the full slice and relies on downstream DB enforcement. In **strict** mode, schema linking must not leak unauthorized identifiers (even in logs/traces) and must filter before returning.

**v2 strict-mode placement:**

1. After retrieval (tables/columns/metrics) filter candidates
2. After closures (metric/connector/FK-key) filter newly-added tables/columns again
3. Recompute connectivity + budgets on the filtered slice

```python
async def filter_by_entitlements(
    *,
    user_id: str,
    sdm_id: str,
    tables: set[str],
    columns_by_table: dict[str, set[str]],
    mode: str,
    db: "AsyncSession",
) -> tuple[set[str], dict[str, set[str]], bool]:
    """Filter schema elements by user permissions.

    Modes per spec §5.4.5:
    - strict: Filter before returning, logging, or sending schema context to downstream components
    - passthrough: Return full slice, rely on DB enforcement

    Returns:
        filtered_tables, filtered_columns_by_table, any_denied
    """
    if mode == "passthrough":
        return tables, columns_by_table, False

    from sqlalchemy import text
    import fnmatch

    result = await db.execute(
        text("""
            SELECT table_patterns, column_exclusions
            FROM sdm_user_permissions
            WHERE user_id = :user_id AND sdm_id = :sdm_id
        """),
        {"user_id": user_id, "sdm_id": sdm_id},
    )
    permissions = result.fetchone()

    if not permissions:
        # No explicit permissions => no access in strict mode
        return set(), {}, True

    allowed_patterns = permissions.table_patterns or []
    excluded_columns = set(permissions.column_exclusions or [])

    def is_table_allowed(table: str) -> bool:
        return any(fnmatch.fnmatch(table, p) for p in allowed_patterns)

    filtered_tables = {t for t in tables if is_table_allowed(t)}

    filtered_columns_by_table: dict[str, set[str]] = {}
    for t, cols in columns_by_table.items():
        if t not in filtered_tables:
            continue

        keep_cols = set()
        for c in cols:
            if f"{t}.{c}" in excluded_columns:
                continue
            keep_cols.add(c)

        filtered_columns_by_table[t] = keep_cols

    any_denied = (filtered_tables != tables) or (filtered_columns_by_table != columns_by_table)
    return filtered_tables, filtered_columns_by_table, any_denied
```

**Admin-only full traces:** only emit full physical identifiers in traces when `X-Debug-Trace: full` and the requester is authorized as an admin (spec §5.4.5). Otherwise return `trace=null` or a redacted trace.

## Migration Strategy

### Phase 1: Core MVP (Zero LLM)

**Checklist:**

- [ ] Database schema: `sdm_linking_nodes`, `sdm_linking_edges`, `sdm_linking_cards` (with tsvector + GIN index)
- [ ] Domain models: `Card`, `SchemaSlice`, `SchemaGraph`
- [ ] Card generation from SDM (A-2)
- [ ] Schema graph construction (A-1)
- [ ] BM25 search implementation (D-1)
- [ ] Two-stage linking (D-3)
- [ ] Closure algorithms: membership, FK-key, metric (D-2)
- [ ] Confidence scoring (F-0)
- [ ] Fallback strategy (F-1)
- [ ] Schema slice output (G-1)
- [ ] API endpoint: `POST /api/v1/schema-link`
- [ ] Unit tests for all components
- [ ] Integration tests with sample SDM

**Feature Flag:** `ENABLE_SCHEMA_LINKING` (default: false)

**Performance Targets:**

- Card generation: < 30s for 500 tables
- Schema graph load: < 100ms for 500 tables
- End-to-end linking: < 200ms

### Phase 2: Accuracy & Scale

**Checklist:**

- [ ] Database schema: `sdm_linking_card_embeddings` (requires pgvector extension), `sdm_linking_artifacts`
- [ ] Enable pgvector: `CREATE EXTENSION IF NOT EXISTS vector;`
- [ ] Embedding generation and storage (requires embedding service)
- [ ] Hybrid retrieval: BM25 + embeddings + RRF (D-4)
- [ ] Bidirectional retrieval (D-5)
- [ ] Greedy connector minimization (D-6)
- [ ] Artifact caching by SDM version (A-3)
- [ ] Query understanding LLM integration (E-1)
- [ ] Recovery loop with query rewriting (E-2)
- [ ] Linking trace output (G-2)
- [ ] Integration tests with LLM mocks

**Feature Flag:** `ENABLE_SCHEMA_LINKING_LLM` (default: false)

**Performance Targets:**

- End-to-end with LLM: < 700ms typical
- Connector minimization: < 50ms for 500 tables

### Phase 2.1: Hierarchical Schemas

**Checklist:**

- [ ] `FieldCard` model for JSON schema fields
- [ ] Hierarchical card generation from JSON schemas (H-1)
- [ ] Field path handling in search
- [ ] Integration tests with JSON SDM

### Phase 3: Enterprise

**Checklist:**

- [ ] Database schema: `sdm_user_permissions`
- [ ] Policy filter implementation (B-1)
- [ ] Catalog router for multi-database (C-1)
- [ ] Ambiguity resolution with LLM (E-3)
- [ ] Cross-SDM relationship suggestions (E-4a)
- [ ] Cross-SDM join hints (E-4b)

**Feature Flag:** `ENABLE_SCHEMA_LINKING_ENTERPRISE` (default: false)

### Phase 4: Cross-Domain

**Checklist:**

- [ ] Unified SQL + JQ linking (I-1)
- [ ] Federation executor integration

### Rollback Procedure

1. Disable feature flag: `ENABLE_SCHEMA_LINKING=false`
2. Check logs for errors: `tail -f $(ls -t tmp/agent-server-*.log | head -1)`
3. If needed, rollback DB migrations:

```sql
-- Down migration for Phase 1
DROP TABLE IF EXISTS sdm_linking_cards;
DROP TABLE IF EXISTS sdm_linking_edges;
DROP TABLE IF EXISTS sdm_linking_nodes;
```

### Database Migrations

**Phase 1 - Up:**

```sql
-- See §6.1 Database Schema for full CREATE statements
CREATE TABLE sdm_linking_nodes (...);
CREATE TABLE sdm_linking_edges (...);
CREATE TABLE sdm_linking_cards (
    ...
    searchable_tsvector TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', searchable_text)) STORED
);
CREATE INDEX idx_sdm_linking_cards_fts ON sdm_linking_cards USING GIN(searchable_tsvector);
```

**Phase 1 - Down:**

```sql
DROP TABLE IF EXISTS sdm_linking_cards;
DROP TABLE IF EXISTS sdm_linking_edges;
DROP TABLE IF EXISTS sdm_linking_nodes;
```

**Phase 2 - Up:**

```sql
-- Enable pgvector extension (requires superuser or extension already installed)
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE sdm_linking_card_embeddings (...);
CREATE INDEX idx_sdm_linking_embeddings_vec ON sdm_linking_card_embeddings
    USING hnsw (embedding vector_cosine_ops);

CREATE TABLE sdm_linking_artifacts (...);
```

**Phase 2 - Down:**

```sql
DROP TABLE IF EXISTS sdm_linking_card_embeddings;
DROP TABLE IF EXISTS sdm_linking_artifacts;
-- Note: Don't drop pgvector extension as other features may use it
```

**Phase 3 - Up:**

```sql
CREATE TABLE sdm_user_permissions (...);
```

---

## References

- [Specification](./schema-linking-specification.md)
- [Python Guidelines](/.claude/skills/python-guidelines/SKILL.md)
- [AGENTS.md](/AGENTS.md)
