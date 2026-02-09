# Feature Specification v5.1: Schema Linking for NL2xQL (Fully Revised)

**Status:** Proposed  
**Author:** Agent Platform Team  
**Date:** 2026-01-31
**Supersedes:** v1 → v5

---

## Changelog from v3.6

- **Added Glossary (§1.1):** Defines key terms (membership closure, FK-key closure, metric closure, etc.)
- **Fixed Epic F table:** Added F-0 (Confidence Scoring) to summary table
- **Added Metric Card example:** Story A-2 now includes complete metric card structure
- **Clarified B-1 phase flexibility:** Section 4 notes B-1 can be pulled into Phase 1 if needed
- **Added Phase column to Epic E table:** Consistent with other Epics
- **Fixed confidence formula edge case:** Single-candidate handling clarified
- **Added Error Response Contract (§5.5):** Standardized error output format
- **Clarified Conversation History:** Noted as Phase 2+ input for query understanding
- **Simplified connector minimization (§5.4.3, D-6):** Replaced Steiner-tree approximation with a greedy connect-to-component algorithm (BFS shortest-path attachment) — simpler to implement, strong results for small terminal sets.
- **Made entitlements configurable (§5.4.5, B-1):** Added `strict` vs `passthrough` modes; `passthrough` (default) relies on DB enforcement.
- **Specified admin debug mode trigger:** Header + entitlement requirement

---

## 1. Executive Summary

Schema linking selects the minimal relevant portion of a Semantic Data Model (SDM) for each natural language question, reducing prompt size and improving query generation accuracy.

### Core Design Principle: Physical-First

Cards are **indexed by physical names** and **return physical references**. The SDM enriches search quality but is not the source of identifiers.

```
┌─────────────────────────────────────────────────────────────────┐
│  SDM provides ENRICHMENT for search                             │
│  ───────────────────────────────────                            │
│  • Synonyms: "client", "buyer" → help match "sales_dw.cust_mstr"│
│  • Descriptions: improve search relevance                       │
│  • Relationships: define joins between physical tables          │
│                                                                 │
│  But cards are INDEXED BY and RETURN physical references        │
└─────────────────────────────────────────────────────────────────┘
```

### Design Principle: Explicit Relationships (No Runtime Join Inference)

Within a single SDM (i.e., within the same source/database), the linker **does not infer joins**. It relies only on **explicit relationships** declared in the SDM:

- If two tables are joinable, that relationship must exist as an SDM edge (with physical join keys).
- If no path exists, the linker returns `connectivity="disconnected"` and a structured explanation (it does not hallucinate connectors).

Cross-SDM connectivity (federation) is handled separately via **explicit cross-SDM relationship artifacts** (Phase 3), not by runtime inference.

### What Schema Linking IS

- Selecting which tables/columns/schemas/fields are relevant to a question
- Ensuring selected elements can be joined together
- Filtering by user access permissions
- Returning **physical** schema elements for the generator

### What Schema Linking is NOT

- Generating SQL/JQ queries (→ Generator)
- Deciding how to decompose complex queries (→ Generator)
- Executing queries against databases (→ Executor)
- Building prompts (→ Prompt Builder)

---

### 1.1 Glossary

| Term                       | Definition                                                                                                                                                          |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Card**                   | A search-optimized document representing a schema element (table, column, metric). Indexed for BM25/embedding retrieval. Internal to the linker.                    |
| **Schema Slice**           | The output of the linker: a minimal set of physical tables, columns, and joins relevant to a question.                                                              |
| **Membership Closure**     | Adding tables that own selected columns. If column `orders.amount` is selected, table `orders` must be in the slice.                                                |
| **FK-Key Closure**         | Adding columns required for joins. If `orders` and `customers` are joined on `customer_id`, both FK columns are added.                                              |
| **Metric Closure**         | Adding tables/columns referenced by a selected metric's expression. If metric `total_revenue` = `SUM(orders.amount)`, table `orders` and column `amount` are added. |
| **Connector Table**        | A table added to enable joins between selected tables (e.g., a bridge table).                                                                                       |
| **Connector Minimization** | Finding the smallest set of connector tables needed to make selected tables joinable. Implemented via greedy shortest-path attachment.                              |
| **SDM**                    | Semantic Data Model. Contains logical names, descriptions, synonyms, relationships, and mappings to physical tables/columns.                                        |
| **Physical Reference**     | The actual database identifier (e.g., `sales_dw.cust_mstr.cust_id`), as opposed to a logical/business name.                                                         |

---

## 2. Approach: Hybrid Deterministic + Agentic

This spec uses a **hybrid approach**: deterministic algorithms where optimal, LLM/agentic approaches where they add value.

### When to Use What

| Task                     | Approach         | Rationale                                                                                   |
| ------------------------ | ---------------- | ------------------------------------------------------------------------------------------- |
| **Card generation**      | ⚙️ Deterministic | SDM provides all metadata needed                                                            |
| **Query understanding**  | 🤖 LLM           | Semantic parsing beats regex                                                                |
| **Retrieval**            | ⚙️ Deterministic | BM25 + embeddings are fast & proven                                                         |
| **Refinement/closure**   | ⚙️ Deterministic | Graph algorithms are correct by definition                                                  |
| **Join minimization**    | ⚙️ Deterministic | Greedy shortest-path attachment (simple, deterministic; works well for small terminal sets) |
| **Recovery/rewriting**   | 🤖 LLM           | Understands WHY linking failed                                                              |
| **Ambiguity resolution** | 🤖 LLM           | Reasons about interpretations                                                               |
| **Policy filtering**     | ⚙️ Deterministic | Security must be deterministic                                                              |

### Cost/Latency Tradeoffs

