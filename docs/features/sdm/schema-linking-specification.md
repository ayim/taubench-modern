# Feature Specification: Schema Linking and Pruning for SDM-Driven NL2SQL

**Status:** Proposed  
**Author:** Agent Platform Team  
**Date:** 2026-01-22  
**Architecture:** See [schema-linking-architecture.md](./schema-linking-architecture.md) for implementation details

---

## Executive Summary

This document specifies a **schema linking and pruning layer** for the NL2SQL pipeline. The goal is to reduce prompt size, improve SQL generation accuracy, and lower latency by selecting only the relevant portions of a Semantic Data Model (SDM) for each natural language question.

**Key Capabilities:**

- **Two-stage linking (tables → columns):** First identify relevant tables (high recall), then select columns within those tables (high precision)
- **Routing artifacts:** Generate retrieval-optimized "cards" from the SDM for efficient search
- **Deterministic refinement:** Enforce joinability via FK-path closure, FK-key closure, and table-membership closure
- **Verified query signals:** Surface similar verified queries to guide routing; outer tools decide execution
- **Adaptive fallback:** Widen schema selection or rewrite queries when confidence is low
- **Concrete scoring:** Ship with tuned defaults that work out-of-the-box
- **Guardrails:** Extractive selection prevents hallucinated schema names; repair loop recovers from execution errors
- **SLM optimization:** Lightweight classifiers gate expensive operations and rerank candidates cheaply
- **Capability gating:** Embedding and vector features enabled only when configured

**Expected Impact:**

| Metric                   | Target                         |
| ------------------------ | ------------------------------ |
| Prompt token reduction   | 30–60% fewer tokens            |
| Latency reduction        | 20–40% faster end-to-end       |
| NL2SQL accuracy (EX)     | 5–15% improvement              |
| Schema linking recall@10 | > 90% of needed elements found |

---

## Table of Contents

