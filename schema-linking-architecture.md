# Architecture Guide: Schema Linking and Pruning

**Date:** 2026-01-22  
**Audience:** Software engineers, technical leads, DevOps  
**Specification:** See [schema-linking-specification.md](./schema-linking-specification.md) for requirements and user stories

---

## Overview

This document provides implementation guidance for the Schema Linking and Pruning feature. It covers:

- Technical architecture decisions (storage, embedding models, BM25)
- Detailed algorithms and data structures
- Migration strategy with test data requirements and tuning procedures
- Rollback and operational strategies

**For "what to build"**, see the [specification document](./schema-linking-specification.md).  
**This document focuses on "how to build it".**

---

## Table of Contents

1. [Story-to-Architecture Mapping](#story-to-architecture-mapping)
2. [Performance Targets](#performance-targets)
3. [Implementation Architecture](#implementation-architecture)
4. [Routing Artifacts: SDM Cards & Indexes](#routing-artifacts-sdm-cards--indexes)
5. [Schema Graph Data Structure](#schema-graph-data-structure)
6. [Linking Algorithm](#linking-algorithm)
7. [Scoring Formula & Configuration](#scoring-formula--configuration)
8. [Migration Strategy](#migration-strategy)
9. [Rollback Strategy](#rollback-strategy)
10. [Appendix: Semi-Structured / JSON Support](#appendix-semi-structured--json-support)

---

## Story-to-Architecture Mapping

This table maps each user story (from [schema-linking-specification.md](./schema-linking-specification.md)) to the relevant architecture sections.

### Epic A: Build and Persist Schema Graphs + Routing Artifacts

| Story | Description                 | Architecture Sections                                                                                                                               |
| ----- | --------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| A-1   | Derive Graph from SDM       | [Schema Graph Data Structure](#schema-graph-data-structure), [Decision 1: Storage Layer](#decision-1-storage-layer-critical---required-for-phase-1) |
| A-2   | Version and Cache Artifacts | [Decision 1: Storage Layer](#decision-1-storage-layer-critical---required-for-phase-1), [Migration Strategy Phase 1](#phase-1-foundation)           |
| A-3   | Generate SDM Cards          | [Routing Artifacts: SDM Cards & Indexes](#routing-artifacts-sdm-cards--indexes), [Card Types](#card-types)                                          |

### Epic B: Schema Linking Engine

| Story | Description                | Architecture Sections                                                                                                                                                                                                  |
| ----- | -------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| B-1   | Baseline Retrieval Linker  | [Linking Algorithm](#linking-algorithm), [Decision 2: Embedding Model](#decision-2-embedding-model-critical---required-for-phase-2), [Decision 3: BM25](#decision-3-bm25-implementation-medium---required-for-phase-2) |
| B-2   | Learned Linking (Optional) | [Decision 5: SLM Models](#decision-5-slm-models-for-phase-5-optional---defer-until-phase-5), [Migration Strategy Phase 5](#phase-5-guardrails-and-optimization)                                                        |
| B-3   | Two-Stage Linker           | [Linking Algorithm Step 3](#step-3-two-stage-selection), [Default Configuration](#default-configuration)                                                                                                               |
| B-4   | Deterministic Refinement   | [Linking Algorithm Step 4](#step-4-deterministic-refinement), [Schema Graph Data Structure](#schema-graph-data-structure)                                                                                              |

### Epic C: Prompt Pruning and NL2SQL Integration

| Story | Description             | Architecture Sections                                                                                                                                                                                    |
| ----- | ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| C-1   | Pruned Schema Prompting | [Linking Algorithm Step 5](#step-5-schema-enrichment-bounded), [Domain Models: LinkingResult](#domain-models)                                                                                            |
| C-2   | Low-Confidence Fallback | [Linking Algorithm Step 6](#step-6-confidence--fallback), [Decision 6: Confidence Thresholds](#decision-6-confidence-threshold-tuning-medium---tune-in-phase-3), [Rollback Strategy](#rollback-strategy) |

### Epic D: Evaluation and Observability

| Story | Description     | Architecture Sections                                                                                                           |
| ----- | --------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| D-1   | Linking Metrics | [Test Data Requirements](#test-data-requirements), [Tuning Playbook](#tuning-playbook), [Operations to Log](#operations-to-log) |

### Epic E: Operations and Maintenance

| Story | Description     | Architecture Sections                                                                                                                     |
| ----- | --------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| E-1   | SDM Update Hook | [Migration Strategy](#migration-strategy), [Rollback Strategy](#rollback-strategy), [Transactional Operations](#transactional-operations) |

### Epic F: Semantic-Layer Inbound Query Translation (Optional)

| Story | Description              | Architecture Sections                          |
| ----- | ------------------------ | ---------------------------------------------- |
| F-1   | Inbound Query Generation | Not yet detailed in architecture (future work) |
| F-2   | Query Engine Compilation | Not yet detailed in architecture (future work) |

### Epic G: Schema Linking Enhancements

| Story | Description                          | Architecture Sections                                                                                 |
| ----- | ------------------------------------ | ----------------------------------------------------------------------------------------------------- |
| G-1   | Schema Metadata Enrichment           | [Linking Algorithm Step 5](#step-5-schema-enrichment-bounded), [Card Types](#card-types)              |
| G-2   | Matched Value Retrieval              | [Indexes](#indexes-per-sdm-version) (Value index), [Boosts](#boosts-additive)                         |
| G-3   | Demonstration Retrieval              | [Card Types](#card-types) (Verified Query cards)                                                      |
| G-4   | Question Decomposition               | [Decision 5: SLM Models](#decision-5-slm-models-for-phase-5-optional---defer-until-phase-5)           |
| G-5   | Schema Enrichment Beyond Minimal Set | [Linking Algorithm Step 5](#step-5-schema-enrichment-bounded)                                         |
| G-6   | Verified Query Anchoring             | [Card Types](#card-types) (Verified Query cards), [Boosts](#boosts-additive)                          |
| G-7   | SQL Skeleton Demo Selection          | [Indexes](#indexes-per-sdm-version) (SQL skeleton index)                                              |
| G-8   | Query Rewrite (Conditional)          | [Decision 6: Confidence Thresholds](#decision-6-confidence-threshold-tuning-medium---tune-in-phase-3) |
| G-9   | Multi-Sample Union (Conditional)     | [Decision 6: Confidence Thresholds](#decision-6-confidence-threshold-tuning-medium---tune-in-phase-3) |

### Epic H: Guardrails and Optimization

| Story | Description                     | Architecture Sections                                                                                                                        |
| ----- | ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| H-1   | Extractive Selection Constraint | [Domain Models](#domain-models), [Linking Algorithm](#linking-algorithm)                                                                     |
| H-2   | Repair Loop on Execution Error  | [Rollback Strategy](#rollback-strategy) (error handling patterns)                                                                            |
| H-3   | Complexity Classifier (SLM)     | [Decision 5: SLM Models](#decision-5-slm-models-for-phase-5-optional---defer-until-phase-5)                                                  |
| H-4   | SLM Reranker                    | [Decision 5: SLM Models](#decision-5-slm-models-for-phase-5-optional---defer-until-phase-5)                                                  |
| H-5   | Learned Confidence Calibration  | [Confidence Estimation](#confidence-estimation), [Decision 5: SLM Models](#decision-5-slm-models-for-phase-5-optional---defer-until-phase-5) |

---

## Performance Targets

Consolidated performance targets from the specification. These define the latency and throughput requirements for each component.

### Artifact Generation (Offline)

| Operation                   | Target                                   | Rationale                                    |
| --------------------------- | ---------------------------------------- | -------------------------------------------- |
| Graph generation (A-1)      | < 30s for 500-table SDM                  | One-time per SDM version                     |
| Card generation (A-3)       | < 30s for 500-table SDM with 5000 fields | One-time per SDM version                     |
| Artifact regeneration (E-1) | < 5 minutes for 500-table SDM            | Background job, includes embedding API calls |

### Artifact Loading (Startup)

| Operation                    | Target                    | Rationale                       |
| ---------------------------- | ------------------------- | ------------------------------- |
| Graph loading (A-1)          | < 100ms for 500-table SDM | Critical path for first request |
| Artifact cache loading (A-2) | < 500ms for 500-table SDM | Service startup time            |

### Linking Pipeline (Online - Per Request)

| Operation                      | Target                                       | Rationale                 |
| ------------------------------ | -------------------------------------------- | ------------------------- |
| **End-to-end linking**         | < 500ms (excluding embedding API)            | User-facing latency       |
| Two-stage retrieval (B-3)      | 2x faster than single-stage for 1000+ fields | Scalability               |
| Deterministic refinement (B-4) | < 50ms                                       | Post-retrieval processing |
| Prompt building (C-1)          | < 20ms                                       | Serialization overhead    |
| Metrics computation (D-1)      | < 10ms per query                             | Observability overhead    |

### Enhancement Operations (Conditional)

| Operation                      | Target             | When Triggered                          |
| ------------------------------ | ------------------ | --------------------------------------- |
| Value matching (G-2)           | < 200ms            | Always (if enabled)                     |
| Demonstration retrieval (G-3)  | < 300ms            | Always (if enabled)                     |
| Anchored linking (G-6)         | < 200ms            | When similar verified query found       |
| Skeleton-based retrieval (G-7) | < 100ms additional | When skeleton index available           |
| Query rewrite (G-8)            | < 1s               | Confidence < threshold                  |
| Multi-sampling (G-9)           | < 1s               | Confidence < threshold or complex query |
| Question decomposition (G-4)   | < 500ms            | Complex queries only                    |

### Guardrail Operations

| Operation                       | Target                    | Rationale                     |
| ------------------------------- | ------------------------- | ----------------------------- |
| ID validation (H-1)             | < 5ms                     | Simple lookup                 |
| Complexity classification (H-3) | < 50ms                    | Gate for expensive operations |
| SLM reranking (H-4)             | < 100ms for 50 candidates | Precision improvement         |
| Confidence prediction (H-5)     | < 10ms                    | Lightweight model             |
| Repair loop (H-2)               | < 2s when triggered       | Extra LLM call                |

### Timeout Configuration

| Operation                     | Timeout | Action on Timeout         |
| ----------------------------- | ------- | ------------------------- |
| Schema linking (sync)         | 5s      | Return fallback schema    |
| Card generation               | 30s     | Fail with error           |
| Embedding API call            | 30s     | Retry once, then fail     |
| Artifact refresh (background) | 5min    | Alert, keep old artifacts |

---

## Feature Availability Matrix

This matrix summarizes which capabilities are available based on storage mode and embedding configuration.

| Capability               | Postgres + pgvector | Postgres (no embeddings) | SQLite-only          |
| ------------------------ | ------------------- | ------------------------ | -------------------- |
| Routing cards storage    | ✅                  | ✅                       | ✅                   |
| Schema graph storage     | ✅                  | ✅                       | ✅                   |
| BM25 retrieval           | ✅ (tsvector)       | ✅ (tsvector)            | ✅ (FTS5 if enabled) |
| Embedding retrieval      | ✅                  | ❌                       | ❌                   |
| RRF fusion               | ✅                  | ✅ (BM25-only)           | ✅ (BM25-only)       |
| Verified query signals   | ✅                  | ✅                       | ✅                   |
| Anchored boosts (G-6)    | ✅                  | ✅                       | ✅                   |
| Value index (G-2)        | ✅                  | ✅                       | ✅ (reduced scale)   |
| SQL skeleton index (G-7) | ✅                  | ✅                       | ✅ (reduced scale)   |

**Notes:**

- SQLite-only mode uses BM25-only retrieval and reduced scale limits.
- Embedding features are enabled only when a model is configured and vector storage is available.

---

## Implementation Architecture

This section outlines the key technical decisions that must be made during implementation. Each decision point includes recommended options with trade-offs to guide the implementer.

---

### Database Naming Convention

All database objects for this feature follow a consistent naming pattern for easy identification and maintenance.

**Table Naming:**

- **Prefix:** All SDM feature tables use `sdm_*` prefix
- **Pattern:** `sdm_<component>` or `sdm_<subfeature>_<component>`
- **Examples:**
  - `sdm_routing_cards` (routing/linking cards)
  - `sdm_schema_graph` (schema graph for linking)
  - Future: `sdm_value_index`, `sdm_skeleton_index`, etc.

**Index Naming:**

- **Pattern:** `idx_<table_name>_<column(s)>`
- **Examples:**
  - `idx_routing_cards_sdm_version`
  - `idx_routing_cards_card_type`
  - `idx_routing_cards_fts` (full-text search)
  - `idx_routing_cards_vector` (vector search)

**Benefits:**

- ✅ Easy to find all SDM tables: `SELECT * FROM information_schema.tables WHERE table_name LIKE 'sdm_%'`
- ✅ Clear ownership and feature grouping
- ✅ Avoids naming conflicts with other features
- ✅ Version management handled via migrations (not table names)
- ✅ Consistent with existing codebase patterns

**Anti-patterns to avoid:**

- ❌ `v2_sdm_*` prefix (versions belong in migrations, not table names)
- ❌ Generic names like `routing_cards` (unclear which feature)
- ❌ Mixed prefixes like `sdm_v2_*` (inconsistent)

---

### Decision 1: Storage Layer (CRITICAL - Required for Phase 1)

**Question:** Where should we persist routing cards, schema graphs, and retrieval indexes?

| Option                                    | Components                                                                                                      | Pros                                                                                                     | Cons                                                                                  | Recommendation                                         |
| ----------------------------------------- | --------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| **A: PostgreSQL + pgvector**              | Cards: JSONB table<br>Graph: relational tables<br>BM25: tsvector/ts_rank<br>Embeddings: pgvector HNSW           | • Single database<br>• Transactional consistency<br>• Lower operational overhead<br>• Native FTS support | • pgvector less mature than dedicated vector DBs<br>• May need tuning for large scale | **RECOMMENDED** for MVP<br>Simplicity + existing infra |
| **B: PostgreSQL + Dedicated Vector DB**   | Cards: JSONB table<br>Graph: relational tables<br>BM25: PostgreSQL FTS<br>Embeddings: Qdrant/Weaviate/Milvus    | • Best-in-class vector search<br>• Better scaling for embeddings<br>• Rich filtering capabilities        | • Extra infrastructure<br>• Cross-system consistency<br>• Higher complexity           | Consider for Phase 4+ if scale demands it              |
| **C: PostgreSQL + Elasticsearch**         | Cards: JSONB table<br>Graph: relational tables<br>BM25: Elasticsearch<br>Embeddings: Elasticsearch dense_vector | • Production-grade search<br>• Rich query DSL<br>• Good hybrid search                                    | • Heavy infrastructure<br>• Elasticsearch ops overhead<br>• Redundant storage         | Only if already using ES                               |
| **D: SQLite-only (Studio compatibility)** | Cards: JSON table<br>Graph: JSON table<br>BM25: FTS5 (if enabled)<br>Embeddings: not available                  | • Works in Studio today<br>• Zero external dependencies                                                  | • No vector search<br>• Reduced recall/precision<br>• Limited scale                   | **REQUIRED** until Studio is decommissioned            |

**Schema (Option A - Recommended):**

```sql
-- Routing cards for schema linking
-- Naming convention: sdm_* prefix for all SDM-related tables
CREATE TABLE sdm_routing_cards (
    id TEXT PRIMARY KEY,  -- e.g., "table:sdm123:customers"
    sdm_id TEXT NOT NULL,
    sdm_version TEXT NOT NULL,
    card_type TEXT NOT NULL,  -- 'table' | 'field' | 'metric' | 'relationship' | 'verified_query'
    text_content TEXT NOT NULL,  -- For BM25
    text_vector vector(1536),  -- For embedding search (adjust dimension based on model)
    metadata JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_routing_cards_sdm_version (sdm_id, sdm_version),
    INDEX idx_routing_cards_card_type (card_type)
);

-- Full-text search index for BM25
CREATE INDEX idx_routing_cards_fts ON sdm_routing_cards
    USING GIN(to_tsvector('english', text_content));

-- Vector index for embedding search (HNSW)
CREATE INDEX idx_routing_cards_vector ON sdm_routing_cards
    USING hnsw (text_vector vector_cosine_ops);

-- Schema graph for linking
CREATE TABLE sdm_schema_graph (
    sdm_id TEXT NOT NULL,
    sdm_version TEXT NOT NULL,
    graph_data JSONB NOT NULL,  -- Adjacency list + metadata
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (sdm_id, sdm_version)
);
```

**Naming Convention Notes:**

- All SDM feature tables use `sdm_*` prefix for easy identification
- Sub-feature indicated in table name: `sdm_routing_cards`, `sdm_schema_graph`
- Indexes named with table name prefix: `idx_routing_cards_*`
- Version management handled via database migrations, not table names

**Capability Gating:**

- If running in SQLite-only mode, disable embeddings and use BM25-only retrieval.
- Feature availability should be determined at runtime (storage capabilities + embedding config).
- Do not block linking when embeddings are unavailable; degrade to keyword-only retrieval.

---

### Decision 2: Embedding Model (CRITICAL - Required for Phase 2)

**Question:** Which embedding model should we use for semantic retrieval, and how do we handle environments without embeddings?

| Option                                 | Model                | Dimensions | Pros                                                                            | Cons                                                                    | Cost     | Recommendation                       |
| -------------------------------------- | -------------------- | ---------- | ------------------------------------------------------------------------------- | ----------------------------------------------------------------------- | -------- | ------------------------------------ |
| **A: OpenAI text-embedding-3-small**   | OpenAI API           | 1536       | • High quality<br>• Fast inference<br>• Well-tested<br>• No maintenance         | • API cost (~$0.02/1M tokens)<br>• External dependency<br>• Rate limits | $$$      | **RECOMMENDED** when available       |
| **B: text-embedding-3-large**          | OpenAI API           | 3072       | • Best quality<br>• Latest model                                                | • Higher cost<br>• Slower<br>• Larger vectors                           | $$$$     | Use only if A fails quality bar      |
| **C: all-MiniLM-L6-v2**                | Local (HuggingFace)  | 384        | • Free<br>• Fast<br>• Runs locally<br>• No API limits                           | • Lower quality than OpenAI<br>• Need GPU for speed<br>• Self-managed   | Free     | Good for dev/testing                 |
| **D: Configurable provider (LiteLLM)** | Any configured model | Variable   | • Flexible per customer<br>• Central config<br>• Works with bring-your-own keys | • Availability varies<br>• Quality varies                               | Variable | **Preferred long-term**              |
| **E: Embeddings disabled**             | None                 | N/A        | • No external dependency                                                        | • Lower recall/precision                                                | Free     | **Fallback when no model available** |

**Implementation Notes:**

- Embedding model must be **configurable at runtime** (env/config, not hard-coded).
- When **no embedding model** is configured, run **BM25-only** retrieval.
- Start with **Option A** when available; use **Option D** for enterprise configuration.
- Batch encode all cards during artifact generation (Story A-3).
- Cache embeddings in `text_vector` column (when supported by storage).
- Re-embed only on SDM updates.
- Monitor API costs; if >$100/month, consider Option C for some workloads.

---

### Decision 3: BM25 Implementation (MEDIUM - Required for Phase 2)

**Question:** How should we implement BM25 keyword search?

| Option                             | Technology                | Pros                                                                                      | Cons                                                                                                | Recommendation                                          |
| ---------------------------------- | ------------------------- | ----------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| **A: PostgreSQL Full-Text Search** | `tsvector` + `ts_rank_cd` | • Native to PostgreSQL<br>• Persistent<br>• Transactional<br>• Good enough for most cases | • Less flexible than Elasticsearch<br>• BM25 requires custom function<br>• Limited language support | **RECOMMENDED** for MVP<br>Aligns with Option A storage |
| **B: rank-bm25 (Python library)**  | In-memory Python index    | • Simple to use<br>• Pure BM25<br>• No config needed                                      | • Not persistent (rebuild on restart)<br>• Memory overhead<br>• Single-process                      | Good for prototyping<br>Not production-ready            |
| **C: Elasticsearch**               | Dedicated search cluster  | • Production-grade<br>• True BM25<br>• Rich query features                                | • Extra infrastructure<br>• Operational overhead<br>• Overkill for this use case                    | Only if already using ES                                |

**Implementation (Option A - Recommended):**

```python
# BM25-style scoring with PostgreSQL
# Use ts_rank_cd with custom weights to approximate BM25

query = """
SELECT
    id,
    card_type,
    text_content,
    metadata,
    ts_rank_cd(
        to_tsvector('english', text_content),
        plainto_tsquery('english', %s),
        32  -- normalization flag: 32 = length normalization (BM25-like)
    ) AS bm25_score
FROM sdm_routing_cards
WHERE
    sdm_id = %s AND sdm_version = %s
    AND to_tsvector('english', text_content) @@ plainto_tsquery('english', %s)
ORDER BY bm25_score DESC
LIMIT %s;
"""
# Note: This is an approximation. For true BM25, consider adding a custom PostgreSQL function
# or accept ts_rank_cd as "close enough" for Phase 2.
```

---

### Decision 4: Reciprocal Rank Fusion (RRF) Parameters (LOW - Can tune in Phase 3)

**Question:** What value should we use for `k_rrf` in the RRF formula?

| Value              | Behavior                                                      | Use Case                                        |
| ------------------ | ------------------------------------------------------------- | ----------------------------------------------- |
| **k=60** (default) | Balanced: top results matter, but rank 20-50 still contribute | Recommended starting point (RASL paper default) |
| **k=40**           | More aggressive: top-10 dominate, lower ranks decay fast      | Use if retrieval is very precise                |
| **k=80**           | More conservative: lower-ranked results get more credit       | Use if retrieval is noisy                       |

**Formula:**

```
rrf(item) = Σ (1 / (k + rank_in_list_i)) for all lists containing item
```

**Tuning:** Run grid search over k ∈ {40, 60, 80} in Phase 3 validation.

---

### Decision 5: SLM Models for Phase 5 (OPTIONAL - Defer until Phase 5)

**Question:** Which small language models should we use for complexity classification and reranking?

| Use Case                  | Model Options                                                                 | Recommendation                                                                                         |
| ------------------------- | ----------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| **Complexity Classifier** | • DistilBERT (66M params)<br>• MiniLM (22M params)<br>• Rule-based (0 params) | Start with **rule-based** (count joins, aggregations, subqueries)<br>Upgrade to MiniLM if insufficient |
| **Schema Reranker**       | • MiniLM cross-encoder<br>• DistilBERT cross-encoder<br>• T5-small (60M)      | Use **MiniLM cross-encoder** fine-tuned on schema relevance                                            |

**Training Data for SLMs (Phase 5):**

- Synthetic queries generated from verified queries (vary parameters)
- User query logs (anonymized, labeled by execution success)
- Manually labeled dev set (200+ diverse queries)

---

### Decision 6: Confidence Threshold Tuning (MEDIUM - Tune in Phase 3)

**Question:** What confidence thresholds should trigger fallback behaviors?

| Threshold             | Default | Behavior                             | Tuning Guidance                                              |
| --------------------- | ------- | ------------------------------------ | ------------------------------------------------------------ |
| `confidence_low`      | 0.60    | Trigger query rewrite + wider schema | Lower if false positives high; raise if missing hard queries |
| `confidence_very_low` | 0.45    | Fallback to full SDM                 | Rare; only for catastrophic linking failures                 |

**Confidence Formula:**

```
confidence = (conf_margin × 0.5) + (conf_connect × 0.3) + (conf_coverage × 0.2)

Where:
- conf_margin = sigmoid((score_top - score_kth) / 0.25)  # How clear is the winner?
- conf_connect = clamp(1.0 - 0.15 × bridges, 0, 1)       # Is schema connected?
- conf_coverage = matched_value_hits / total_values      # Did we match user's values?
```

**Tuning:** Track correlation between confidence and execution accuracy (EX). Adjust thresholds to minimize false negatives (missed queries) while keeping fallback rate < 10%.

---

### Decision Summary Table

| Decision              | Phase Required | Criticality  | Recommended Default                     |
| --------------------- | -------------- | ------------ | --------------------------------------- |
| Storage Layer         | Phase 1        | **CRITICAL** | PostgreSQL + pgvector                   |
| Embedding Model       | Phase 2        | **CRITICAL** | text-embedding-3-small                  |
| BM25 Implementation   | Phase 2        | **CRITICAL** | PostgreSQL FTS (ts_rank_cd)             |
| RRF k value           | Phase 2        | LOW          | k=60 (tune in Phase 3)                  |
| Confidence Thresholds | Phase 3        | MEDIUM       | low=0.60, very_low=0.45                 |
| SLM Models            | Phase 5        | LOW          | Rule-based classifier + MiniLM reranker |

**Next Steps:**

1. Implement Option A (PostgreSQL + pgvector) for Phases 1-3
2. Use text-embedding-3-small for embedding
3. Use PostgreSQL FTS for BM25
4. Defer SLM decisions until Phase 5
5. Tune thresholds and parameters in Phase 3 validation

---

## Routing Artifacts: SDM Cards & Indexes

### Why Separate Artifacts?

The SDM is maintained as Snowflake-style semantic YAML—ideal for business metadata but awkward for:

- High-performance retrieval
- JSON/semi-structured paths
- High-cardinality value indexes

**Solution:** Keep SDM as the source of truth, but generate **routing artifacts** (cards + indexes) as separate, machine-friendly JSON documents per SDM version.

### Card Types

Each card is a short retrieval document with stable IDs and provenance back to the SDM.

| Card Type          | ID Format                          | Text Content                                      | Metadata                                 |
| ------------------ | ---------------------------------- | ------------------------------------------------- | ---------------------------------------- |
| **Table**          | `table:<sdm_id>:<table_name>`      | Name + description + synonyms                     | Source, rowcount, domain tags            |
| **Field**          | `field:<sdm_id>:<table>:<field>`   | Name + description + type + samples + synonyms    | Type, is_enum, PK/FK flags, parent table |
| **Metric**         | `metric:<sdm_id>:<table>:<metric>` | Name + description + expression tokens + synonyms | Parent table, expression, grain          |
| **Relationship**   | `rel:<sdm_id>:<rel_name>`          | Name + left/right tables + join keys              | Join keys, directionality, cardinality   |
| **Verified Query** | `vq:<sdm_id>:<vq_name>`            | NLQ + domain tags + SQL skeleton                  | Referenced tables/fields, full SQL       |

### Indexes (per SDM version)

- **BM25 index** over card text (keyword matching)
- **Embedding ANN index** over card text (semantic similarity)
- **Value index** (optional) over enum-like dimension values
- **SQL skeleton index** (optional) for verified query similarity

---

## Schema Graph Data Structure

This section defines the graph data structure used for Story A-1 (Derive Graph from SDM) and Story B-4 (Deterministic Refinement). The graph enables joinability queries and shortest-path computations required for FK-path closure.

### Graph Requirements (from Specification)

The schema graph must support these operations:

1. **Joinability query:** Given two tables, determine if they can be joined (directly or through intermediate tables)
2. **Shortest path:** Given two tables, find the shortest join path between them
3. **Neighbor query:** Given a table, find all tables it can join to

### Graph Node Schema

```python
from pydantic import BaseModel, Field
from typing import Literal

class GraphNode(BaseModel):
    """A node in the schema graph representing a table or field."""
    id: str = Field(..., description="Unique ID: 'table:<sdm_id>:<name>' or 'field:<sdm_id>:<table>:<name>'")
    node_type: Literal["table", "field"]
    name: str = Field(..., description="Display name from SDM")
    sdm_id: str
    sdm_version: str

    # Table-specific fields
    description: str | None = None

    # Field-specific fields (only for node_type="field")
    parent_table: str | None = Field(None, description="Parent table name (for fields)")
    data_type: str | None = Field(None, description="SQL data type: INTEGER, VARCHAR, etc.")
    is_primary_key: bool = Field(default=False)
    is_foreign_key: bool = Field(default=False)
    foreign_key_target: str | None = Field(None, description="Target table.column for FK fields")
```

### Graph Edge Schema

```python
class GraphEdge(BaseModel):
    """An edge in the schema graph representing a relationship."""
    id: str = Field(..., description="Unique ID: 'edge:<sdm_id>:<source>:<target>'")
    edge_type: Literal["contains", "fk_reference", "join"]
    source_node_id: str = Field(..., description="Source node ID")
    target_node_id: str = Field(..., description="Target node ID")

    # Relationship details (for fk_reference and join edges)
    join_keys: list[tuple[str, str]] | None = Field(
        None,
        description="List of (source_column, target_column) pairs"
    )
    cardinality: Literal["1:1", "1:N", "N:1", "N:M"] | None = None
    relationship_name: str | None = Field(None, description="Name from SDM relationship")

    # Edge is bidirectional for traversal
    is_bidirectional: bool = Field(default=True, description="Can traverse in both directions")
```

### Edge Types

| Edge Type      | Source     | Target     | Purpose                                    |
| -------------- | ---------- | ---------- | ------------------------------------------ |
| `contains`     | Table node | Field node | Represents table-field ownership           |
| `fk_reference` | Table node | Table node | Foreign key relationship from SDM          |
| `join`         | Table node | Table node | Joinable tables (may not have explicit FK) |

### Complete Graph Schema

```python
class SchemaGraph(BaseModel):
    """The complete schema graph for an SDM version."""
    sdm_id: str
    sdm_version: str
    nodes: dict[str, GraphNode] = Field(default_factory=dict, description="Node ID → Node")
    edges: list[GraphEdge] = Field(default_factory=list)

    # Adjacency list for fast traversal (built from edges)
    adjacency: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Node ID → list of connected Node IDs"
    )

    def get_node(self, node_id: str) -> GraphNode | None:
        """Get a node by ID."""
        return self.nodes.get(node_id)

    def get_neighbors(self, node_id: str) -> list[str]:
        """Get all nodes connected to this node."""
        return self.adjacency.get(node_id, [])

    def are_joinable(self, table1: str, table2: str) -> bool:
        """Check if two tables can be joined (directly or via path)."""
        # Uses BFS/DFS on adjacency list
        ...

    def shortest_join_path(self, table1: str, table2: str) -> list[str] | None:
        """Find shortest path of tables to join table1 to table2.

        Returns list of table node IDs forming the path, or None if no path exists.
        Used for FK-path closure in Story B-4.
        """
        # Uses BFS for unweighted shortest path
        ...

    def get_join_keys(self, table1: str, table2: str) -> list[tuple[str, str]] | None:
        """Get join key pairs for directly connected tables.

        Used for FK-key closure in Story B-4.
        """
        ...
```

### Database Storage

The graph is stored as JSONB in the `sdm_schema_graph` table (defined in [Decision 1: Storage Layer](#decision-1-storage-layer-critical---required-for-phase-1)):

```sql
CREATE TABLE sdm_schema_graph (
    sdm_id TEXT NOT NULL,
    sdm_version TEXT NOT NULL,
    graph_data JSONB NOT NULL,  -- Serialized SchemaGraph
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (sdm_id, sdm_version)
);
```

### Example Graph (Serialized)

```json
{
  "sdm_id": "sales_sdm",
  "sdm_version": "v1.2.0",
  "nodes": {
    "table:sales_sdm:orders": {
      "id": "table:sales_sdm:orders",
      "node_type": "table",
      "name": "orders",
      "description": "Customer orders"
    },
    "table:sales_sdm:customers": {
      "id": "table:sales_sdm:customers",
      "node_type": "table",
      "name": "customers",
      "description": "Customer master data"
    },
    "field:sales_sdm:orders:customer_id": {
      "id": "field:sales_sdm:orders:customer_id",
      "node_type": "field",
      "name": "customer_id",
      "parent_table": "orders",
      "data_type": "INTEGER",
      "is_foreign_key": true,
      "foreign_key_target": "customers.id"
    }
  },
  "edges": [
    {
      "id": "edge:sales_sdm:orders:customer_id",
      "edge_type": "contains",
      "source_node_id": "table:sales_sdm:orders",
      "target_node_id": "field:sales_sdm:orders:customer_id"
    },
    {
      "id": "edge:sales_sdm:orders_to_customers",
      "edge_type": "fk_reference",
      "source_node_id": "table:sales_sdm:orders",
      "target_node_id": "table:sales_sdm:customers",
      "join_keys": [["customer_id", "id"]],
      "cardinality": "N:1",
      "relationship_name": "orders_to_customers"
    }
  ],
  "adjacency": {
    "table:sales_sdm:orders": ["field:sales_sdm:orders:customer_id", "table:sales_sdm:customers"],
    "table:sales_sdm:customers": ["table:sales_sdm:orders"]
  }
}
```

### Graph Operations for Deterministic Refinement (Story B-4)

```python
def fk_path_closure(linked_tables: set[str], graph: SchemaGraph) -> set[str]:
    """Add bridge tables needed to connect all linked tables.

    For each pair of linked tables that aren't directly connected,
    find the shortest path and add intermediate tables.
    """
    result = set(linked_tables)
    table_list = list(linked_tables)

    for i, t1 in enumerate(table_list):
        for t2 in table_list[i+1:]:
            if not graph.are_directly_connected(t1, t2):
                path = graph.shortest_join_path(t1, t2)
                if path:
                    result.update(path)

    return result


def fk_key_closure(linked_tables: set[str], graph: SchemaGraph) -> set[str]:
    """Add join key fields for all relationships between linked tables.

    For each pair of linked tables with a relationship,
    ensure both join key columns are included.
    """
    linked_fields = set()

    for edge in graph.edges:
        if edge.edge_type in ("fk_reference", "join"):
            if edge.source_node_id in linked_tables and edge.target_node_id in linked_tables:
                if edge.join_keys:
                    for source_col, target_col in edge.join_keys:
                        linked_fields.add(f"field:{graph.sdm_id}:{edge.source_node_id.split(':')[-1]}:{source_col}")
                        linked_fields.add(f"field:{graph.sdm_id}:{edge.target_node_id.split(':')[-1]}:{target_col}")

    return linked_fields
```

### Edge Cases

| Case                                                         | Handling                                                                           |
| ------------------------------------------------------------ | ---------------------------------------------------------------------------------- |
| **Self-referential relationship** (e.g., employee → manager) | Create edge from table to itself; `shortest_join_path` returns single-element path |
| **Composite foreign key** (multiple column pairs)            | Single edge with multiple entries in `join_keys` list                              |
| **Isolated table** (no relationships)                        | Table node exists with empty adjacency list; `are_joinable` returns False          |
| **Circular relationships**                                   | BFS handles cycles via visited set; no infinite loops                              |
| **Missing relationship in SDM**                              | Tables appear as disconnected; linking logs warning                                |

---

## Linking Algorithm

**Orchestration boundary:** The linker returns a focused schema slice plus evidence. It does not decide whether to execute a verified query tool or block iterative LLM attempts. The outer agent can use verified-query candidates or request expanded context.

### Step 0: Parse the Question

Extract lightweight signals from the NL question:

- **Literals:** Quoted strings, numbers, date phrases
- **Intent hints:** "top N", "trend", "by", "compare", "conversion rate"
- **Candidate entities:** Words/phrases for retrieval queries

### Step 1: Candidate Retrieval (High Recall)

Query the retrieval indexes to get candidates:

| Card Type        | Retrieve Top-N |
| ---------------- | -------------- |
| Tables           | 20             |
| Fields           | 80             |
| Metrics          | 25             |
| Verified Queries | 5              |
| Relationships    | 15 (optional)  |

**Capability gating:**

- If embeddings are unavailable, retrieve candidates using **BM25 only**.
- If vector search is available, use **BM25 + embeddings**.

### Step 2: Evidence Scoring

Score each entity using:

- **Reciprocal Rank Fusion (RRF)** of BM25 and embedding ranks (when embeddings available)
- **BM25-only scoring** when embeddings are disabled/unavailable
- **Boosts:** Matched values, type hints, verified query membership (as a signal)

Aggregate evidence to table level:

- Tables score from their own card match
- Tables score from strong field/metric matches
- Tables score from appearing in retrieved verified queries

### Step 3: Two-Stage Selection

**Stage 1: Select Tables**

- Pick top-K tables by aggregated score (default: 8)
- Include parent tables of top fields/metrics

**Stage 2: Select Fields Within Tables**

- Pick top fields/metrics within selected tables
- Include join keys for selected relationships

### Step 4: Deterministic Refinement

Enforce database logic to guarantee executable SQL:

1. **Table membership closure:** If a field is included, include its parent table
2. **FK-path closure:** Ensure selected tables form a connected subgraph; add bridging tables as needed
3. **FK-key closure:** If a relationship is used, include both join key fields
4. **Fuzzy repair (optional):** Match LLM-generated names to closest valid schema elements

### Step 5: Schema Enrichment (Bounded)

Add predictable enrichment without bloating the prompt:

- **Always include:** PK fields, join keys for selected relationships
- **Add up to 3 representative fields per table:**
  - One "name/title/label" field
  - One date/time field
  - One status/category field
- **For enum fields:** Include up to 5–10 sample values

### Step 6: Confidence & Fallback

Compute a confidence score. If low:

- Widen K (more tables/fields)
- Run a single query rewrite pass and union candidates
- Run multi-sampling union for schema linking
- Fall back to full SDM summary

---

## Scoring Formula & Configuration

### Reciprocal Rank Fusion (RRF)

RRF avoids brittle score normalization between retrieval systems:

```
rrf(e) = 1 / (k_rrf + rank_bm25(e)) + 1 / (k_rrf + rank_embed(e))
```

**When embeddings are unavailable:** use BM25-only scoring:

```
rrf(e) = 1 / (k_rrf + rank_bm25(e))
```

Default: `k_rrf = 60`

### Boosts (Additive)

| Boost Type         | Condition                                                   | Value             |
| ------------------ | ----------------------------------------------------------- | ----------------- |
| **Value match**    | Literal matches dimension value                             | +0.15 (cap +0.30) |
| **Type match**     | Date hint + time_dimension, or numeric comparison + fact    | +0.05             |
| **Verified query** | Entity in top verified query's referenced set (signal only) | +0.20             |

**Final entity score:**

```
score_entity(e) = rrf(e) + boost_value(e) + boost_type(e) + boost_vq(e)
```

### Table Score Aggregation

```
score_table(T) =
    0.35 * score_table_card(T)
  + 0.45 * max(score_entity(f) for f in fields(T))
  + 0.20 * max(score_entity(m) for m in metrics(T))
  + 0.25 * is_in_top_verified_query(T)  # signal only, not execution
```

Weights prioritize field-level evidence (0.45) over table-level (0.35), ensuring high-quality field matches pull in their tables even if the table name itself doesn't match well.

### Confidence Estimation

```
confidence = (conf_margin × 0.5) + (conf_connect × 0.3) + (conf_coverage × 0.2)
```

Where:

- `conf_margin = sigmoid((score_top - score_kth) / 0.25)`
- `conf_connect = clamp(1.0 - 0.15 * bridges, 0, 1)`
- `conf_coverage = matched_values / total_literals` (0 if no literals)

### Default Configuration

| Parameter                  |  Default | Description                                |
| -------------------------- | -------: | ------------------------------------------ |
| `N_tables_retrieve`        |       20 | Stage 1 table candidates                   |
| `N_fields_retrieve`        |       80 | Global field candidates                    |
| `N_metrics_retrieve`       |       25 | Global metric candidates                   |
| `N_vq_retrieve`            |        5 | Verified query candidates                  |
| `K_tables`                 |        8 | Selected tables (before closure)           |
| `K_fields_per_table`       |       12 | Fields per table (incl. join keys)         |
| `k_rrf`                    |       60 | RRF smoothing constant                     |
| `confidence_low`           |     0.60 | Trigger rewrite/widen                      |
| `confidence_very_low`      |     0.45 | Fallback to full SDM                       |
| `rewrite_enabled`          |     true | Query rewrite on low confidence            |
| `multisample_enabled`      |     true | Multi-sample union on low confidence       |
| `embeddings_enabled`       |     true | Enable vector retrieval when available     |
| `storage_mode`             |     auto | Auto-detect postgres vs sqlite             |
| `vq_anchoring_enabled`     |    false | Boost verified-query elements when enabled |
| `max_prompt_schema_tokens` | budgeted | Hard ceiling on schema tokens              |

---

## Implementation Specifics

This section defines schema-linking-specific implementation details. For general engineering standards (logging patterns, error handling, type safety, async patterns), see `docs/engineering-standards/engineering-standards.md`.

---

### Exception Types

Define these specific exceptions for the schema linking pipeline:

```python
class SchemaLinkingError(Exception):
    """Base exception for schema linking pipeline failures."""
    pass

class SDMVersionMismatchError(SchemaLinkingError):
    """Raised when artifact version doesn't match requested SDM version."""
    pass

class LinkingTimeoutError(SchemaLinkingError):
    """Raised when linking operation exceeds timeout."""
    pass

class ArtifactGenerationError(SchemaLinkingError):
    """Raised when card/graph generation fails."""
    pass

class EmbeddingAPIError(SchemaLinkingError):
    """Raised when embedding model API call fails."""
    pass
```

---

### Domain Models

Use Pydantic models for all schema linking data structures:

```python
from pydantic import BaseModel, Field
from typing import Literal

class LinkingConfig(BaseModel):
    """Configuration for schema linking pipeline."""
    N_tables_retrieve: int = Field(default=20, ge=1, le=100)
    N_fields_retrieve: int = Field(default=80, ge=1, le=500)
    K_tables: int = Field(default=8, ge=1, le=50)
    K_fields_per_table: int = Field(default=12, ge=1, le=100)
    k_rrf: int = Field(default=60, ge=10, le=200)
    confidence_low: float = Field(default=0.60, ge=0, le=1)
    confidence_very_low: float = Field(default=0.45, ge=0, le=1)
    timeout_seconds: float = Field(default=5.0, ge=1, le=30)

class RoutingCard(BaseModel):
    """A retrieval card for schema linking."""
    id: str = Field(..., description="Unique card ID: table:sdm123:customers")
    sdm_id: str
    sdm_version: str
    card_type: Literal["table", "field", "metric", "relationship", "verified_query"]
    text_content: str = Field(..., min_length=1)
    metadata: dict[str, Any]

class LinkingRequest(BaseModel):
    """Request to link a question to schema elements."""
    nl_question: str = Field(..., min_length=1, max_length=10000)
    sdm_id: str
    sdm_version: str
    config: LinkingConfig | None = None
    force_full_schema: bool = Field(default=False)

class LinkingResult(BaseModel):
    """Result of schema linking operation."""
    linked_tables: list[str] = Field(default_factory=list)
    linked_fields: list[str] = Field(default_factory=list)
    linked_metrics: list[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0, le=1)
    fallback_triggered: bool = Field(default=False)
    fallback_reason: str | None = None
    duration_ms: float = Field(..., ge=0)
```

---

### Operations to Log

Log these key operations using structured logging (see engineering standards for format):

| Operation          | Event Name                 | Context Fields                                                                                             |
| ------------------ | -------------------------- | ---------------------------------------------------------------------------------------------------------- |
| Card generation    | `sdm_cards_generated`      | sdm_id, sdm_version, card_count, duration_ms                                                               |
| Schema linking     | `schema_linking_completed` | sdm_id, sdm_version, linked_tables_count, linked_fields_count, confidence, fallback_triggered, duration_ms |
| Fallback triggered | `schema_linking_fallback`  | sdm_id, reason, confidence, original_k, widened_k                                                          |
| Artifact refresh   | `sdm_artifacts_refreshed`  | sdm_id, old_version, new_version, duration_ms                                                              |
| Embedding API call | `embedding_api_called`     | batch_size, model, duration_ms                                                                             |

---

### Timeout Values

| Operation                     | Timeout | Rationale                             |
| ----------------------------- | ------- | ------------------------------------- |
| Schema linking (sync)         | 5s      | Fast retrieval + scoring              |
| Card generation               | 30s     | Iterates over SDM (potentially large) |
| Embedding API call            | 30s     | External API, batch processing        |
| Artifact refresh (background) | 5min    | Large SDMs with many cards            |

---

### Transactional Operations

These operations must be wrapped in transactions for ACID compliance:

```python
# Artifact persistence must be atomic
async with storage.transaction():
    await storage.save_cards(cards, embeddings)
    await storage.save_graph(graph)
    # If either fails, both roll back
```

---

## Migration Strategy

### Phase 1: Foundation

- [ ] Identify SDM fields used for relationships
- [ ] Define graph schema and storage format
- [ ] Define card schema and artifact storage format (JSON)
- [ ] Create baseline linker configuration (defaults)
- [ ] Define schema metadata enrichment sources (types, comments, samples)
- [ ] Create database migration for `sdm_routing_cards` and `sdm_schema_graph` tables
- [ ] Ensure all new tables follow `sdm_*` naming convention (see Implementation Architecture section)

### Phase 2: Linking MVP

- [ ] Build graph generator + card generator
- [ ] Build BM25 + embedding indexes
- [ ] Implement two-stage baseline linker
- [ ] Implement deterministic refinement (FK paths + keys)
- [ ] Integrate with prompt builder (pruning) + fallback

### Phase 3: Validation

**Prerequisites:**

- Phase 2 baseline linker working
- Test data prepared (see Test Data Requirements below)
- Metrics infrastructure in place

**Tasks:**

- [ ] Measure linking recall/precision on known queries
- [ ] Measure NL2SQL latency and EX accuracy
- [ ] Tune k + thresholds (see Tuning Playbook below)
- [ ] Compare minimal vs enriched schema strategies
- [ ] Validate on held-out test set

---

#### Test Data Requirements

To properly validate linking quality, you need a diverse test set with known gold schemas.

> **See also:** [Schema Linking Testing Guide](./schema-linking-testing-guide.md) for complete validation procedures using BIRD benchmark.

**Minimum Requirements:**

- **100+ queries** with gold SQL and known schema elements
- **Stratified by difficulty:**
  - 40% simple (single table, < 3 columns)
  - 40% moderate (2 tables, joins, basic aggregation)
  - 20% complex (3+ tables, multiple joins, nested aggregations, subqueries)
- **Stratified by domain:**
  - Cover all major table groups in your SDM
  - Include both common and rare tables
  - Mix fact tables and dimension tables

**Data Sources (in priority order):**

1. **Existing verified queries** (expand parameters)

   - Take each verified query
   - Generate 3-5 variants with different filters/parameters
   - Manually label required tables/fields
   - Example: "What were sales in Q1?" → "What were sales in Q2?", "What were sales by region in Q1?"

2. **Synthetic generation** (template-based)

   - Create templates for common query patterns
   - Fill with tables/columns from SDM
   - Generate SQL automatically
   - Example template: "What is the [metric] for [dimension] in [time_period]?"

3. **User query logs** (if available)
   - Export historical queries (anonymized)
   - Manually label 100+ with gold schemas
   - Use execution success as quality signal
   - Prioritize queries that failed or had high latency

**Gold Schema Annotation:**

For each query, annotate:

```json
{
  "nl_question": "What were total sales by region last quarter?",
  "gold_tables": ["sales_fact", "regions", "time_dim"],
  "gold_fields": ["sales_fact.amount", "sales_fact.region_id", "regions.region_name", "time_dim.quarter"],
  "gold_relationships": ["sales_fact→regions", "sales_fact→time_dim"],
  "difficulty": "moderate",
  "gold_sql": "SELECT r.region_name, SUM(s.amount) FROM sales_fact s JOIN regions r ON s.region_id = r.id JOIN time_dim t ON s.date_id = t.id WHERE t.quarter = 'Q4-2025' GROUP BY r.region_name"
}
```

**Storage:** Store test data in `quality/schema_linking_test_data/` as YAML or JSON files.

---

#### Tuning Playbook

Once you have test data, tune the linker parameters to maximize quality.

**Step 1: Establish Baseline**

Run the linker with default configuration (from document):

- `K_tables = 8`
- `K_fields_per_table = 12`
- `k_rrf = 60`
- `confidence_low = 0.60`
- `confidence_very_low = 0.45`

Measure baseline metrics:

- Linking recall@10 (% queries where all gold elements appear in top-10)
- Linking precision@10 (% selected elements that are in gold set)
- NL2SQL EX accuracy (% queries that execute correctly)
- Prompt token reduction (vs full schema)
- Latency (end-to-end)

**Step 2: Grid Search Parameters**

| Parameter             | Search Range             | Step | Metric to Optimize          |
| --------------------- | ------------------------ | ---- | --------------------------- |
| `K_tables`            | [6, 8, 10, 12]           | 2    | Recall@10 (tables)          |
| `K_fields_per_table`  | [8, 10, 12, 15]          | 2-3  | Recall@10 (fields)          |
| `k_rrf`               | [40, 60, 80]             | 20   | F1@10 (precision vs recall) |
| `confidence_low`      | [0.55, 0.60, 0.65, 0.70] | 0.05 | Fallback rate vs accuracy   |
| `confidence_very_low` | [0.40, 0.45, 0.50]       | 0.05 | Emergency fallback rate     |

**Step 3: Optimize for F1**

For each configuration:

1. Run linker on dev set (80% of test data)
2. Compute metrics:
   - Recall@10 = (queries with all gold elements) / (total queries)
   - Precision@10 = (gold elements in linked) / (total linked elements)
   - F1@10 = 2 × (Precision × Recall) / (Precision + Recall)
3. Track NL2SQL EX accuracy (does linked schema enable correct SQL?)
4. Track prompt token reduction

**Step 4: Select Configuration**

Choose configuration that:

- Maximizes **F1@10** (primary metric)
- Achieves **Recall@10 > 90%** (hard constraint)
- Achieves **Precision@10 > 60%** (hard constraint)
- Keeps **fallback rate < 10%** (operational constraint)
- Improves **EX accuracy by 5-15%** vs baseline (business goal)

**Step 5: Validate on Test Set**

- Run selected configuration on held-out test set (20% of test data)
- Confirm metrics hold
- If significant degradation, expand dev set and re-tune

**Step 6: Document Configuration**

Update default configuration in code and documentation with tuned values.

Example:

```python
# Tuned configuration (validated 2026-01-22 on 120-query test set)
DEFAULT_LINKING_CONFIG = {
    "N_tables_retrieve": 20,
    "N_fields_retrieve": 80,
    "K_tables": 10,  # Tuned from 8 (improved recall)
    "K_fields_per_table": 12,
    "k_rrf": 60,
    "confidence_low": 0.65,  # Tuned from 0.60 (reduced false positives)
    "confidence_very_low": 0.45,
}
```

**Tools:**

- Use `pytest` with parametrize for grid search
- Log all configurations and metrics to database or CSV
- Use `matplotlib`/`seaborn` to visualize recall/precision trade-offs

**Expected Effort:** 2-3 days for proper tuning with 100-query dev set.

---

### Phase 4: Enhancements

- [ ] Add verified-query anchoring + skeleton demo selection
- [ ] Add matched-value retrieval + value index (consider: `sdm_value_index` table)
- [ ] Add SQL skeleton index (consider: `sdm_skeleton_index` table)
- [ ] Add low-confidence rewrite
- [ ] Add optional multi-sample union and/or decomposition
- [ ] Add A/B testing support

**Note:** If adding new tables for value indexes or skeleton indexes, follow the `sdm_*` naming convention:

- `sdm_value_index` for matched value retrieval
- `sdm_skeleton_index` for SQL skeleton similarity
- All indexes: `idx_<table_name>_<columns>`

### Phase 5: Guardrails and Optimization

- [ ] Implement extractive selection constraint (H-1)
- [ ] Add repair loop for execution errors (H-2)
- [ ] Train/deploy complexity classifier (H-3)
- [ ] Add SLM reranker over retrieval candidates (H-4)
- [ ] Train learned confidence calibration model (H-5)
- [ ] Measure cost/latency savings from SLM gating

---

## Rollback Strategy

In case linking introduces regressions, we need a safe rollback path.

### Feature Flag (Required for Phase 2)

Add a feature flag to enable/disable linking:

```python
# Feature flag
ENABLE_SCHEMA_LINKING = os.getenv("ENABLE_SCHEMA_LINKING", "false").lower() == "true"

# In NL2SQL pipeline
if ENABLE_SCHEMA_LINKING:
    linked_schema = schema_linker.link(nl_question, sdm)
    prompt = build_prompt_with_linked_schema(linked_schema)
else:
    # Fallback to current behavior (full schema)
    prompt = build_prompt_with_full_schema(sdm)
```

**Deployment Plan:**

1. Deploy with flag OFF (no behavior change)
2. Enable for 5% of traffic (canary)
3. Monitor metrics (latency, accuracy, errors)
4. If good: gradually increase to 100%
5. If bad: disable flag immediately (< 1 minute rollback)

### Per-SDM Override (Required for Phase 2)

Allow disabling linking for specific SDMs:

```yaml
# In SDM metadata
metadata:
  disable_schema_linking: true # Force full-schema prompting for this SDM
  reason: 'SDM too small (5 tables), linking overhead not worth it'
```

### Per-Query Override (Required for Phase 2)

Allow users to bypass linking:

```python
# API parameter
POST /api/nl2sql
{
  "question": "What were sales last quarter?",
  "sdm_id": "sales_sdm",
  "force_full_schema": true  # Optional: bypass linking
}
```

### Emergency Rollback Checklist

If linking causes production issues:

1. **Immediate (< 1 min):**

   - [ ] Set `ENABLE_SCHEMA_LINKING=false` in environment
   - [ ] Restart service (or use hot reload if supported)
   - [ ] Confirm traffic reverted to full-schema mode

2. **Within 1 hour:**

   - [ ] Analyze logs to identify failure mode
   - [ ] Identify affected queries/SDMs
   - [ ] Create GitHub issue with reproduction steps

3. **Within 1 day:**
   - [ ] Fix root cause in dev environment
   - [ ] Add regression test
   - [ ] Re-deploy with fix
   - [ ] Re-enable linking with canary rollout

### Monitoring Alerts (Required for Phase 3)

Set up alerts to catch issues early:

| Alert                  | Condition                           | Action                                                   |
| ---------------------- | ----------------------------------- | -------------------------------------------------------- |
| **High fallback rate** | Fallback rate > 20% for 10+ minutes | Investigate linking quality; may need to tune thresholds |
| **Linking errors**     | Linking failure rate > 5%           | Check logs; may have schema validation issues            |
| **Latency spike**      | p95 latency increases > 30%         | Linking may be slow; check embedding API or DB           |
| **Accuracy drop**      | EX accuracy drops > 5% absolute     | Linking may be pruning needed schema; consider rollback  |

---

## Appendix: Semi-Structured / JSON Support

If your SDM needs to cover JSON/semi-structured fields (Snowflake VARIANT, Postgres JSONB, etc.), do **not** force nested JSON metadata into the Snowflake semantic YAML.

**Recommended approach:**

1. Keep SDM as the source of truth (YAML or JSON)
2. Add an extension model for semi-structured fields + array flattening
3. Generate routing artifacts (cards) from that extension

This keeps the core SDM clean while enabling rich linking over complex nested structures.

**Example:**

```yaml
# SDM table with semi-structured field
tables:
  - name: events
    columns:
      - name: event_data
        type: VARIANT # Snowflake semi-structured type
        description: 'JSON payload with event details'
```

**Extension model (for linking):**

```json
{
  "table": "events",
  "field": "event_data",
  "json_paths": [
    { "path": "$.user_id", "type": "string", "description": "User identifier" },
    { "path": "$.action", "type": "string", "description": "Action performed" },
    { "path": "$.timestamp", "type": "timestamp", "description": "Event time" }
  ]
}
```

**Generated cards:**

- `field:sdm123:events:event_data.user_id` (linkable)
- `field:sdm123:events:event_data.action` (linkable)
- `field:sdm123:events:event_data.timestamp` (linkable)

This approach allows linking to nested fields without polluting the core SDM specification.