| Component              | Latency     | LLM Calls | When Invoked                  |
| ---------------------- | ----------- | --------- | ----------------------------- |
| Card generation        | Offline     | 0         | SDM update (deterministic)    |
| Query understanding    | +200-500ms  | 1         | Every request (Phase 2+)      |
| Retrieval (BM25+embed) | 50-200ms    | 0         | Every request                 |
| Refinement             | 20-80ms     | 0         | Every request                 |
| Recovery loop          | +500-1000ms | 1-2       | Only on low confidence (~10%) |
| Ambiguity check        | +300-500ms  | 1         | Only when ambiguous (~15%)    |

**Typical request:** 1-2 LLM calls (query understanding + optional recovery)

---

## 3. Research Foundation

| Paper                                | Key Technique                                  | Approach      | Used In   |
| ------------------------------------ | ---------------------------------------------- | ------------- | --------- |
| **RASL** (Amazon, 2025)              | Componentized cards, two-stage retrieval       | Deterministic | Epic A, D |
| **LinkAlign** (EMNLP 2025)           | Multi-round retrieval, query rewriting         | 🤖 Agentic    | Epic E    |
| **Rethinking Schema Linking** (2025) | Bidirectional retrieval, question augmentation | Hybrid        | Epic D, E |
| **SteinerSQL** (2025)                | Steiner tree for join paths                    | Deterministic | Epic D    |
| **DBCopilot** (EDBT 2025)            | Schema routing                                 | Deterministic | Epic C    |
| **E-SQL** (2024)                     | Question enrichment                            | 🤖 Agentic    | Epic E    |
| **CHESS** (2024)                     | Entity extraction, value matching              | 🤖 Agentic    | Epic E    |
| **DIN-SQL** (NeurIPS 2023)           | Decomposition, self-correction                 | 🤖 Agentic    | Epic E    |
| **IBM Schema Linking**               | FK-path/key closure                            | Deterministic | Epic D    |

---

## 4. Implementation Phases

```
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 1: Core MVP                                              │
│  • BM25 only, no LLM required                                   │
│  • SQLite FTS5 sufficient                                       │
│  • Optional: B-1 (Policy Filter) if enterprise requires early   │
│  Time: 2-3 weeks                                                │
├─────────────────────────────────────────────────────────────────┤
│  PHASE 2: Accuracy & Scale                                      │
│  • Add embeddings (sqlite-vss / pgvector)                       │
│  • Add LLM query understanding                                  │
│  • Add LLM recovery loop                                        │
│  Time: 3-4 weeks                                                │
├─────────────────────────────────────────────────────────────────┤
│  PHASE 2.1: Hierarchical Schemas                                │
│  • JSON schema support                                          │
│  • Same hybrid approach                                         │
│  Time: 2-3 weeks                                                │
├─────────────────────────────────────────────────────────────────┤
│  PHASE 3: Enterprise                                            │
│  • Multi-database routing                                       │
│  • Access control (if not done in Phase 1)                      │
│  • Ambiguity resolution (LLM)                                   │
│  • Cross-SDM relationship management                            │
│  Time: 4-5 weeks                                                │
├─────────────────────────────────────────────────────────────────┤
│  PHASE 4: Cross-Domain                                          │
│  • SQL + JQ unified                                             │
│  Time: 3-4 weeks                                                │
└─────────────────────────────────────────────────────────────────┘
```

### Infrastructure by Phase

| Phase   | Search            | Vector DB             | LLM Calls                   | Notes                               |
| ------- | ----------------- | --------------------- | --------------------------- | ----------------------------------- |
| **1**   | BM25 only         | None                  | **0** (fully deterministic) | B-1 can be added here if needed     |
| **2**   | BM25 + Embeddings | sqlite-vss / pgvector | 1-2 per request             |                                     |
| **2.1** | Same              | Same                  | Same                        |                                     |
| **3**   | Same              | Same                  | 1-3 per request             | B-1 required if not done in Phase 1 |
| **4**   | Same              | Same                  | Same                        |                                     |

---

## 5. Component Boundary

### 5.1 Physical-First with SDM Enrichment

**Critical Concept:** Cards are indexed by **physical names** and return **physical references**. The SDM provides enrichment for search but is not the source of identifiers.

```
┌─────────────────────────────────────────────────────────────────┐
│  PHYSICAL DATABASE              SEMANTIC DATA MODEL (SDM)       │
│  ──────────────────             ─────────────────────────       │
│                                                                 │
│  sales_dw.cust_mstr      ◄──    Enrichment for search:          │
│    cust_id                        Logical: "Customers"          │
│    cust_nm                        Synonyms: [client, buyer]     │
│    rgn_cd                         Description: "Master data"    │
│                                                                 │
│  (What we index & return)       (What helps us find it)         │
└─────────────────────────────────────────────────────────────────┘
```

**The SDM provides:**

- Logical/business-friendly names → included in searchable text
- Descriptions → included in searchable text
- Synonyms → included in searchable text
- Relationships → stored with physical references
- Mapping to physical table/column names → **this becomes the card ID**

**Why Physical-First:**

```
User: "Show sales by customer"
            │
            ▼
┌───────────────────────────────────────────────────────────────┐
│  Search CARDS                                                 │
│  ────────────                                                 │
│  Query: "sales customer"                                      │
│  Card text: "cust_mstr Customers client buyer..."             │
│             ↑          ↑                                      │
│          physical    SDM enrichment helps match!              │
│                                                               │
│  Match: card for "sales_dw.cust_mstr"                         │
└───────────────────────────────────────────────────────────────┘
            │
            ▼
┌───────────────────────────────────────────────────────────────┐
│  Return SCHEMA SLICE (all physical)                           │
│  ──────────────────────────────────                           │
│  table: "sales_dw.cust_mstr"                                  │
│  columns: ["cust_id", "cust_nm"]                              │
└───────────────────────────────────────────────────────────────┘
            │
            ▼
   Generator directly produces:
   SELECT cust_nm, SUM(amount)
   FROM sales_dw.cust_mstr ...

   ✓ No translation layer needed!
```