1. [Problem Statement](#problem-statement)
2. [Solution Overview](#solution-overview)
3. [Requirements](#requirements)
4. [Epics](#epics)
5. [User Stories](#user-stories)
6. [Breaking Changes](#breaking-changes)
7. [Success Metrics](#success-metrics)
8. [References](#references)

---

## Problem Statement

### 1. NL2SQL Context Size

The system currently passes a full SDM (or large subtrees) into LLM prompts. As SDMs grow, this creates:

- **Long prompts:** Higher latency and cost
- **Increased ambiguity:** The LLM struggles to identify relevant schema elements
- **Lower recall:** Important tables and columns get buried in noise

### 2. No Dedicated Schema Linking

Selection of tables and columns is implicit or rule-based. There is no explicit schema linking layer that:

- Chooses relevant tables for a question
- Considers relationships (joins) between tables
- Produces a minimal, connected schema slice for prompt generation

### 3. Limited Schema Linking Evidence

Prompts lack consistent schema metadata (data types, PK/FK flags, sample values) and matched values from the database, reducing the LLM's ability to link natural language terms to schema elements.

---

## Solution Overview

### Architecture: SDM-Derived Schema Linking

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  NL Question    │────▶│  Schema Linker   │────▶│  Pruned Schema  │
└─────────────────┘     │                  │     │  + Evidence     │
                        │  - Card retrieval│     └────────┬────────┘
                        │  - Scoring       │              │
                        │  - Refinement    │              ▼
                        └──────────────────┘     ┌─────────────────┐
                                                 │  SQL Generator  │
                                                 │  (LLM)          │
                                                 └────────┬────────┘
                                                          │
                                                          ▼
                                                 ┌─────────────────┐
                                                 │  Physical SQL   │
                                                 └─────────────────┘
```

**Pipeline Steps:**

1. **Build routing artifacts** from the SDM (tables, fields, relationships → cards + indexes)
2. **Link** the NL question to a minimal, connected sub-schema using hybrid retrieval
3. **Enrich** the linked schema with metadata and matched values (bounded)
4. **Prompt** the LLM with only the linked schema
5. **Execute** physical SQL directly (consistent with physical-first SDM approach)

**Orchestration boundary:** Schema linking provides a focused schema slice and evidence to improve SQL generation. It does not block iterative LLM attempts or tool-driven workflows; the outer agent can still retry, expand, or defer to verified-query tools when available.

### Key Design Principles

| Principle                     | Rationale                                                       |
| ----------------------------- | --------------------------------------------------------------- |
| **Two-stage linking**         | Scales to large SDMs (1000+ tables) by filtering tables first   |
| **Separate card artifacts**   | Keeps SDM as source of truth; cards optimized for retrieval     |
| **Deterministic refinement**  | Guarantees joinable, executable schema slices                   |
| **Verified query anchoring**  | Surfaces proven patterns; anchoring is optional and tool-driven |
| **Confidence-based fallback** | Graceful degradation when linking is uncertain                  |
| **Capability-gated features** | Enable embeddings/vector search only when available             |

---

## Requirements

| Req ID     | Requirement                                                                                   |
| ---------- | --------------------------------------------------------------------------------------------- |
| **REQ-1**  | The system shall build a schema graph from each SDM version                                   |
| **REQ-2**  | The schema graph shall include tables, fields, and relationships (FK/joinability)             |
| **REQ-3**  | The linker shall return a minimal, connected sub-schema for each NL question                  |
| **REQ-4**  | Prompts shall include only linked tables/fields unless override is requested                  |
| **REQ-5**  | The linker shall support SDMs sourced from files, databases, and mixed sources                |
| **REQ-6**  | Routing artifacts (cards + indexes) shall be persisted and versioned per SDM                  |
| **REQ-7**  | Linking accuracy and latency shall be observable and logged                                   |
| **REQ-8**  | The system shall have a fallback path when linking confidence is low                          |
| **REQ-9**  | Linked schema shall include data types and PK/FK metadata when available                      |
| **REQ-10** | The linker shall support matched-value retrieval for NL questions                             |
| **REQ-11** | The linker shall support optional schema enrichment beyond the minimal set                    |
| **REQ-12** | The system shall support question decomposition for complex queries (optional)                |
| **REQ-13** | The linker shall support two-stage linking (tables → fields) for large SDMs                   |
| **REQ-14** | The linker shall apply deterministic refinement: table membership + FK path + FK key closure  |
| **REQ-15** | The linker shall support conditional query rewriting on low confidence                        |
| **REQ-16** | The linker shall support conditional multi-sampling union on low confidence                   |
| **REQ-17** | The linker shall surface verified-query candidates and optionally anchor linking when enabled |
| **REQ-18** | The LLM shall select schema elements extractively from candidate IDs (no hallucinated names)  |
| **REQ-19** | The system shall attempt one repair pass on SQL execution errors before failing               |
| **REQ-20** | The system shall use a complexity classifier to gate expensive operations                     |
| **REQ-21** | The system shall support SLM-based reranking and learned confidence calibration (optional)    |
| **REQ-22** | The system shall support a SQLite-only storage path with reduced capabilities                 |
| **REQ-23** | Embedding model selection shall be configurable and optional at runtime                       |
| **REQ-24** | The linker shall fall back to BM25-only retrieval when embeddings are unavailable             |

---

## Epics

### Epic A: Build and Persist Schema Graphs + Routing Artifacts

**Description:** Derive a schema graph and retrieval artifacts from SDM metadata and persist them per SDM version.

**Research Foundation:** This epic implements the "componentized semantic units" approach from RASL, which indexes schema elements (tables, fields, metadata) as separate retrievable artifacts for multi-stage retrieval. See [References](#references) for full citations.

**Acceptance Criteria:**

- [ ] Graph nodes include tables and fields
- [ ] Graph edges include relationship links from SDM
- [ ] Card store generated for: tables, fields, metrics, relationships, verified queries
- [ ] BM25 + embedding index built over card store
- [ ] Artifacts stored per SDM version with checksums
- [ ] Artifacts can be loaded quickly at runtime

---

### Epic B: Schema Linking Engine

**Description:** Implement linking to select relevant tables/fields for each NL question.

**Research Foundation:** This epic implements two-stage linking with relevance calibration (RASL), multi-round retrieval with query rewriting (LinkAlign), and deterministic refinement rules including FK-path closure and FK-key closure (IBM schema-linking paper). See [References](#references) for full citations.

**Acceptance Criteria:**

- [ ] Implements two-stage linking (tables → fields)
- [ ] Uses hybrid retrieval (BM25 + embeddings) with RRF fusion
- [ ] Applies deterministic refinement (membership, FK path, FK keys)
- [ ] Returns:
  - [ ] Linked schema slice (bounded)
  - [ ] Evidence and highlights (for debugging)
- [ ] Confidence score returned with each result
- [ ] Default configuration shipped with overrides

---

### Epic C: Prompt Pruning and NL2SQL Integration

**Description:** Use linked schema slices for prompt generation and SQL output.

**Acceptance Criteria:**

- [ ] Prompt includes only linked schema by default
- [ ] Prompt instructs physical SQL usage (or SDM IR if Epic F used)
- [ ] Fallback to full SDM or expanded schema when confidence is low
- [ ] Logging includes linked schema identifiers, confidence, and fallback reason

---

### Epic D: Evaluation and Observability

**Description:** Measure linking quality and impact on NL2SQL.

**Acceptance Criteria:**

- [ ] Metrics: linking recall (perfect-recall style), precision, prompt token count, latency
- [ ] End-to-end execution accuracy (EX) tracked on test set
- [ ] Error analysis reports:
  - Missing tables
  - Missing join keys / junction tables
  - Wrong join path
  - Missed columns / wrong filters
- [ ] Dashboard breakouts by query difficulty (simple/moderate/complex)

---

### Epic E: Operations and Maintenance

**Description:** Ensure routing artifacts are refreshed on SDM updates.

**Acceptance Criteria:**

- [ ] Artifacts regenerated on SDM update
- [ ] Graph + card store version stored with SDM version ID
- [ ] Rollback to previous artifact set on failure
- [ ] CI check verifies artifact generation determinism

---

### Epic F: Semantic-Layer Inbound Query Translation (Optional)

**Description:** Allow the LLM to generate semantic-layer (SDM) queries that are compiled into physical SQL.

**Acceptance Criteria:**

- [ ] Define an inbound query schema that references SDM measures/dimensions
- [ ] Add a compiler that translates inbound queries to physical SQL
- [ ] Ensure joins and KPI logic are resolved in the compiler (not LLM)
- [ ] Add retry loop for invalid inbound queries or compilation errors

---

### Epic G: Schema Linking Enhancements

**Description:** Improve linking quality using best practices: matched values, demonstration retrieval, query rewrite, self-consistency, decomposition.

**Research Foundation:** This epic combines multiple research techniques: SQL skeleton-based demonstration selection (DAIL-SQL), conditional decomposition for complex questions (DIN-SQL), test-time self-consistency and merge/revise correction (CSC-SQL), and router-generator decoupling with relation-aware retrieval (DBCopilot). See [References](#references) for full citations.

**Acceptance Criteria:**

- [ ] Matched value retrieval pipeline and scoring boost
- [ ] Verified query retrieval + SQL skeleton demo selection
- [ ] Optional query rewrite pass on low confidence
- [ ] Optional multi-sample union on low confidence
- [ ] Optional question decomposition path for complex queries
- [ ] Schema enrichment bounded and measurable

---

### Epic H: Guardrails and Optimization

**Description:** Add lightweight classifiers and guardrails to reduce cost, improve robustness, and prevent hallucinated schema references.

**Research Foundation:** This epic implements hallucination mitigation through pre-generation alignment (TA-SQL) and execution feedback loops with question rewriting (DART-SQL). See [References](#references) for full citations.

**Acceptance Criteria:**

- [ ] LLM schema selection is extractive (selects from candidate IDs, cannot invent names)
- [ ] Execution errors trigger a single repair attempt with error context
- [ ] Complexity classifier gates expensive operations (decomposition, rewrite, multi-sample)
- [ ] SLM reranker improves precision over retrieval candidates
- [ ] Confidence prediction is learnable from routing features

---

## User Stories

### Epic A: Build and Persist Schema Graphs + Routing Artifacts

**Story A-1: Derive Graph from SDM**

> As a developer, I want to build a schema graph from the SDM so linking can use SDM relationships directly.

**Context:**
The schema graph transforms the SDM's tables, columns, and relationships into a structure that answers two critical questions during linking: (1) "Which tables can be joined together?" and (2) "What is the shortest path of joins between two tables?" Without this graph, the linker cannot determine if a set of selected tables forms a valid, connected schema.

**Scope:**

_What this story produces:_

- A graph where every SDM table is a node
- A graph where every SDM column is a node, connected to its parent table
- A graph where every SDM relationship becomes an edge between two table nodes, with the join column pairs recorded on the edge
- Enough information on each node/edge to reconstruct which SDM element it came from

_What the graph must support:_

- Given two tables, find whether they can be joined (directly or through intermediate tables)
- Given two tables, find the shortest join path between them (for FK-path closure)
- Given a table, find all tables it can join to (for relationship expansion)

**Acceptance Criteria:**

- [ ] All SDM tables and columns are represented as nodes, with fields linked to their parent tables
- [ ] All SDM relationships are represented as edges, capturing join keys and cardinality
- [ ] The graph supports bidirectional traversal for path-finding algorithms
- [ ] Edge cases are handled gracefully: self-joins, composite keys, isolated tables, and malformed references
- [ ] The graph can be serialized to and loaded from storage without data loss

**Performance Target:** Graph loading completes in < 100ms for a 500-table SDM

**Edge Cases:**

- Self-referential relationships (e.g., employee → manager) create valid edges
- Composite foreign keys (multiple column pairs) are represented on a single edge
- Tables with no relationships are included as isolated nodes (not omitted)
- Malformed relationship references log warnings but do not fail graph generation

**Dependencies:**

- SDM definition must be fully parsed and validated before graph generation
- Graph data structure defined in architecture document

---

**Story A-2: Version and Cache Artifacts**

> As an operator, I want routing artifacts versioned per SDM so linking uses the correct schema.

**Context:**
SDMs evolve over time (new tables, renamed columns, changed relationships). The linker must always use artifacts that match the current SDM version. Stale artifacts cause linking failures or incorrect SQL. This story ensures artifacts are versioned, cached, and invalidated correctly.

**Scope:**

_What this story produces:_

- A versioning scheme that ties each artifact set (graph + cards + indexes) to a specific SDM version
- A caching layer that stores computed artifacts to avoid regeneration on every request
- An invalidation mechanism that detects SDM changes and triggers re-generation

_What the system must support:_

- On service startup, load cached artifacts if they match the current SDM version
- On SDM update, detect the version change and schedule artifact regeneration
- During regeneration, continue serving requests with old artifacts until new ones are ready

**Acceptance Criteria:**

- [ ] Every artifact set is tagged with the SDM ID and version that produced it
- [ ] Cached artifacts are loaded at startup without recomputation if the version matches
- [ ] SDM version changes trigger automatic artifact invalidation and regeneration
- [ ] Requests during regeneration continue to work (graceful transition)
- [ ] Artifact version mismatches are logged and surfaced as errors

**Performance Target:** Artifact loading from cache completes in < 500ms for a 500-table SDM

**Dependencies:**

- Story A-1 (graph generation) and A-3 (card generation) must be complete
- SDM must expose a version identifier that changes when content changes

---

**Story A-3: Generate SDM Cards**

> As a developer, I want to generate retrieval cards from the SDM so linking does not require maintaining JSON inside YAML.

**Context:**
The linker uses keyword search (BM25) and semantic search (embeddings) to find relevant schema elements. These searches need documents optimized for retrieval—not the raw SDM YAML. Cards are short, search-optimized documents generated from the SDM, one per table/field/metric/relationship/verified-query.

**Scope:**

_What this story produces:_

- A card for every table in the SDM (containing name, description, synonyms)
- A card for every field in the SDM (containing name, type, description, sample values)
- A card for every metric in the SDM (containing name, description, expression keywords)
- A card for every relationship in the SDM (containing table names, join keys)
- A card for every verified query in the SDM (containing NLQ, SQL skeleton, referenced tables)

_What each card must include:_

- A stable, unique ID that can be traced back to the SDM element (e.g., `table:sdm123:customers`)
- Text content suitable for keyword and semantic search
- Metadata for scoring boosts (e.g., is_primary_key, cardinality)

**Acceptance Criteria:**

- [ ] Cards are generated for all five element types: table, field, metric, relationship, verified-query
- [ ] Each card has a stable ID with clear provenance to its SDM source element
- [ ] Card text content is optimized for search (includes name, description, synonyms, sample values)
- [ ] Cards are serialized in a format suitable for indexing (JSON)
- [ ] Card generation is deterministic—same SDM produces identical cards

**Performance Target:** Card generation completes in < 30s for a 500-table SDM with 5000 fields

**Edge Cases:**

- Fields with no description use name only
- Metrics with complex expressions include tokenized expression keywords
- Verified queries without SQL have skeleton marked as empty

**Dependencies:**

- SDM definition must be fully parsed
- Card schema defined in architecture document

---

### Epic B: Schema Linking Engine

**Story B-1: Baseline Retrieval Linker**

> As a system, I want a baseline linking implementation so we get immediate wins without ML training.

**Context:**
Before investing in ML-based linking, we need a baseline that works out-of-the-box using standard retrieval techniques. This baseline combines keyword matching (BM25) and semantic similarity (embeddings) to rank schema elements by relevance to the user's question. It serves as both the production default and the benchmark for future improvements.

**Scope:**

_What this story produces:_

- A linker that takes a natural language question and returns relevant tables, fields, and metrics
- Ranking based on two signals: keyword overlap (BM25) and meaning similarity (embeddings)
- Relationship expansion that pulls in tables connected to high-scoring tables

_How ranking works:_

- Query the card indexes (BM25 + embedding) for each card type
- Combine scores using Reciprocal Rank Fusion (RRF) to avoid normalization issues
- Expand results by including tables related to top-scoring elements

**Acceptance Criteria:**

- [ ] Linker queries both BM25 and embedding indexes and fuses results using RRF
- [ ] Linker expands results to include tables related to high-scoring fields/metrics
- [ ] Linker returns a ranked list of tables, fields, and metrics with scores
- [ ] Linker returns a confidence score indicating how certain the linking is
- [ ] Linker completes within latency budget (see performance target)

**Performance Target:** Linking completes in < 500ms for a 500-table SDM (excluding embedding API latency)

**Dependencies:**

- Story A-3 (cards generated and indexed)
- BM25 and embedding indexes built and queryable

---

**Story B-2: Learned Linking (Optional)**

> As a system, I want to support a learned linker so linking improves over time.

**Context:**
The baseline linker uses general-purpose retrieval. A learned linker can be trained on domain-specific data to better understand which schema elements are relevant for particular question patterns. This is optional and only pursued if baseline quality is insufficient.

**Scope:**

_What this story produces:_

- A training pipeline that accepts labeled question → schema element pairs
- A model that scores schema elements given a question (can replace or augment baseline)
- Integration with the schema graph to constrain predictions to valid elements

_What training data looks like:_

- Questions paired with the gold set of tables/fields needed to answer them
- Can be generated synthetically from verified queries or labeled manually

**Acceptance Criteria:**

- [ ] Training pipeline accepts labeled data in a defined format
- [ ] Trained model can score schema elements given a question
- [ ] Model predictions are constrained to valid schema elements (no hallucination)
- [ ] Learned linker can be benchmarked against baseline on the same test set
- [ ] Model can be updated/retrained as new labeled data becomes available

**Performance Target:** Learned linker inference adds < 100ms to baseline latency

**Dependencies:**

- Story B-1 (baseline linker for comparison)
- Labeled training data (at least 500 question-schema pairs)

---

**Story B-3: Two-Stage Linker**

> As a system, I want to link tables first and then fields within linked tables so linking scales to large SDMs.

**Context:**
For large SDMs (hundreds or thousands of tables), scoring every field globally is expensive and noisy. Two-stage linking first selects a small set of relevant tables (high recall), then selects fields only within those tables (high precision). This narrows the search space and improves both speed and accuracy.

**Scope:**

_What this story produces:_

- Stage 1: Select top-K tables from the full SDM based on question relevance
- Stage 2: Select top-N fields/metrics only from the tables chosen in Stage 1
- Configurable K and N values to tune recall vs. precision trade-off

_Why two stages:_

- Reduces field candidate pool from thousands to hundreds
- Allows different retrieval strategies per stage (e.g., stricter thresholds for fields)
- Improves precision without sacrificing table-level recall

**Acceptance Criteria:**

- [ ] Stage 1 retrieves top-K tables with high recall (target: 95%+ of needed tables in top-K)
- [ ] Stage 2 retrieves top-N fields only from Stage 1 tables
- [ ] K and N are configurable via linker configuration
- [ ] Two-stage linking is faster than global field ranking for large SDMs
- [ ] Linking results include which stage selected each element (for debugging)

**Performance Target:** Two-stage linking is at least 2x faster than single-stage for SDMs with 1000+ fields

**Edge Cases:**

- If Stage 1 misses a needed table, Stage 2 cannot recover it (handled by refinement in B-4)
- Very small SDMs (< 50 fields) may skip Stage 1 and link globally

**Dependencies:**

- Story B-1 (baseline retrieval mechanisms)

---

**Story B-4: Deterministic Refinement**

> As a system, I want linking outputs to always be joinable and executable via deterministic refinement.

**Context:**
Retrieval-based linking often selects the "right" tables but misses the "glue"—junction tables needed to connect them, or join key columns needed to write the SQL. Deterministic refinement applies rule-based fixes after retrieval to guarantee the linked schema is connected and executable.

**Scope:**

_What this story produces:_

- FK-path closure: If two selected tables aren't directly joinable, add the intermediate tables needed to connect them
- FK-key closure: If a relationship is used, ensure both join key columns are included in the linked schema
- Table membership closure: If a field is included, ensure its parent table is also included

_What "deterministic" means:_

- Given the same linking output, refinement always produces the same result
- Refinement is idempotent—applying it twice produces the same result as applying it once
- No ML or randomness; purely rule-based graph operations

**Acceptance Criteria:**

- [ ] FK-path closure adds junction/bridge tables so all selected tables form a connected subgraph
- [ ] FK-key closure adds join key columns for every relationship between selected tables
- [ ] Table membership closure ensures every selected field's parent table is included
- [ ] Refinement is idempotent—running it multiple times produces the same output
- [ ] Refinement logs what it added (for debugging and metrics)

**Performance Target:** Refinement adds < 50ms to linking time

**Edge Cases:**

- If no path exists between two selected tables, log a warning and include both as disconnected (SQL may fail)
- Circular relationships are handled without infinite loops
- Self-joins don't duplicate the table

**Dependencies:**

- Story A-1 (schema graph for path-finding)
- Story B-1 or B-3 (raw linking output to refine)

---

### Epic C: Prompt Pruning and NL2SQL Integration

**Story C-1: Pruned Schema Prompting**

> As an LLM, I want a minimal schema slice so I can generate SQL faster and more accurately.

**Context:**
The LLM generates SQL based on the schema in its prompt. A smaller, more relevant schema means: (1) fewer tokens = lower cost and latency, (2) less noise = higher accuracy, (3) fits in context window for large SDMs. This story integrates linking output into the prompt builder.

**Scope:**

_What this story produces:_

- A prompt builder that accepts the linked schema (from Stories B-1/B-3/B-4) instead of the full SDM
- Schema serialization that includes only linked tables, fields, metrics, and necessary relationships
- Relationship information included only when joins are needed between linked tables

_What the prompt contains:_

- Table definitions for linked tables only
- Field definitions for linked fields only (including enrichment from G-1)
- Relationship definitions only for joins between linked tables
- No unlinked tables, fields, or relationships

**Acceptance Criteria:**

- [ ] Prompt contains only tables/fields/metrics selected by the linker
- [ ] Relationships are included only if both tables in the relationship are linked
- [ ] Schema slice is serialized in the same format the LLM expects (SDM YAML or equivalent)
- [ ] Prompt token count is reduced compared to full-schema prompting (target: 30-60% reduction)
- [ ] Prompt builder accepts a flag to force full-schema mode (bypass linking)

**Performance Target:** Prompt building adds < 20ms to request latency

**Dependencies:**

- Stories B-1/B-3/B-4 (linking output)
- Existing prompt builder interface (to integrate with)

---

**Story C-2: Low-Confidence Fallback**

> As a system, I want a fallback path so queries still work if linking is uncertain.

**Context:**
Linking can fail—the question may be ambiguous, use unfamiliar vocabulary, or require tables the linker didn't retrieve. When linking confidence is low, the system should gracefully degrade: try wider selection, or fall back to full schema. This prevents hard failures while preserving quality for high-confidence cases.

**Scope:**

_What this story produces:_

- A confidence threshold below which fallback is triggered
- Fallback behaviors: (1) widen K to include more tables/fields, (2) fall back to full SDM
- Logging that indicates when and why fallback occurred

_Fallback ladder:_

1. Confidence ≥ threshold: Use linked schema as-is
2. Confidence < threshold but > critical: Widen K (more tables/fields) and re-link
3. Confidence < critical: Fall back to full SDM (or summarized SDM if too large)

**Acceptance Criteria:**

- [ ] Confidence threshold is configurable (default defined in architecture doc)
- [ ] When confidence is below threshold, system widens selection or falls back to full schema
- [ ] Every fallback event is logged with: confidence score, threshold, fallback action taken
- [ ] Fallback rate is tracked as a metric (target: < 10% of queries)
- [ ] Queries that fall back still produce valid SQL (no hard failures due to linking)

**Edge Cases:**

- Very large SDMs may use summarized schema instead of full schema for fallback
- Multiple fallback attempts are capped to avoid infinite widening

**Dependencies:**

- Stories B-1/B-3 (confidence score calculation)
- Story C-1 (prompt builder supports both pruned and full schema)

---

### Epic D: Evaluation and Observability

**Story D-1: Linking Metrics**

> As a developer, I want linking metrics so I can track quality over time.

**Context:**
To improve linking, we must measure it. Key questions: Did linking include all needed schema elements? How much did we reduce the prompt? Did pruning hurt SQL accuracy? This story establishes the metrics infrastructure for ongoing quality tracking.

**Scope:**

_What this story produces:_

- Linking recall: % of queries where all gold schema elements appear in linked output
- Linking precision: % of linked elements that are actually needed
- Prompt token reduction: Token count of pruned schema vs. full schema
- End-to-end impact: NL2SQL execution accuracy (EX) with linking vs. without

_How metrics are computed:_

- Recall/precision require a test set with known gold schema elements
- Token reduction is computed on every query
- EX accuracy is tracked on a held-out test set or sampled production queries

**Acceptance Criteria:**

- [ ] Linking recall and precision are computed against a test set with gold schemas
- [ ] Prompt token count is logged for every query (pruned vs. full)
- [ ] End-to-end NL2SQL execution accuracy is tracked and compared to baseline
- [ ] Metrics are surfaced in a dashboard or report (not just raw logs)
- [ ] Metrics are broken out by query difficulty (simple/moderate/complex) if available

**Performance Target:** Metrics computation adds < 10ms per query (excluding test set evaluation)

**Dependencies:**

- Test set with gold schema annotations (see architecture doc: Test Data Requirements)
- Logging infrastructure for metrics collection

---

### Epic E: Operations and Maintenance

**Story E-1: SDM Update Hook**

> As an operator, I want routing artifacts rebuilt automatically when SDMs change.

**Context:**
SDMs are updated when business logic changes (new tables, renamed columns, updated relationships). Routing artifacts must stay in sync. Manual rebuilds are error-prone and slow. This story automates artifact regeneration when SDMs change, with safeguards to prevent service disruption.

**Scope:**

_What this story produces:_

- A hook/trigger that detects when an SDM is updated
- Automatic scheduling of artifact regeneration for the updated SDM
- Retention of old artifacts during regeneration (for rollback and continued serving)

_What happens on SDM update:_

1. Update hook fires (e.g., SDM save event, version bump)
2. System schedules background artifact regeneration
3. Old artifacts continue serving requests during regeneration
4. On success: new artifacts become active, old artifacts archived
5. On failure: old artifacts continue serving, alert raised

**Acceptance Criteria:**

- [ ] SDM updates automatically trigger artifact regeneration (no manual intervention)
- [ ] Old artifacts remain available during regeneration and for rollback
- [ ] Regeneration failures are logged, alerted, and do not break live queries
- [ ] Successful regeneration atomically swaps in new artifacts
- [ ] Artifact regeneration history is retained for debugging

**Performance Target:** Artifact regeneration completes within 5 minutes for a 500-table SDM

**Edge Cases:**

- Rapid successive SDM updates should coalesce (don't regenerate multiple times)
- If regeneration is in progress and new update arrives, queue or restart

**Dependencies:**

- Stories A-1, A-2, A-3 (artifact generation and versioning)
- SDM update event mechanism (assumed to exist)

---

### Epic F: Semantic-Layer Inbound Query Translation (Optional)

**Story F-1: Inbound Query Generation**

> As an LLM, I want to generate SDM-level queries so the system can handle joins and KPI logic.

**Context:**
Currently, the LLM generates physical SQL directly, which requires it to know join paths and KPI formulas. An alternative: the LLM generates a higher-level "inbound query" that references SDM measures/dimensions, and a compiler translates it to physical SQL. This moves join and KPI complexity out of the LLM.

**Scope:**

_What this story produces:_

- A query schema that the LLM can generate (references SDM measures, dimensions, filters—not physical tables/columns)
- Validation that catches malformed inbound queries before compilation
- Integration with the prompt builder to instruct the LLM to output inbound queries

_What an inbound query looks like:_

- Specifies measures to aggregate (e.g., "total_sales")
- Specifies dimensions to group by (e.g., "region", "quarter")
- Specifies filters (e.g., "year = 2025")
- Does NOT specify joins or physical table names

**Acceptance Criteria:**

- [ ] LLM generates inbound queries that reference SDM measures/dimensions (not physical columns)
- [ ] Inbound query schema is defined and documented
- [ ] Validation detects and rejects malformed inbound queries with clear error messages
- [ ] Prompt instructs LLM to output inbound query format (not raw SQL)
- [ ] Invalid inbound queries trigger a retry or fallback (not hard failure)

**Dependencies:**

- SDM must define measures and dimensions with clear semantics
- Story F-2 (compiler to translate inbound queries to SQL)

---

**Story F-2: Query Engine Compilation**

> As a system, I want a compiler that resolves joins and KPIs consistently.

**Context:**
The inbound query from Story F-1 is abstract—it says what to compute, not how. The compiler translates it to physical SQL by: (1) resolving measures to their SQL expressions, (2) determining join paths between required tables, (3) applying filters correctly. This ensures consistent SQL generation regardless of LLM variability.

**Scope:**

_What this story produces:_

- A compiler that takes an inbound query and produces physical SQL
- Join resolution using SDM relationships (same logic as FK-path closure in B-4)
- Measure expansion: replace measure references with their SQL expressions

_What the compiler handles:_

- Which tables are needed for the requested measures/dimensions
- How to join those tables (using SDM relationships)
- How to expand measure expressions (e.g., "total_sales" → "SUM(sales_fact.amount)")
- How to apply filters to the correct tables/columns

**Acceptance Criteria:**

- [ ] Compiler produces valid, executable physical SQL from inbound queries
- [ ] Joins are derived from SDM relationships (consistent with schema graph)
- [ ] Measures are expanded to their SQL expressions as defined in SDM
- [ ] Filters are applied to the correct physical columns
- [ ] Compilation errors (e.g., undefined measure) produce clear error messages

**Performance Target:** Compilation completes in < 50ms

**Edge Cases:**

- Inbound query requests measures from unrelated tables (compilation error)
- Circular join paths are detected and handled
- Missing measure definitions produce helpful errors

**Dependencies:**

- Story A-1 (schema graph for join path resolution)
- SDM measure definitions with SQL expressions

---

### Epic G: Schema Linking Enhancements

**Story G-1: Schema Metadata Enrichment**

> As a linker, I want schema metadata (types, PK/FK, descriptions, samples) to improve linking accuracy.

**Context:**
The linked schema isn't just a list of names—it should include metadata that helps the LLM generate correct SQL: data types (for casting), PK/FK flags (for joins), sample values (for WHERE clauses), descriptions (for understanding). This story enriches the prompt schema with this metadata.

**Scope:**

_What metadata to include:_

- Data types for every linked field (INTEGER, VARCHAR, DATE, etc.)
- Primary key flags for fields that are PKs
- Foreign key flags and targets for fields that are FKs
- Sample values for dimension fields (up to 10 values)
- Descriptions for all elements (from SDM)

_Where metadata comes from:_

- SDM definition (types, PK/FK, descriptions)
- Database profiling (sample values) or SDM annotations

**Acceptance Criteria:**

- [ ] Linked schema includes data types for all fields
- [ ] PK and FK flags are included when available in SDM
- [ ] Sample values are included for enum-like dimension fields (bounded to ~10 values)
- [ ] Descriptions from SDM are included for tables, fields, and metrics
- [ ] Metadata enrichment is bounded to avoid prompt bloat (see performance target)

**Performance Target:** Metadata enrichment adds < 10% to prompt token count vs. schema names alone

**Edge Cases:**

- Fields without types in SDM are marked as "unknown"
- Sample values are omitted if field has high cardinality (> 100 distinct values)

**Dependencies:**

- Story C-1 (prompt builder to integrate metadata)
- SDM or database profiling for sample values

---

**Story G-2: Matched Value Retrieval**

> As a linker, I want matched values from the database to reduce ambiguity.

**Context:**
Users often mention specific values in their questions ("sales in California", "orders from December"). Matching these values to columns ("California" → state_name column) provides strong evidence for which columns are relevant. This story adds value matching to the linking pipeline.

**Scope:**

_What this story produces:_

- A value index over dimension column values (e.g., all product names, all region names)
- A matching step that finds which columns contain values mentioned in the question
- A boost to columns that match user-specified values

_How value matching works:_

1. Extract literal values from the question ("California", "2025", "premium")
2. Query value index to find columns containing those values
3. Boost those columns' scores in the linker

**Acceptance Criteria:**

- [ ] Value index is built over dimension columns (string/categorical fields with < 1000 distinct values)
- [ ] Matched values are retrieved for literals in the user's question
- [ ] Matched values boost the score of the corresponding columns in linking
- [ ] Value matching completes within latency budget (see performance target)
- [ ] Value matches are logged for debugging

**Performance Target:** Value matching adds < 200ms to linking time

**Dependencies:**

- Story B-1 (baseline linker to integrate with)
- Database or SDM with dimension values

---

**Story G-3: Demonstration Retrieval**

> As a system, I want to retrieve similar examples to improve LLM schema linking.

**Context:**
Few-shot prompting improves LLM performance. By including similar verified queries as examples, the LLM can learn patterns (e.g., "questions about trends usually need time dimensions"). This story retrieves demonstrations to inject into the prompt.

**Scope:**

_What this story produces:_

- Retrieval of verified queries similar to the user's question
- Selection of demonstrations by semantic or structural similarity
- Injection of retrieved demos into the LLM prompt

_What makes a good demonstration:_

- Semantically similar to the user's question
- Successfully executed before (verified query)
- Demonstrates relevant SQL patterns (joins, aggregations)

**Acceptance Criteria:**

- [ ] Verified queries are retrieved by semantic similarity to the user's question
- [ ] Top-N demonstrations are injected into the prompt (N configurable, default 3-5)
- [ ] Demonstration count is bounded to avoid prompt bloat
- [ ] Demonstrations include both NLQ and SQL (or schema elements used)
- [ ] Demonstration retrieval completes within latency budget

**Performance Target:** Demonstration retrieval adds < 300ms to request time

**Dependencies:**

- Verified queries indexed for retrieval (part of Story A-3)
- Prompt builder supports injection of demonstrations

---

**Story G-4: Question Decomposition**

> As a system, I want to decompose complex questions to improve schema recall.

**Context:**
Complex questions like "Compare sales vs. profit trend by region" involve multiple concepts (sales, profit, trend, region). Decomposing into sub-questions and linking each separately increases recall of all needed schema elements. This is optional and triggered only for complex queries.

**Scope:**

_What this story produces:_

- A decomposition step that breaks complex questions into 2-3 sub-questions
- Independent linking for each sub-question
- Merging/union of linking results across sub-questions

_When decomposition is triggered:_

- Only for queries classified as "complex" (by complexity classifier from H-3)
- Configurable threshold (e.g., questions with > 3 concepts)

**Acceptance Criteria:**

- [ ] Complex questions are decomposed into 2-3 sub-questions
- [ ] Each sub-question is linked independently
- [ ] Linking results are merged (union of linked elements)
- [ ] Decomposition is triggered only for complex queries (gated by classifier)
- [ ] Decomposition logs sub-questions for debugging

**Performance Target:** Decomposition adds < 500ms for complex queries

**Dependencies:**

- Story H-3 (complexity classifier to gate decomposition)
- Story B-1 (linker to run on sub-questions)

---

**Story G-5: Schema Enrichment Beyond Minimal Set**

> As a system, I want to expand beyond the minimal schema when it improves SQL quality.

**Context:**
Sometimes the minimal linked schema is too narrow—it misses helpful context columns (e.g., missing "customer_name" when "customer_id" is linked). This story adds enrichment heuristics to include related columns without bloating the prompt excessively.

**Scope:**

_What this story produces:_

- Enrichment rules that add semantically related columns to linked tables
- Heuristics: add name/title fields, add date/timestamp fields, add status/category fields
- Bounded enrichment (max +3 fields per table)

_Why enrich:_

- Name fields help the LLM understand what the table represents
- Date fields enable time-based filtering even if not explicitly requested
- Status fields provide common filtering options

**Acceptance Criteria:**

- [ ] Enrichment adds up to 3 representative fields per linked table
- [ ] Enrichment prioritizes: name/title fields, date fields, status fields
- [ ] Enrichment is bounded to avoid prompt bloat (token budget enforced)
- [ ] Enrichment can be disabled via configuration (for A/B testing)
- [ ] Enrichment logs which fields were added and why

**Performance Target:** Enrichment adds < 10% to prompt token count

**Dependencies:**

- Story C-1 (prompt builder to include enriched fields)

---

**Story G-6: Verified Query Anchoring**

> As a system, I want to surface verified-query candidates and optionally use them to anchor linking when enabled.

**Context:**
We already have verified-query tools that can answer intents directly. The linker should not decide to answer a question via a verified query. Instead, it should surface high-similarity verified queries as signals to the outer agent and, if configured, use them to bias schema linking.

**Scope:**

_What this story produces:_

- Retrieval of the most similar verified queries to the user's question
- Similarity scores and referenced schema elements returned as evidence
- Optional anchoring that boosts those elements during linking (configurable)

_What this does NOT do:_

- It does not short-circuit the NL2SQL flow
- It does not auto-execute a verified query tool

**Acceptance Criteria:**

- [ ] Top verified-query candidates are retrieved by semantic similarity to the user's question
- [ ] Similarity scores and candidate metadata are returned to the outer agent
- [ ] When anchoring is enabled and similarity exceeds threshold, linked elements from the verified query are boosted
- [ ] Anchoring is optional and can be disabled without impacting baseline linking
- [ ] Anchored linking remains compatible with additional schema expansion or fallback

**Performance Target:** Anchored linking completes in < 200ms (vs. 500ms for full linking)

**Dependencies:**

- Story A-3 (verified queries indexed)
- Story B-1 (linker to integrate anchoring)

---

**Story G-7: SQL Skeleton Demo Selection**

> As a system, I want to choose demonstrations by SQL skeleton similarity to improve SQL structure with minimal tokens.

**Context:**
Demonstrations selected by semantic similarity (G-3) may not share SQL structure. Skeleton-based selection picks demos with similar JOIN/GROUP BY patterns, teaching the LLM the right SQL structure for the current query. This uses fewer tokens than showing full SQL.

**Scope:**

_What this story produces:_

- Extraction of SQL skeletons from verified queries (e.g., "SELECT [cols] FROM [table] JOIN [table] GROUP BY [col]")
- Retrieval of demos by skeleton similarity + semantic similarity
- Inclusion of skeleton-matched demos in prompt

_What a skeleton is:_

- SQL with table/column names replaced by placeholders
- Keeps structure: SELECT, FROM, JOIN, WHERE, GROUP BY, ORDER BY, LIMIT

**Acceptance Criteria:**

- [ ] SQL skeletons are extracted from verified query SQL
- [ ] Demonstrations are retrieved by skeleton similarity (Jaccard or similar) + semantic similarity
- [ ] Skeleton-based demos are included in prompt
- [ ] Skeleton selection improves SQL structural accuracy (measured in validation)
- [ ] Skeleton index is built as part of artifact generation (Story A-3)

**Performance Target:** Skeleton-based retrieval adds < 100ms vs. semantic-only retrieval

**Dependencies:**

- Story A-3 (verified queries with SQL)
- Story G-3 (demonstration retrieval framework)

---

**Story G-8: Query Rewrite (Conditional)**

> As a system, I want to rewrite the question into SDM vocabulary when linking confidence is low.

**Context:**
Users may ask "What's the revenue?" when the SDM calls it "total_sales". If linking confidence is low, rewrite the question to use SDM terminology and re-link. This is a fallback strategy for vocabulary mismatch.

**Scope:**

_What this story produces:_

- A rewrite step triggered when confidence < threshold
- LLM-based rewrite that replaces user terms with SDM terms
- Re-linking with rewritten question and merge results with original linking

_When to rewrite:_

- Only when confidence is below threshold (e.g., < 0.60)
- Not for every query (too expensive)

**Acceptance Criteria:**

- [ ] Rewrite is triggered only when confidence is below threshold
- [ ] Rewritten question uses SDM vocabulary (table names, field names, metric names)
- [ ] System re-links with rewritten question
- [ ] Results from original and rewritten linking are merged (union)
- [ ] Rewrite attempts are logged for debugging

**Performance Target:** Rewrite adds < 1s when triggered (LLM call overhead)

**Dependencies:**

- Story B-1 (confidence score to gate rewrite)
- LLM API for rewriting

---

**Story G-9: Multi-Sample Union (Conditional)**

> As a system, I want to sample multiple linking predictions and union them to increase recall on complex queries.

**Context:**
For complex or ambiguous queries, a single linking attempt may miss needed elements. Multi-sampling generates multiple linking predictions (varying parameters or randomness) and unions them to increase recall. This is expensive and only used when necessary.

**Scope:**

_What this story produces:_

- Generation of N linking predictions (N = 3-5) with slight parameter variations
- Union of all predicted schema elements
- Bounded union size (cap total elements to fit in context)

_When to multi-sample:_

- Confidence < threshold OR
- Query classified as "complex"

**Acceptance Criteria:**

- [ ] Multi-sampling is triggered only for low-confidence or complex queries
- [ ] System generates N linking predictions (N configurable, default 3)
- [ ] Predictions are unioned (deduplicated)
- [ ] Union size is capped to context budget (drop lowest-scoring elements if needed)
- [ ] Multi-sampling logs sample count and union size

**Performance Target:** Multi-sampling adds < 1s (N parallel linking calls)

**Dependencies:**

- Story B-1 (linker with configurable parameters)
- Story H-3 (complexity classifier to gate multi-sampling)

---

### Epic H: Guardrails and Optimization

**Story H-1: Extractive Selection Constraint**

> As a system, I want the LLM to select schema elements only from retrieved candidate IDs so it cannot hallucinate table or column names.

**Context:**
LLMs sometimes hallucinate—generate table/column names that don't exist in the schema. This breaks SQL execution. Extractive selection constrains the LLM to only choose from a pre-retrieved candidate list (by ID), preventing hallucination. This aligns with the "align before generate" pattern.

**Scope:**

_What this story produces:_

- A prompt format that provides candidate IDs to the LLM (not free-form schema)
- Parsing of LLM output as ID selections (not free text)
- Validation that rejects invalid IDs (IDs not in candidate list)

_How extractive selection works:_

1. Linker retrieves 50-100 candidate tables/fields (with IDs)
2. Prompt provides candidate IDs: "Select from: [table:sdm1:orders, table:sdm1:customers, ...]"
3. LLM outputs IDs: "Selected: [table:sdm1:orders, field:sdm1:orders:amount]"
4. System validates IDs are in candidate list

**Acceptance Criteria:**

- [ ] LLM prompt provides candidate element IDs, not free-form schema descriptions
- [ ] LLM output is parsed as a list of selected IDs
- [ ] Invalid IDs (not in candidate list) are rejected with clear error message
- [ ] System does not attempt to fuzzy-match invalid IDs (strict validation)
- [ ] Extractive selection eliminates hallucinated schema element names

**Performance Target:** ID validation adds < 5ms

**Dependencies:**

- Story B-1 (candidate retrieval)
- Prompt builder supports ID-based format

---

**Story H-2: Repair Loop on Execution Error**

> As a system, I want to attempt one SQL correction when execution fails so recoverable errors don't require user intervention.

**Context:**
Even with good linking, generated SQL sometimes fails due to minor errors (typos, wrong JOIN syntax, missing GROUP BY). A repair loop captures the error, provides it to the LLM with the original SQL, and attempts one correction. This recovers from many transient errors without user intervention.

**Scope:**

_What this story produces:_

- Error capture on SQL execution failure (error message + context)
- LLM-based repair: provide error + original SQL + linked schema, ask for correction
- Single retry attempt (no infinite loops)

_What errors to repair:_

- Syntax errors (missing parentheses, wrong JOIN syntax)
- Semantic errors (ambiguous column references, missing GROUP BY)
- Not data errors (constraint violations, wrong values)

**Acceptance Criteria:**

- [ ] On SQL execution error, system captures error message and SQL that failed
- [ ] System calls LLM with: error message, original SQL, linked schema, request for correction
- [ ] Corrected SQL is executed (one retry only)
- [ ] Repair attempts and success rate are logged
- [ ] Infinite loops are prevented (max 1 repair attempt)

**Performance Target:** Repair adds < 2s when triggered (one extra LLM call)

**Edge Cases:**

- If repair also fails, return both errors to user
- Repair is not attempted for data errors (wrong table, missing data)

**Dependencies:**

- SQL execution error handling (assumed to exist)
- LLM API for correction

---

**Story H-3: Complexity Classifier (SLM)**

> As a system, I want a lightweight classifier to decide query complexity so I only pay for expensive operations (decomposition, rewrite, multi-sample) when needed.

**Context:**
Enhancements like decomposition (G-4), rewrite (G-8), and multi-sampling (G-9) are expensive (extra LLM calls, higher latency). They should only run on complex queries that need them. A complexity classifier gates these operations, saving cost and time on simple queries.

**Scope:**

_What this story produces:_

- A classifier that labels queries as simple/moderate/complex
- Rule-based or SLM-based (start with rules, upgrade to SLM if needed)
- Integration points in the pipeline to gate expensive operations

_What makes a query complex:_

- Multiple concepts (> 2 aggregations, > 2 dimensions)
- Multiple tables required (based on preliminary linking)
- Temporal comparisons ("vs. last year", "trend over time")

**Acceptance Criteria:**

- [ ] Classifier labels queries as simple/moderate/complex in < 50ms
- [ ] Simple queries skip decomposition, rewrite, and multi-sampling
- [ ] Complex queries trigger full enhancement pipeline
- [ ] Classifier can be rule-based (no ML) or SLM-based (lightweight model)
- [ ] Classification is logged for debugging and evaluation

**Performance Target:** Classification adds < 50ms and minimal cost

**Rule-Based Classifier (Phase 1):**

- Count: JOINs, GROUP BYs, subqueries, aggregations, time comparisons
- Simple: 0-1 joins, 0-1 aggregations
- Moderate: 2 joins, 2-3 aggregations
- Complex: 3+ joins or 3+ aggregations or subqueries

**Dependencies:**

- Stories G-4, G-8, G-9 (operations to gate)

---

**Story H-4: SLM Reranker**

> As a system, I want a small model to rerank top-50 retrieval candidates so I get better precision without a full LLM call.

**Context:**
BM25 + embedding retrieval is fast but imperfect. A small reranking model (SLM) can reorder the top-50 candidates more accurately than raw retrieval scores, improving precision before feeding results to the LLM. This is cheaper and faster than using the LLM itself for reranking.

**Scope:**

_What this story produces:_

- A small model (< 100M parameters) that scores candidate relevance given a question
- Reranking applied after BM25 + embedding retrieval, before final selection
- Model can be fine-tuned on schema linking data

_How reranking works:_

1. Retrieve top-50 candidates (BM25 + embeddings)
2. Rerank using SLM (produces refined scores)
3. Select top-K from reranked list

**Acceptance Criteria:**

- [ ] SLM reranker scores candidate relevance given the user's question
- [ ] Reranking is applied after retrieval, before final selection
- [ ] Reranker improves precision vs. raw retrieval (validated via A/B test)
- [ ] Reranking is faster and cheaper than LLM-based selection
- [ ] Reranker can be fine-tuned on domain-specific data

**Performance Target:** Reranking adds < 100ms for 50 candidates

**Model Options:**

- MiniLM cross-encoder (recommended)
- DistilBERT cross-encoder
- Fine-tuned on question-schema pairs

**Dependencies:**

- Story B-1 (retrieval to rerank)
- Fine-tuning data (optional, improves quality)

---

**Story H-5: Learned Confidence Calibration**

> As a system, I want to train a confidence predictor from routing features so confidence scores better predict actual success.

**Context:**
The baseline confidence score (from B-1) is heuristic-based. A learned model can predict success more accurately by training on historical queries with known outcomes. This improves fallback decisions and reduces unnecessary fallbacks.

**Scope:**

_What this story produces:_

- A lightweight model that predicts P(success | routing_features)
- Training on historical queries with execution success labels
- Integration to replace or augment heuristic confidence

_What features to use:_

- Score margins (how confident was retrieval?)
- Join closure cost (how many bridges were added?)
- Value hit count (how many user values matched?)
- Query complexity (from H-3 classifier)

**Acceptance Criteria:**

- [ ] Confidence model is trained on historical query data with success labels
- [ ] Model uses routing features: score margins, join closure cost, value matches, complexity
- [ ] Calibrated confidence improves fallback decisions (fewer false positives/negatives)
- [ ] Model is lightweight (< 10M parameters) and fast (< 10ms inference)
- [ ] Model is interpretable (feature importance available)

**Performance Target:** Confidence prediction adds < 10ms

**Dependencies:**

- Historical query logs with execution success labels (at least 1000 queries)
- Story B-1 (features to train on)

---

## Breaking Changes

| What Changes                   | Impact                            | Mitigation                                      |
| ------------------------------ | --------------------------------- | ----------------------------------------------- |
| Full-schema prompts by default | Prompts now pruned                | Provide fallback and override flag              |
| Implicit schema selection      | Explicit linking required         | Ship baseline linker + deterministic refinement |
| Prompt format                  | Includes linked schema + evidence | Update prompt builders + tests                  |

---

## Success Metrics

| Metric                     | Target             | Measurement                                  |
| -------------------------- | ------------------ | -------------------------------------------- |
| **Prompt Token Count**     | 30–60% reduction   | Compare pre/post linking                     |
| **Latency**                | 20–40% faster      | End-to-end timing (NL question → SQL result) |
| **NL2SQL Accuracy (EX)**   | 5–15% improvement  | Test set execution accuracy vs baseline      |
| **Linking Recall@k**       | > 90% at k=10      | % queries where all needed elements appear   |
| **Linking Precision@k**    | > 60% at k=10      | Noise level in linked schema                 |
| **Joinability Rate**       | > 99%              | Linked schema always connected/compilable    |
| **Fallback Rate**          | < 10%              | % queries using widened/full schema          |
| **Complex Query Accuracy** | 10–20% improvement | Multi-join and aggregation queries           |
| **Operational Stability**  | 0 regressions      | Error rate / rollback rate                   |

**Validation:** See [Schema Linking Testing Guide](./schema-linking-testing-guide.md) for detailed validation procedures using BIRD benchmark.

---

## References

| Technique                                                                                              | What it does                                                                                                                  | Primary paper source(s)                                                                           |
| ------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| **Componentized "semantic units" + multi-stage retrieval (table/field/metadata indexed separately)**   | Improves recall/precision on large catalogs by indexing schema/metadata as separate retrievable units and narrowing in stages | **RASL: Retrieval Augmented Schema Linking for Massive Database Text-to-SQL** (2025) ([arXiv][1]) |
| **Two-stage routing (tables → fields) + relevance calibration**                                        | High-recall table selection first; then precision field selection only within those tables                                    | **RASL** (same) ([arXiv][1])                                                                      |
| **Multi-round retrieval + irrelevant-isolation + query rewriting (only on low confidence)**            | When the schema vocab doesn't match the user vocab, rewrite once and reroute; optionally isolate irrelevant schema candidates | **LinkAlign** (EMNLP 2025 / arXiv 2025) ([ACL Anthology][2])                                      |
| **SQL skeleton-based demonstration selection**                                                         | Pick examples by structural similarity (GROUP BY / JOIN pattern) rather than only semantic similarity                         | **DAIL-SQL** (VLDB 2024) ([bolinding.github.io][3])                                               |
| **Conditional decomposition for complex questions**                                                    | Break down hard NLQs into manageable subtasks (linking → classification/decomposition → SQL → self-correction)                | **DIN-SQL** (2023, NeurIPS) ([arXiv][4])                                                          |
| **Test-time self-consistency + merge/revise correction (selectively)**                                 | Sample multiple SQL candidates; choose/merge the best; use revision to fix semantic errors (not just syntax)                  | **CSC-SQL** (2025) ([arXiv][5])                                                                   |
| **"Don't prune when schema fits" + highlight/augment/select/correct instead of hard filtering**        | When you can fit enough schema/SDM in context, avoid catastrophic recall misses from pruning                                  | **The Death of Schema Linking?** (2024) ([arXiv][6])                                              |
| **Router ↔ generator decoupling; relation-aware retrieval / routing**                                 | Clean separation: route to the right DB/tables first, then generate SQL; supports massive schema scenarios                    | **DBCopilot** (arXiv 2312.03463) ([arXiv][7])                                                     |
| **Deterministic refinement rules (membership closure, FK path closure, FK key closure, fuzzy repair)** | Fix the most common "it selected the right stuff but forgot the join glue" failures; improves recall and executability        | **IBM schema-linking paper** (attached PDF)                                                       |
| **Hallucination mitigation by "before generation, align it"**                                          | Strengthen pre-generation alignment to reduce hallucinated tables/columns; complements extractive linking + constraints       | **TA-SQL** (ACL Findings 2024) ([arXiv][8])                                                       |
| **Question rewriting + execution feedback loop** (optional enhancement)                                | Rewrite ambiguous quest; use execution feedback to repair                                                                     | **DART-SQL** (ACL Findings 2024) ([ACL Anthology][9])                                             |

[1]: https://arxiv.org/pdf/2507.23104?utm_source=chatgpt.com
[2]: https://aclanthology.org/2025.emnlp-main.51/?utm_source=chatgpt.com
[3]: https://bolinding.github.io/papers/vldb24dailsql.pdf?utm_source=chatgpt.com
[4]: https://arxiv.org/abs/2304.11015?utm_source=chatgpt.com
[5]: https://arxiv.org/abs/2505.13271?utm_source=chatgpt.com
[6]: https://arxiv.org/abs/2408.07702?utm_source=chatgpt.com
[7]: https://arxiv.org/abs/2312.03463?utm_source=chatgpt.com
[8]: https://arxiv.org/abs/2405.15307?utm_source=chatgpt.com
[9]: https://aclanthology.org/2024.findings-acl.120/?utm_source=chatgpt.com