### 5.2 Input / Output Contract

```
┌────────────────────────────────────────────────────────────────┐
│                      SCHEMA LINKER                             │
│                                                                │
│  INPUT                           OUTPUT                        │
│  ─────                           ──────                        │
│  • NL Question                   • Schema Slice                │
│  • User Context                    - Physical table names      │
│  • SDM Version                     - Physical column names     │
│  • Conversation History (2+)       - Types, joins, keys        │
│                                  • Confidence Score            │
│                                  • Connectivity Status         │
│                                  • Linking Trace               │
│                                  • Error (if failed)           │
└────────────────────────────────────────────────────────────────┘

Note: Conversation History is used in Phase 2+ for query understanding
context. In Phase 1, it is accepted but ignored.
```

### 5.3 Architecture with Agentic Components

```
┌─────────────────────────────────────────────────────────────────┐
│                         NL Question                             │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│  🤖 QUERY UNDERSTANDING (LLM)                         Phase 2+  │
│  • Extract entities, metrics, filters, time ranges              │
│  • Map user jargon to domain vocabulary (no schema IDs)         │
│  • Identify query intent                                        │
│  • Uses conversation history for context                        │
│  Output: Parsed query with extracted terms                      │
└──────────────────────────────┬───────────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│  ⚙️ RETRIEVAL (Deterministic)                                   │
│  • BM25 keyword search over cards                               │
│  • Embedding similarity search (Phase 2+)                       │
│  • Cards indexed by PHYSICAL names                              │
│  • Card text includes SDM enrichment for better matching        │
└──────────────────────────────┬───────────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│  ⚙️ REFINEMENT (Deterministic)                                  │
│  • Membership closure                                           │
│  • FK-key closure (using physical references)                   │
│  • Metric closure (add dependencies of selected metrics)        │
│  • Greedy connector minimization (shortest-path attachment)                          │
└──────────────────────────────┬───────────────────────────────────┘
                               ▼
          ┌────────────────────┴────────────────┐
          │     Confidence < threshold?         │
          │     OR not connected?               │
          └────────────────┬────────────────────┘
                    yes    │    no
          ┌────────────────┴────────────────┐
          ▼                                 ▼
┌─────────────────────────┐      ┌─────────────────────────┐
│ 🤖 RECOVERY (LLM)       │      │  Continue               │
│ • Analyze failure       │      │                         │
│ • Rewrite query         │      │                         │
│ • Re-retrieve           │      │                         │
└──────────┬──────────────┘      └──────────┬──────────────┘
           └────────────────┬───────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│  🤖 AMBIGUITY CHECK (LLM, Optional)                   Phase 3+  │
│  • Multiple valid interpretations detected?                     │
│  • Rank by likelihood OR return alternatives                    │
└──────────────────────────────┬───────────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│  ⚙️ POLICY FILTER (Deterministic)              Phase 1 or 3+    │
│  • Remove unauthorized elements                                 │
└──────────────────────────────┬───────────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│  OUTPUT: Schema Slice (physical refs) + Confidence + Trace      │
└──────────────────────────────────────────────────────────────────┘

Legend: 🤖 = LLM/Agentic    ⚙️ = Deterministic
```

---

### 5.4 Core Contracts and Guardrails (MUST implement)

This section tightens underspecified behaviors so multiple engineers don't implement divergent linkers. It **does not add new scope**—it makes existing requirements precise.

#### 5.4.0 Data modeling contract (TypedDict prohibition)

- **No `TypedDict` or raw dicts for domain objects.** Use Pydantic `BaseModel` (preferred) or `@dataclass` for linker data structures (cards, filters, schema slices, traces).
- Opaque JSON blobs (e.g., raw payloads, JSON schema documents) may remain `dict[str, Any]` but must be wrapped in a typed model that gives the object a clear domain boundary.

#### 5.4.1 Deterministic query normalization (Phase 1)

Even in BM25-only mode, normalize the query into stable search tokens:

- Split on `.`, `_`, `-`, and camelCase
- Lowercase, strip punctuation
- Drop configurable stopwords
- Optional: deterministic synonym expansion using SDM synonyms dictionary (no LLM)

This improves recall without adding agentic complexity.

#### 5.4.2 Connectivity contract

- `connectivity: "connected" | "disconnected"`
- If `disconnected`, the linker **MUST** return:
  - `components`: list of connected components (each is a list of tables)
  - `missing_links`: list of terminal pairs that could not be connected (with a reason)
- The linker **MUST NOT** pretend connectivity by adding arbitrary connector tables when no join path exists in the schema graph.

Rationale: connectivity failure is a _schema linking outcome_; decomposition/clarification is a generator/agent decision.

#### 5.4.3 Connector minimization contract (Greedy shortest-path)

**Goal:** Given a set of terminal tables `T` (from retrieval + closure), find a connected subgraph containing all `T` while adding as few extra connector/bridge tables as practical.

We intentionally avoid Steiner/MST-based approximations in the implementation spec because they add complexity that is rarely necessary for NL2xQL slices (typically **K≈6–12 terminal tables**).

**Recommended algorithm: Greedy connect-to-component (deterministic)**

```python
def find_connectors(join_graph, terminals, seed=None):
    """
    Greedy connector minimization using shortest-path attachment.

    join_graph: graph where nodes are physical tables and edges are SDM relationships
    terminals: iterable of physical table names that must be connected
    seed: optional terminal to start from (default = highest-scoring; tie-break lexical)
    """
    terminals = set(terminals)
    if len(terminals) <= 1:
        return terminals

    # Deterministic seed selection
    seed = seed or select_seed(terminals)  # highest retrieval score, then lexical
    connected = {seed}
    remaining = terminals - {seed}

    while remaining:
        best_t, best_path = None, None
        best_len = 10**9

        # Deterministic iteration order for reproducibility
        for t in sorted(remaining):
            path = bfs_shortest_path_to_component(join_graph, t, connected)  # returns list of nodes
            if not path:
                continue

            if len(path) < best_len or (len(path) == best_len and should_prefer(t, best_t)):
                best_t, best_path, best_len = t, path, len(path)

        if best_path is None:
            # No join path exists for at least one remaining terminal
            break

        connected.update(best_path)
        remaining.remove(best_t)

    return connected
```

**Tie-breaking (MUST be deterministic):**

1. Shorter path length wins
2. Higher retrieval score wins (if available)
3. Lexical order wins

**Post-step (required):** After connector minimization, run FK-key closure to add join columns for all edges on the selected paths.

**If disconnected:** If any terminal cannot be attached, return `connectivity="disconnected"` and include `components` + `missing_links` (see §5.4.2).

> Optional future enhancement (not required): introduce Steiner/MST approximation behind a feature flag once the greedy version is stable and benchmarked.

#### 5.4.4 Confidence score contract

A single scalar `confidence` is used only for gating (recovery, widening, fallback). Define it deterministically:

**Formula:**

```python
from math import sqrt

def compute_confidence(table_candidates, column_candidates, selected_column_ids, is_connected):
    """
    Deterministic confidence for gating (recovery, widening, fallback).

    table_candidates: ranked list with .score in [0,1] (or normalized)
    column_candidates: ranked list with .id and .score in [0,1] (or normalized)
    selected_column_ids: set/list of column IDs selected into the slice (subset of candidate IDs)
    is_connected: bool
    """
    # Table confidence: dominance of top match
    if len(table_candidates) >= 2:
        s1, s2 = table_candidates[0].score, table_candidates[1].score
        table_conf = s1 / (s1 + s2) if (s1 + s2) > 0 else 0.0
    elif len(table_candidates) == 1:
        table_conf = max(0.0, min(table_candidates[0].score, 1.0))
    else:
        table_conf = 0.0

    # Column confidence: mass of selected columns vs mass of candidates
    selected_ids = set(selected_column_ids or [])
    selected_mass = sum(c.score for c in column_candidates if getattr(c, "id", None) in selected_ids)
    candidate_mass = sum(c.score for c in column_candidates)
    col_conf = (selected_mass / candidate_mass) if candidate_mass > 0 else 0.0
    col_conf = max(0.0, min(col_conf, 1.0))

    # Connectivity penalty
    conn_factor = 1.0 if is_connected else 0.7

    # Combined confidence (geometric mean)
    return sqrt(table_conf * col_conf) * conn_factor
```

The linker should include `_debug.confidence_breakdown` in traces for tuning.

#### 5.4.5 Entitlements and safe tracing

Entitlement enforcement is **configurable** based on your threat model:

```yaml
entitlements:
  mode: "strict" | "passthrough"    # Default: "passthrough"
```

| Mode              | Behavior                                                                                                        | Use When                                                                        |
| ----------------- | --------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| **`strict`**      | Filter schema elements by user permissions before returning slice, logging, or sending schema context to an LLM | Schema structure is sensitive; multi-tenant SaaS; probing attacks are a concern |
| **`passthrough`** | Return full slice; rely on DB/executor for access control                                                       | Schema is non-sensitive; internal trusted deployments                           |

When `strict` mode is enabled, authorization must be enforced **before**:

- returning a schema slice,
- logging retrieval candidates (unless redacted),
- sending any schema-related context to an LLM.

**Minimum rules:**

- Filter retrieval results by entitlements (at query-time or index-time)
- Default traces to **redact** sample values / sensitive descriptions
- Admin debug mode: enabled via `X-Debug-Trace: full` header (requires `admin` entitlement)

#### 5.4.6 Slice budgets (prompt safety)

Define hard caps and enforce them deterministically:

- `max_tables` (default: 10)
- `max_columns_per_table` (default: 25)
- `max_total_columns` (default: 80)

Return `truncated: true/false` and the applied limits. This prevents prompt bloat and downstream confusion.

#### 5.4.7 Metric cards must be machine-actionable

A metric card must include a machine-readable list of referenced **physical** tables/columns (precomputed from SDM). If a metric is selected, metric closure must pull in those dependencies deterministically (no LLM).

#### 5.4.8 Query understanding contract (Phase 2+)

The Phase 2 LLM call is **schema-agnostic**:

- Input: question + optional conversation context + optional small domain glossary
- Output: normalized search tokens + entities/metrics/filters/time hints
- It **MUST NOT** output table/column identifiers

This keeps the LLM cheap, scalable, and prevents schema hallucination.

---

### 5.5 Error Response Contract

When the linker fails, return a structured error:

```yaml
error:
  code: "sdm_not_found" | "entitlement_denied" | "no_matches" | "timeout" | "internal_error"
  message: "Human-readable explanation"
  details:                          # Optional, for debugging
    sdm_version: "v2.3.1"
    elapsed_ms: 450
  trace_id: "abc123-def456"         # For log correlation

# Always include (even on error):
schema_slice: null                  # or empty slice
confidence: 0.0
connectivity: "unknown"
```

**Error codes:**

| Code                 | Meaning                                            | HTTP Status            |
| -------------------- | -------------------------------------------------- | ---------------------- |
| `sdm_not_found`      | Requested SDM version doesn't exist                | 404                    |
| `entitlement_denied` | User lacks permission to access any matched schema | 403                    |
| `no_matches`         | No schema elements matched the query               | 200 (with empty slice) |
| `timeout`            | Linking exceeded time budget                       | 504                    |
| `internal_error`     | Unexpected failure                                 | 500                    |

---

## 6. Epics & Stories

---

## EPIC A: Schema Graph & Routing Artifacts

**Goal:** Build internal data structures that enable fast linking.

**Approach:** Fully deterministic. SDM provides all metadata needed.

| Story                | Phase | Approach         | LLM Calls |
| -------------------- | ----- | ---------------- | --------- |
| A-1: Schema graph    | 1     | ⚙️ Deterministic | 0         |
| A-2: Card generation | 1     | ⚙️ Deterministic | 0         |
| A-3: Caching         | 2     | ⚙️ Deterministic | 0         |

---

### Story A-1: Build Schema Graph from SDM [Phase 1] ⚙️

> As a developer, I want a schema graph from the SDM so linking can check connectivity.

**Approach:** Pure deterministic graph construction. No LLM needed.

**What this produces:**

- Graph with **physical table names** as nodes
- Relationships as edges (stored with physical references)
- Edges store: join keys (physical), cardinality, provenance

**Acceptance Criteria:**

- [ ] All physical tables as nodes
- [ ] Relationships stored with physical column references
- [ ] Can compute: joinability, shortest path
- [ ] Handles self-referential relationships

**Performance:** < 100ms load for 500 tables

---

### Story A-2: Generate Routing Cards from SDM [Phase 1] ⚙️

> As a developer, I want search-optimized cards indexed by physical names.

**Approach:** Deterministic extraction from SDM. **No LLM needed** — SDM already contains synonyms, descriptions, and business context.

**Key Principle:** Cards are indexed by **physical names** but include **SDM enrichment** in searchable text.

**Source of card content:**

| Card Field          | Source                                                | Purpose                 |
| ------------------- | ----------------------------------------------------- | ----------------------- |
| `id`                | Physical table/column name                            | **Primary identifier**  |
| `text` (searchable) | physical_name + logical_name + description + synonyms | Search matching         |
| `physical_table`    | SDM physical mapping                                  | **What we return**      |
| `sdm_context`       | SDM metadata                                          | Optional debugging only |

**Table Card Structure:**

```json
{
  "id": "table:sales_dw.cust_mstr",
  "type": "table",
  "text": "sales_dw cust_mstr Customers customer client buyer account master data contact info",

  "physical_table": "sales_dw.cust_mstr",
  "sdm_context": {
    "logical_name": "Customers",
    "description": "Customer master data including contact info",
    "synonyms": ["client", "buyer", "account"]
  }
}
```

**Column Card Structure:**

```json
{
  "id": "column:sales_dw.cust_mstr.cust_nm",
  "type": "column",
  "text": "cust_nm customer name full name buyer name sales_dw cust_mstr",

  "physical_column": "cust_nm",
  "physical_table": "sales_dw.cust_mstr",
  "data_type": "varchar",
  "sdm_context": {
    "logical_name": "Customer Name",
    "description": "Full customer name",
    "synonyms": ["buyer name"]
  }
}
```

**Metric Card Structure:**

```json
{
  "id": "metric:total_revenue",
  "type": "metric",
  "text": "total revenue sales sum amount gross revenue orders",

  "metric_name": "total_revenue",
  "physical_dependencies": [
    { "table": "sales_dw.orders", "column": "amount" },
    { "table": "sales_dw.orders", "column": "order_date" }
  ],
  "expression_hint": "SUM(orders.amount)",
  "sdm_context": {
    "logical_name": "Total Revenue",
    "description": "Sum of all order amounts",
    "synonyms": ["gross revenue", "total sales"]
  }
}
```

**Card Types Generated:**

| Card Type         | ID Format                                   | Returns                    | Closure Behavior                                 |
| ----------------- | ------------------------------------------- | -------------------------- | ------------------------------------------------ |
| Table card        | `table:{physical_table}`                    | Physical table name        | Membership                                       |
| Column card       | `column:{physical_table}.{physical_column}` | Physical column reference  | Membership                                       |
| Metric card       | `metric:{metric_name}`                      | Expression + physical deps | Metric closure: adds all `physical_dependencies` |
| Relationship card | `rel:{table1}:{table2}`                     | Physical join columns      | FK-key closure                                   |

**Card Generation:**

```python
def generate_table_card(sdm_table) -> Card:
    physical_name = sdm_table.physical_table
    searchable_text = " ".join([
        physical_name.replace(".", " "),
        sdm_table.logical_name or "",
        sdm_table.description or "",
        " ".join(sdm_table.synonyms or [])
    ])

    return Card(
        id=f"table:{physical_name}",
        type="table",
        text=searchable_text,
        physical_table=physical_name,
        sdm_context={
            "logical_name": sdm_table.logical_name,
            "description": sdm_table.description,
            "synonyms": sdm_table.synonyms
        }
    )

def generate_metric_card(sdm_metric) -> Card:
    # Extract physical dependencies from metric expression
    deps = parse_metric_dependencies(sdm_metric.expression)

    searchable_text = " ".join([
        sdm_metric.name,
        sdm_metric.logical_name or "",
        sdm_metric.description or "",
        " ".join(sdm_metric.synonyms or []),
        " ".join(d["table"] + " " + d["column"] for d in deps)
    ])

    return Card(
        id=f"metric:{sdm_metric.name}",
        type="metric",
        text=searchable_text,
        metric_name=sdm_metric.name,
        physical_dependencies=deps,
        expression_hint=sdm_metric.expression,
        sdm_context={
            "logical_name": sdm_metric.logical_name,
            "description": sdm_metric.description,
            "synonyms": sdm_metric.synonyms
        }
    )
```

**Acceptance Criteria:**

- [ ] Card IDs use physical names
- [ ] Searchable text includes: physical name + logical name + description + synonyms
- [ ] Cards return physical references
- [ ] Metric cards include `physical_dependencies` for metric closure
- [ ] Card generation is deterministic (same SDM → same cards)
- [ ] Cards indexed for BM25 search

**Performance:** < 30s for 500 tables

**LLM Usage:** None. SDM is the source of truth.

---

### Story A-3: Version and Cache Artifacts [Phase 2] ⚙️

> As an operator, I want artifacts versioned and cached per SDM version.

**Approach:** Deterministic caching logic.

**Acceptance Criteria:**

- [ ] Artifacts cached by `(sdm_id, sdm_version)`
- [ ] SDM update triggers regeneration
- [ ] Old artifacts serve during regeneration

---

## EPIC B: Access Control & Governance

**Goal:** Ensure zero schema leakage.

**Approach:** Fully deterministic. Security rules must not depend on LLM.

| Story              | Phase  | Approach         | LLM Calls |
| ------------------ | ------ | ---------------- | --------- |
| B-1: Policy filter | 1 or 3 | ⚙️ Deterministic | 0         |

---

### Story B-1: Policy / Entitlement Filter [Phase 1 or 3] ⚙️

> As a platform, I want **zero schema leakage** by filtering schema elements by user permissions.

**Phase flexibility:** Implement in Phase 1 if enterprise security is a launch requirement; otherwise Phase 3.

**Approach:** Rule-based filtering on **physical references**.

**Critical ordering rule (MUST):**

- Entitlements MUST be applied **before**:
  - any schema slice is returned,
  - any linking trace is logged (unless redacted),
  - any schema-related context is sent to an LLM.

**Acceptance Criteria:**

- [ ] Filter operates on physical table/column names
- [ ] Unauthorized elements never appear in output schema slices
- [ ] Unauthorized elements never appear in traces (except redacted counts)
- [ ] Retrieval results are filtered at query-time or index-time (preferred)
- [ ] If no permitted matches exist, return error with `code="entitlement_denied"` or empty slice with `confidence=0` and `reason="no_permitted_matches"`
- [ ] Policy evaluation is deterministic and auditable
- [ ] < 20ms latency (after cache warmup)

---

## EPIC C: Catalog Router

**Goal:** Route queries to correct databases/schemas.

| Story                   | Phase | Approach         | LLM Calls |
| ----------------------- | ----- | ---------------- | --------- |
| C-1: Database selection | 3     | ⚙️ Deterministic | 0         |

---

### Story C-1: Database/Schema Selection [Phase 3] ⚙️

> As a system, I want to route to the correct database before table linking.

**Approach:** BM25 + embedding search over database/schema cards (same physical-first approach).

**Acceptance Criteria:**

- [ ] Routes correctly 95%+ of time
- [ ] No LLM calls (retrieval-based)
- [ ] Returns physical database/schema identifiers
- [ ] Skipped for single-SDM deployments

**Performance:** < 300ms

---

## EPIC D: Schema Linking Engine (Tabular)

**Goal:** Core linking logic.

**Approach:** Fully deterministic. Retrieval + graph algorithms.

| Story                       | Phase | Approach         | LLM Calls |
| --------------------------- | ----- | ---------------- | --------- |
| D-1: Basic retrieval        | 1     | ⚙️ Deterministic | 0         |
| D-2: Basic refinement       | 1     | ⚙️ Deterministic | 0         |
| D-3: Two-stage linking      | 1     | ⚙️ Deterministic | 0         |
| D-4: Hybrid retrieval       | 2     | ⚙️ Deterministic | 0         |
| D-5: Bidirectional          | 2     | ⚙️ Deterministic | 0         |
| D-6: Connector minimization | 2     | ⚙️ Deterministic | 0         |

---

### Story D-1: Basic Retrieval Linker [Phase 1] ⚙️

> As a system, I want to search cards and return matching physical schema elements.

**Approach:** BM25 search. No LLM.

```python
class ColumnRef(BaseModel):
    table: str
    column: str

def link(question: str, parsed_query: ParsedQuery | None = None) -> SchemaSlice:
    raw_terms = parsed_query.search_terms if parsed_query else question
    search_terms = normalize_query(raw_terms)  # §5.4.1

    table_cards = bm25_search(table_index, search_terms, k=10)
    column_cards = bm25_search(column_index, search_terms, n=30)
    metric_cards = bm25_search(metric_index, search_terms, k=5)

    tables = [card.physical_table for card in table_cards]
    columns = [
        ColumnRef(table=card.physical_table, column=card.physical_column)
        for card in column_cards
    ]
    metrics = [card for card in metric_cards]

    return SchemaSlice(tables, columns, metrics, confidence)
```

**Acceptance Criteria:**

- [ ] Returns physical table/column names
- [ ] Works without any LLM calls
- [ ] Confidence score (0-1)

**Performance:** < 200ms

---

### Story D-2: Basic Refinement [Phase 1] ⚙️

> As a system, I want to ensure selected tables can be joined.

**Approach:** Graph algorithms on physical table graph.

**Acceptance Criteria:**

- [ ] Membership closure: add tables containing selected columns
- [ ] FK-key closure: add columns needed for joins
- [ ] Metric closure: add tables/columns referenced by selected metrics
- [ ] All references are physical

---

### Story D-3: Two-Stage Linking [Phase 1] ⚙️

> As a system, I want to first narrow to tables, then find relevant columns.

**Algorithm:**

```python
def two_stage_link(question: str) -> SchemaSlice:
    table_cards = bm25_search(table_index, question, k=10)
    candidate_tables = [card.physical_table for card in table_cards]

    column_cards = bm25_search(
        column_index,
        question,
        table_filter=candidate_tables
    )

    return SchemaSlice(tables=candidate_tables, columns=column_cards)
```

---

### Story D-4: Hybrid Retrieval [Phase 2] ⚙️

> As a system, I want to combine BM25 and embedding search.

**Approach:** RRF fusion of BM25 + embedding scores. Still returns physical references.

---

### Story D-5: Bidirectional Retrieval [Phase 2] ⚙️

> As a system, I want to search both table-first and column-first.

**Approach:** Two retrieval paths, merged via RRF.

---

### Story D-6: Connector Minimization (Greedy) [Phase 2] ⚙️

> As a system, I want to add **minimal connector tables** so selected tables can be joined.

**Approach:** Greedy connect-to-component using BFS shortest-path attachment (see §5.4.3).

**Algorithm (summary):**

1. Seed with the highest-scoring terminal table
2. Repeatedly attach the nearest remaining terminal via shortest join path to the connected component
3. Add all tables on each path to the connected set
4. Deterministic tie-breaks: path length → score → lexical

**Acceptance Criteria:**

- [ ] Connectors are **physical table names**
- [ ] Join paths use **physical column references**
- [ ] Output is deterministic and idempotent
- [ ] If no path exists, return `connectivity="disconnected"` with `components` + `missing_links`
- [ ] < 50ms for ~500 tables (excluding graph load)

---

## EPIC E: Agentic Enhancement

**Goal:** Use LLM to improve linking quality where it genuinely helps.

| Story                                 | Phase | Approach         | LLM Calls | When              |
| ------------------------------------- | ----- | ---------------- | --------- | ----------------- |
| E-1: Query understanding              | 2     | 🤖 LLM           | 1         | Every request     |
| E-2: Recovery loop                    | 2     | 🤖 LLM           | 1-2       | Low confidence    |
| E-3: Ambiguity resolution             | 3     | 🤖 LLM           | 1         | When ambiguous    |
| E-4a: Cross-SDM suggestions (offline) | 3     | ⚙️ Deterministic | 0         | SDM update        |
| E-4b: Cross-SDM hints (runtime)       | 3     | ⚙️ Deterministic | 0         | Multi-SDM queries |

**Policy:** No within-SDM join inference at runtime. Within-SDM relationships must be explicit.

---

### Story E-1: Query Understanding (Schema-Agnostic) [Phase 2] 🤖

> As a system, I want to extract structured information from the natural language question.

**Hard boundary:** LLM **must not** output schema identifiers. Outputs only search signals.

**Input:**

- `question`
- `conversation_history` (optional, for context)
- `domain_glossary` (optional, small)

**Output:**

```python
class FilterHint(BaseModel):
    field_hint: str
    op: str
    value: int | str

class ParsedQuery(BaseModel):
    search_tokens: list[str]
    entities: list[str] = []
    metrics: list[str] = []
    filters: list[FilterHint] = []

ParsedQuery(
    search_tokens=["sales", "revenue", "customer", "by", "month"],
    entities=["customer"],
    metrics=["sales"],
    filters=[FilterHint(field_hint="date", op="last_n_months", value=12)],
)
```

---

### Story E-2: Recovery Loop [Phase 2] 🤖

> As a system, I want to recover from low-confidence linking.

**Trigger:** Confidence < 0.6 OR connectivity = "disconnected"

```python
def link_with_recovery(question: str, max_rounds: int = 2) -> SchemaSlice:
    result = link(question)

    for round in range(max_rounds):
        if result.confidence >= 0.6 and result.connectivity == "connected":
            break

        rewritten = llm_rewrite_query(question, result)
        result2 = link(rewritten.query)
        result = merge_results(result, result2)

    return result
```

---

### Story E-3: Ambiguity Resolution [Phase 3] 🤖

> As a system, I want to handle questions with multiple valid interpretations.

**LLM ranks interpretations**, each is a schema slice with physical refs.

---

### Story E-4a: Cross-SDM Relationship Suggestions (Offline) [Phase 3] ⚙️

> As a system, I want to propose candidate cross-SDM relationships for human review.

**Scope:** Offline job only. Not used to force connectivity at runtime.

**Acceptance Criteria:**

- [ ] Produces candidates with evidence and confidence
- [ ] Candidates enter review/approval workflow
- [ ] Approved edges stored as explicit `cross_relationship` artifacts
- [ ] Rejected edges remembered to avoid re-suggesting

---

### Story E-4b: Cross-SDM Join Hints (Runtime) [Phase 3] ⚙️

> As a system, I want to return hint-only cross-SDM join candidates.

**Rules:**

- Hints are **never** treated as guaranteed join edges
- Hints **must not** be used to claim `connectivity="connected"`
- Hints are filtered by entitlements

---

## EPIC F: Fallback & Confidence

| Story                   | Phase | Approach         | LLM Calls |
| ----------------------- | ----- | ---------------- | --------- |
| F-0: Confidence scoring | 1     | ⚙️ Deterministic | 0         |
| F-1: Simple fallback    | 1     | ⚙️ Deterministic | 0         |

---

### Story F-0: Confidence Scoring [Phase 1] ⚙️

> As a system, I want a deterministic confidence score for gating.

**Definition:** See §5.4.4.

**Acceptance Criteria:**

- [ ] Confidence is in [0, 1]
- [ ] Deterministic for identical inputs
- [ ] Decreases when disconnected
- [ ] Breakdown available in traces

---

### Story F-1: Simple Fallback [Phase 1] ⚙️

> As a system, I want to return "no confident matches" gracefully.

**Acceptance Criteria:**

- [ ] Returns empty slice with confidence = 0
- [ ] Provides reason for failure
- [ ] Uses error contract (§5.5) if appropriate

---

## EPIC G: Output & Observability

| Story              | Phase | Approach         | LLM Calls |
| ------------------ | ----- | ---------------- | --------- |
| G-1: Schema slice  | 1     | ⚙️ Deterministic | 0         |
| G-2: Linking trace | 2     | ⚙️ Deterministic | 0         |

---

### Story G-1: Schema Slice Output [Phase 1] ⚙️

> As a system, I want to output a schema slice with physical references.

**Output Format:**

```yaml
schema_slice:
  limits:
    max_tables: 10
    max_columns_per_table: 25
    max_total_columns: 80
  truncated: false

  tables:
    - table: 'sales_dw.cust_mstr'
      columns:
        - column: 'cust_id'
          type: integer
          primary_key: true
        - column: 'cust_nm'
          type: varchar

    - table: 'sales_dw.orders'
      columns:
        - column: 'order_id'
          type: integer
          primary_key: true
        - column: 'cust_id'
          type: integer
        - column: 'amount'
          type: decimal

  joins:
    - from: 'sales_dw.cust_mstr.cust_id'
      to: 'sales_dw.orders.cust_id'
      type: 'inner'

  metrics:
    - name: 'total_revenue'
      expression: 'SUM(sales_dw.orders.amount)'

  connectivity: 'connected'
  components: []
  missing_links: []

  confidence: 0.85
  cross_sdm_join_hints: []
```

**Acceptance Criteria:**

- [ ] All names are physical
- [ ] Includes `limits` + `truncated` flags
- [ ] If disconnected, includes `components` and `missing_links`
- [ ] Generator can use directly for SQL

---

### Story G-2: Linking Trace [Phase 2] ⚙️

**Traces redacted by default. Admin mode via `X-Debug-Trace: full` header (requires admin entitlement).**

```yaml
trace:
  input:
    question: 'Show sales by customer'

  query_understanding:
    extracted:
      entities: ['customer']
      metrics: ['sales']

  retrieval:
    method: 'hybrid_bidirectional'
    matches:
      - card_id: 'table:sales_dw.cust_mstr'
        score: 0.89
      - card_id: 'table:sales_dw.orders'
        score: 0.76

  refinement:
    algorithm: 'steiner_approximation'
    connectors_added: []

  confidence_breakdown:
    table_conf: 0.88
    col_conf: 0.82
    conn_factor: 1.0
    final: 0.85

  output:
    tables: ['sales_dw.cust_mstr', 'sales_dw.orders']
    confidence: 0.85
```

---

## EPIC H: Hierarchical Schema Linking

| Story                  | Phase | Approach         | LLM Calls |
| ---------------------- | ----- | ---------------- | --------- |
| H-1: JSON Schema Cards | 2.1   | ⚙️ Deterministic | 0         |

---

### Story H-1: JSON Schema Cards [Phase 2.1] ⚙️

**Card for nested field:**

```json
{
  "id": "field:events.user.address.city",
  "type": "field",
  "text": "city user address location events",
  "physical_path": "events.user.address.city",
  "data_type": "string",
  "sdm_context": {
    "logical_name": "User City",
    "description": "City from user address"
  }
}
```

---

## EPIC I: Cross-Domain Linking

| Story                 | Phase | Approach         | LLM Calls |
| --------------------- | ----- | ---------------- | --------- |
| I-1: Unified SQL + JQ | 4     | ⚙️ Deterministic | 0         |

---

## 7. Summary: Physical vs SDM

| Aspect         | Source   | Used For                                    |
| -------------- | -------- | ------------------------------------------- |
| Physical names | Database | Card IDs, output references, SQL generation |
| Synonyms       | SDM      | Search enrichment (in card text)            |
| Descriptions   | SDM      | Search enrichment (in card text)            |
| Logical names  | SDM      | Search enrichment, optional debugging       |
| Relationships  | SDM      | Join graph (stored with physical refs)      |

**SDM = search quality booster, not the source of truth for identifiers.**

---

## 8. Cost Estimation

### Per-Request Cost (Phase 2+)

| Component                  | LLM Calls | Tokens (approx)   | Cost @ GPT-4o-mini    |
| -------------------------- | --------- | ----------------- | --------------------- |
| Query understanding        | 1         | ~500 in, ~200 out | $0.0001               |
| Recovery (10% of requests) | 0.1-0.2   | ~800 in, ~300 out | $0.00005              |
| **Total average**          | **~1.2**  | **~600**          | **~$0.00015/request** |

---

## 9. Requirements Summary

### By Phase

| Phase | Stories                                                |
| ----- | ------------------------------------------------------ |
| 1     | A-1, A-2, D-1, D-2, D-3, F-0, F-1, G-1, (B-1 optional) |
| 2     | A-3, D-4, D-5, D-6, E-1, E-2, G-2                      |
| 2.1   | H-1                                                    |
| 3     | B-1 (if not Phase 1), C-1, E-3, E-4a, E-4b             |
| 4     | I-1                                                    |

### Non-Functional Requirements

| ID    | Requirement          | Target            |
| ----- | -------------------- | ----------------- |
| NFR-1 | Latency without LLM  | < 200ms           |
| NFR-2 | Latency with LLM     | < 700ms typical   |
| NFR-3 | LLM failure handling | Graceful fallback |
| NFR-4 | LLM cost per request | < $0.001          |

---

## 10. Summary: What Uses LLM

| Component           | LLM?   | Phase  | Calls |
| ------------------- | ------ | ------ | ----- |
| Card generation     | **No** | 1      | 0     |
| Query understanding | Yes    | 2+     | 1     |
| Retrieval           | No     | All    | 0     |
| Refinement          | No     | All    | 0     |
| Recovery            | Yes    | 2+     | 1-2   |
| Ambiguity           | Yes    | 3+     | 1     |
| Policy filter       | No     | 1 or 3 | 0     |

**Phase 1: Zero LLM calls** — fully deterministic, BM25 only  
**Phase 2+: 1-2 LLM calls typical**, ~$0.00015/request
