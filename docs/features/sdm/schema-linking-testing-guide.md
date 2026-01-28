# Schema Linking Testing & Validation Guide

**Date:** 2026-01-22  
**Purpose:** Validate schema linking efficacy using BIRD benchmark  
**Related:** [Specification](./schema-linking-specification.md) | [Architecture](./schema-linking-architecture.md)

---

## Table of Contents

1. [Overview](#overview)
2. [Story-to-Test Coverage Matrix](#story-to-test-coverage-matrix)
3. [Component Tests](#component-tests)
4. [Performance Validation](#performance-validation)
5. [Enhancement Feature Tests](#enhancement-feature-tests)
6. [Guardrail Tests](#guardrail-tests)
7. [End-to-End Validation (BIRD)](#end-to-end-validation-bird)
8. [Metrics Collection](#metrics-collection)
9. [Success Criteria](#success-criteria)
10. [Troubleshooting](#troubleshooting)
11. [Continuous Monitoring](#continuous-monitoring)

---

## Overview

This guide explains how to measure the impact of schema linking on NL2SQL accuracy, latency, and token usage using the BIRD benchmark.

**Testing Levels:**

- **Component tests:** Validate individual stories (graph generation, card indexing, refinement)
- **Performance tests:** Verify architecture latency targets
- **Integration tests:** End-to-end BIRD benchmark runs (baseline vs treatment)

**Capability Modes:**

- **Embeddings enabled:** Hybrid retrieval (BM25 + embeddings)
- **Embeddings disabled:** BM25-only retrieval (required for SQLite-only environments)

Run the key performance and integration tests in both modes to validate capability gating behavior.

---

## Story-to-Test Coverage Matrix

This table maps each user story to its test coverage. Use this to ensure all stories are validated.

### Feature Availability Test Matrix

Run key tests in each capability mode to validate gating behavior.

| Capability Mode              | Required Tests                      | Expected Outcome                                    |
| ---------------------------- | ----------------------------------- | --------------------------------------------------- |
| **Postgres + pgvector**      | Full component + performance + BIRD | Baseline targets met with hybrid retrieval          |
| **Postgres (no embeddings)** | Performance + BIRD (BM25-only)      | Slight recall drop, latency within target           |
| **SQLite-only**              | Component + BIRD (BM25-only)        | BM25-only behavior, feature degraded but functional |

### Epic A: Build and Persist Schema Graphs + Routing Artifacts

| Story | Description                 | Test Type          | Test Location                                                    |
| ----- | --------------------------- | ------------------ | ---------------------------------------------------------------- |
| A-1   | Derive Graph from SDM       | Unit               | [Component Tests: Graph Generation](#a-1-graph-generation-tests) |
| A-2   | Version and Cache Artifacts | Unit + Integration | [Component Tests: Artifact Caching](#a-2-artifact-caching-tests) |
| A-3   | Generate SDM Cards          | Unit               | [Component Tests: Card Generation](#a-3-card-generation-tests)   |

### Epic B: Schema Linking Engine

| Story | Description                | Test Type          | Test Location                                                        |
| ----- | -------------------------- | ------------------ | -------------------------------------------------------------------- |
| B-1   | Baseline Retrieval Linker  | Integration        | [BIRD Validation](#end-to-end-validation-bird)                       |
| B-2   | Learned Linking (Optional) | Integration        | Deferred to Phase 5                                                  |
| B-3   | Two-Stage Linker           | Unit + Performance | [Performance: Two-Stage Retrieval](#two-stage-retrieval-performance) |
| B-4   | Deterministic Refinement   | Unit               | [Component Tests: Refinement](#b-4-deterministic-refinement-tests)   |

### Epic C: Prompt Pruning and NL2SQL Integration

| Story | Description             | Test Type   | Test Location                                     |
| ----- | ----------------------- | ----------- | ------------------------------------------------- |
| C-1   | Pruned Schema Prompting | Integration | [Metrics: Token Reduction](#3-prompt-token-count) |
| C-2   | Low-Confidence Fallback | Integration | [Metrics: Fallback Rate](#5-fallback-rate)        |

### Epic D: Evaluation and Observability

| Story | Description     | Test Type   | Test Location                             |
| ----- | --------------- | ----------- | ----------------------------------------- |
| D-1   | Linking Metrics | Integration | [Metrics Collection](#metrics-collection) |

### Epic E: Operations and Maintenance

| Story | Description     | Test Type   | Test Location                                             |
| ----- | --------------- | ----------- | --------------------------------------------------------- |
| E-1   | SDM Update Hook | Integration | [Component Tests: SDM Update](#e-1-sdm-update-hook-tests) |

### Epic F: Semantic-Layer Inbound Query Translation (Optional)

| Story | Description              | Test Type | Test Location |
| ----- | ------------------------ | --------- | ------------- |
| F-1   | Inbound Query Generation | —         | Future work   |
| F-2   | Query Engine Compilation | —         | Future work   |

### Epic G: Schema Linking Enhancements

| Story | Description                      | Test Type          | Test Location                                                           |
| ----- | -------------------------------- | ------------------ | ----------------------------------------------------------------------- |
| G-1   | Schema Metadata Enrichment       | Unit               | [Enhancement Tests: Metadata](#g-1-metadata-enrichment-tests)           |
| G-2   | Matched Value Retrieval          | Unit + Integration | [Enhancement Tests: Value Matching](#g-2-value-matching-tests)          |
| G-3   | Demonstration Retrieval          | Unit + Integration | [Enhancement Tests: Demo Retrieval](#g-3-demonstration-retrieval-tests) |
| G-4   | Question Decomposition           | Unit               | [Enhancement Tests: Decomposition](#g-4-question-decomposition-tests)   |
| G-5   | Schema Enrichment Beyond Minimal | Unit               | [Enhancement Tests: Enrichment](#g-5-schema-enrichment-tests)           |
| G-6   | Verified Query Anchoring         | Integration        | [Enhancement Tests: Anchoring](#g-6-verified-query-anchoring-tests)     |
| G-7   | SQL Skeleton Demo Selection      | Unit               | [Enhancement Tests: Skeleton Selection](#g-7-skeleton-selection-tests)  |
| G-8   | Query Rewrite (Conditional)      | Integration        | [Enhancement Tests: Rewrite](#g-8-query-rewrite-tests)                  |
| G-9   | Multi-Sample Union (Conditional) | Integration        | [Enhancement Tests: Multi-Sample](#g-9-multi-sample-tests)              |

### Epic H: Guardrails and Optimization

| Story | Description                     | Test Type          | Test Location                                                                  |
| ----- | ------------------------------- | ------------------ | ------------------------------------------------------------------------------ |
| H-1   | Extractive Selection Constraint | Unit               | [Guardrail Tests: Extractive Constraint](#h-1-extractive-selection-constraint) |
| H-2   | Repair Loop on Execution Error  | Integration        | [Guardrail Tests: Repair Loop](#h-2-repair-loop-on-execution-error)            |
| H-3   | Complexity Classifier (SLM)     | Unit               | [Guardrail Tests: Complexity](#h-3-complexity-classifier)                      |
| H-4   | SLM Reranker                    | Unit + Integration | [Guardrail Tests: Reranker](#h-4-slm-reranker)                                 |
| H-5   | Learned Confidence Calibration  | Unit               | [Guardrail Tests: Confidence](#h-5-confidence-calibration)                     |

---

## Component Tests

These unit tests validate individual stories in isolation. Run these before integration tests.

```bash
# Run all component tests
uv run --project agent_platform_server pytest tests/schema_linking/ -v

# Run specific epic
uv run --project agent_platform_server pytest tests/schema_linking/test_graph.py -v
```

### A-1: Graph Generation Tests

**Purpose:** Validate that schema graphs are correctly derived from SDM definitions.

**Test file:** `tests/schema_linking/test_graph.py`

```python
class TestGraphGeneration:
    """Story A-1: Derive Graph from SDM"""

    def test_tables_become_nodes(self, sample_sdm):
        """All SDM tables appear as graph nodes."""
        graph = build_schema_graph(sample_sdm)

        for table in sample_sdm.tables:
            node_id = f"table:{sample_sdm.id}:{table.name}"
            assert node_id in graph.nodes
            assert graph.nodes[node_id].node_type == "table"

    def test_fields_become_nodes_with_parent(self, sample_sdm):
        """All SDM fields appear as nodes connected to parent tables."""
        graph = build_schema_graph(sample_sdm)

        for table in sample_sdm.tables:
            for field in table.fields:
                node_id = f"field:{sample_sdm.id}:{table.name}:{field.name}"
                assert node_id in graph.nodes
                assert graph.nodes[node_id].parent_table == table.name

    def test_relationships_become_edges(self, sample_sdm):
        """All SDM relationships appear as graph edges."""
        graph = build_schema_graph(sample_sdm)

        for rel in sample_sdm.relationships:
            # Find edge between source and target tables
            source_id = f"table:{sample_sdm.id}:{rel.source_table}"
            target_id = f"table:{sample_sdm.id}:{rel.target_table}"

            edge = next(
                (e for e in graph.edges
                 if e.source_node_id == source_id and e.target_node_id == target_id),
                None
            )
            assert edge is not None
            assert edge.join_keys == rel.join_keys

    def test_self_referential_relationship(self):
        """Self-joins create valid edges (e.g., employee → manager)."""
        sdm = create_sdm_with_self_reference()
        graph = build_schema_graph(sdm)

        employee_id = f"table:{sdm.id}:employees"
        self_edge = next(
            (e for e in graph.edges
             if e.source_node_id == employee_id and e.target_node_id == employee_id),
            None
        )
        assert self_edge is not None

    def test_composite_foreign_key(self):
        """Composite keys are captured in a single edge."""
        sdm = create_sdm_with_composite_fk()
        graph = build_schema_graph(sdm)

        edge = graph.get_edge_between("orders", "order_details")
        assert len(edge.join_keys) == 2  # Two column pairs

    def test_isolated_table_included(self):
        """Tables with no relationships are included as isolated nodes."""
        sdm = create_sdm_with_isolated_table()
        graph = build_schema_graph(sdm)

        isolated_id = f"table:{sdm.id}:audit_log"
        assert isolated_id in graph.nodes
        assert graph.get_neighbors(isolated_id) == []

    def test_graph_serialization_roundtrip(self, sample_sdm):
        """Graph can be serialized to JSON and loaded without data loss."""
        graph = build_schema_graph(sample_sdm)

        serialized = graph.model_dump_json()
        restored = SchemaGraph.model_validate_json(serialized)

        assert restored.nodes == graph.nodes
        assert restored.edges == graph.edges
```

### A-2: Artifact Caching Tests

**Purpose:** Validate artifact versioning and cache invalidation.

**Test file:** `tests/schema_linking/test_artifact_cache.py`

```python
class TestArtifactCaching:
    """Story A-2: Version and Cache Artifacts"""

    def test_artifacts_keyed_by_version(self, artifact_store):
        """Different SDM versions produce separate cached artifacts."""
        sdm_v1 = create_sdm(version="v1.0")
        sdm_v2 = create_sdm(version="v2.0")

        artifact_store.generate_and_store(sdm_v1)
        artifact_store.generate_and_store(sdm_v2)

        assert artifact_store.get(sdm_v1.id, "v1.0") is not None
        assert artifact_store.get(sdm_v1.id, "v2.0") is not None
        assert artifact_store.get(sdm_v1.id, "v1.0") != artifact_store.get(sdm_v1.id, "v2.0")

    def test_cache_hit_returns_existing(self, artifact_store):
        """Repeated requests return cached artifacts without regeneration."""
        sdm = create_sdm()

        artifact_store.generate_and_store(sdm)
        first_call = artifact_store.get(sdm.id, sdm.version)
        second_call = artifact_store.get(sdm.id, sdm.version)

        assert first_call is second_call  # Same object reference

    def test_stale_cache_detection(self, artifact_store):
        """Cache detects when SDM has changed and needs regeneration."""
        sdm = create_sdm()
        artifact_store.generate_and_store(sdm)

        # Simulate SDM change (new version)
        sdm.version = "v1.1"

        assert artifact_store.is_stale(sdm.id, "v1.0", sdm.version)
```

### A-3: Card Generation Tests

**Purpose:** Validate that SDM cards are correctly generated for retrieval.

**Test file:** `tests/schema_linking/test_cards.py`

```python
class TestCardGeneration:
    """Story A-3: Generate SDM Cards"""

    def test_table_card_content(self, sample_sdm):
        """Table cards include name, description, and synonyms."""
        cards = generate_cards(sample_sdm)

        table_cards = [c for c in cards if c.card_type == "table"]
        assert len(table_cards) == len(sample_sdm.tables)

        for card in table_cards:
            assert card.name in card.text
            assert card.description in card.text

    def test_field_card_metadata(self, sample_sdm):
        """Field cards include type, PK/FK flags, and parent table."""
        cards = generate_cards(sample_sdm)

        field_cards = [c for c in cards if c.card_type == "field"]
        for card in field_cards:
            assert card.metadata.get("parent_table") is not None
            assert card.metadata.get("data_type") is not None

    def test_card_ids_are_stable(self, sample_sdm):
        """Card IDs are deterministic for the same SDM."""
        cards1 = generate_cards(sample_sdm)
        cards2 = generate_cards(sample_sdm)

        ids1 = {c.id for c in cards1}
        ids2 = {c.id for c in cards2}

        assert ids1 == ids2

    def test_verified_query_cards(self, sample_sdm_with_verified_queries):
        """Verified query cards include NLQ, SQL skeleton, and referenced elements."""
        cards = generate_cards(sample_sdm_with_verified_queries)

        vq_cards = [c for c in cards if c.card_type == "verified_query"]
        assert len(vq_cards) > 0

        for card in vq_cards:
            assert "nlq" in card.text.lower() or card.metadata.get("nlq")
            assert card.metadata.get("referenced_tables") is not None
```

### B-4: Deterministic Refinement Tests

**Purpose:** Validate FK-path closure, FK-key closure, and table membership closure.

**Test file:** `tests/schema_linking/test_refinement.py`

```python
class TestDeterministicRefinement:
    """Story B-4: Deterministic Refinement"""

    def test_fk_path_closure_adds_bridge_tables(self, sample_graph):
        """FK-path closure adds intermediate tables to connect disconnected tables."""
        # orders → customers (direct)
        # orders → products (needs order_items bridge)
        linked_tables = {"orders", "products"}

        refined = fk_path_closure(linked_tables, sample_graph)

        assert "order_items" in refined  # Bridge table added

    def test_fk_key_closure_adds_join_columns(self, sample_graph):
        """FK-key closure adds join key fields for all relationships."""
        linked_tables = {"orders", "customers"}

        refined_fields = fk_key_closure(linked_tables, sample_graph)

        assert "orders.customer_id" in refined_fields
        assert "customers.id" in refined_fields

    def test_table_membership_closure(self, sample_graph):
        """Table membership closure adds parent tables for orphaned fields."""
        linked_fields = {"order_items.quantity", "order_items.price"}
        linked_tables = set()  # No tables explicitly linked

        refined_tables = table_membership_closure(linked_fields, linked_tables, sample_graph)

        assert "order_items" in refined_tables

    def test_refinement_handles_cycles(self, graph_with_cycles):
        """Refinement handles circular relationships without infinite loops."""
        linked_tables = {"table_a", "table_c"}

        # Should complete without hanging
        refined = fk_path_closure(linked_tables, graph_with_cycles)

        assert "table_b" in refined  # Bridge added

    def test_refinement_preserves_original_selection(self, sample_graph):
        """Refinement never removes originally selected elements."""
        original_tables = {"orders", "customers"}

        refined = fk_path_closure(original_tables.copy(), sample_graph)

        assert original_tables.issubset(refined)
```

### E-1: SDM Update Hook Tests

**Purpose:** Validate that artifact regeneration triggers correctly when SDM changes.

**Test file:** `tests/schema_linking/test_sdm_update.py`

```python
class TestSdmUpdateHook:
    """Story E-1: SDM Update Hook"""

    async def test_sdm_update_triggers_regeneration(self, artifact_store, sdm_service):
        """SDM update triggers background artifact regeneration."""
        sdm = create_sdm(version="v1.0")
        await artifact_store.generate_and_store(sdm)

        # Update SDM
        sdm.version = "v1.1"
        await sdm_service.update(sdm)

        # Verify regeneration was triggered
        new_artifacts = await artifact_store.get(sdm.id, "v1.1")
        assert new_artifacts is not None

    async def test_queries_use_old_artifacts_during_regeneration(
        self, artifact_store, linking_service
    ):
        """In-flight queries continue using old artifacts during regeneration."""
        sdm = create_sdm(version="v1.0")
        await artifact_store.generate_and_store(sdm)

        # Start regeneration (background)
        regeneration_task = asyncio.create_task(
            artifact_store.regenerate(sdm.id, "v1.1")
        )

        # Query during regeneration should use v1.0
        result = await linking_service.link("Show all orders", sdm.id)
        assert result.artifact_version == "v1.0"

        await regeneration_task

    async def test_atomic_artifact_swap(self, artifact_store):
        """Artifact swap is atomic—no partial state visible."""
        sdm = create_sdm(version="v1.0")
        await artifact_store.generate_and_store(sdm)

        # Regenerate
        await artifact_store.regenerate(sdm.id, "v1.1")

        # Should see complete v1.1, not partial
        artifacts = await artifact_store.get(sdm.id, "v1.1")
        assert artifacts.graph is not None
        assert artifacts.cards is not None
        assert artifacts.indexes is not None
```

---

## Performance Validation

These tests verify that the implementation meets architecture latency targets.

```bash
# Run performance tests
uv run --project agent_platform_server pytest tests/schema_linking/test_performance.py -v --benchmark
```

### Graph Loading Performance

**Target:** < 100ms for 500-table SDM (Story A-1)

```python
class TestGraphPerformance:
    """Performance tests for graph operations."""

    @pytest.mark.benchmark
    def test_graph_load_500_tables(self, large_sdm_500_tables, benchmark):
        """Graph loading completes in < 100ms for 500-table SDM."""
        # Pre-generate and store graph
        graph_json = build_schema_graph(large_sdm_500_tables).model_dump_json()

        result = benchmark(SchemaGraph.model_validate_json, graph_json)

        assert benchmark.stats["mean"] < 0.100  # 100ms

    @pytest.mark.benchmark
    def test_shortest_path_500_tables(self, large_graph_500_tables, benchmark):
        """Shortest path query completes in < 10ms for 500-table graph."""
        result = benchmark(
            large_graph_500_tables.shortest_join_path,
            "table:sdm:table_001",
            "table:sdm:table_499"
        )

        assert benchmark.stats["mean"] < 0.010  # 10ms
```

### Artifact Cache Loading Performance

**Target:** < 500ms for 500-table SDM (Story A-2)

```python
@pytest.mark.benchmark
def test_artifact_cache_load_500_tables(self, artifact_store, large_sdm, benchmark):
    """Artifact cache loading completes in < 500ms."""
    # Pre-populate cache in DB
    artifact_store.generate_and_store(large_sdm)
    artifact_store.clear_memory_cache()

    result = benchmark(artifact_store.load_to_memory, large_sdm.id, large_sdm.version)

    assert benchmark.stats["mean"] < 0.500  # 500ms
```

### Two-Stage Retrieval Performance

**Target:** 2x faster than single-stage for 1000+ fields (Story B-3)

```python
@pytest.mark.benchmark
def test_two_stage_vs_single_stage(self, large_sdm_1000_fields, benchmark):
    """Two-stage retrieval is faster than single-stage for large schemas."""
    query = "Show total revenue by customer"

    # Single-stage timing
    single_stage_time = benchmark(
        single_stage_retrieval,
        query,
        large_sdm_1000_fields,
        k=50
    )

    # Two-stage timing
    two_stage_time = benchmark(
        two_stage_retrieval,
        query,
        large_sdm_1000_fields,
        k_broad=100,
        k_narrow=50
    )

    # Two-stage should be at least 1.5x faster (allowing margin)
    assert two_stage_time.stats["mean"] < single_stage_time.stats["mean"] * 0.67
```

### Deterministic Refinement Performance

**Target:** < 50ms (Story B-4)

```python
@pytest.mark.benchmark
def test_refinement_latency(self, large_graph_500_tables, benchmark):
    """Deterministic refinement completes in < 50ms."""
    linked_tables = {"table_001", "table_050", "table_200", "table_400"}

    result = benchmark(
        deterministic_refinement,
        linked_tables,
        large_graph_500_tables
    )

    assert benchmark.stats["mean"] < 0.050  # 50ms
```

### End-to-End Linking Performance

**Target:** < 500ms excluding embedding API (Specification)

```python
@pytest.mark.benchmark
def test_end_to_end_linking_latency(self, linking_service, sample_sdm, benchmark):
    """End-to-end linking completes in < 500ms (excluding embedding API)."""
    query = "Show all orders with customer names and product details"

    # Mock embedding API to isolate linking latency
    with mock_embedding_api(latency=0):
        result = benchmark(
            linking_service.link,
            query,
            sample_sdm.id
        )

    assert benchmark.stats["mean"] < 0.500  # 500ms
```

```python
@pytest.mark.benchmark
def test_end_to_end_linking_latency_bm25_only(self, linking_service, sample_sdm, benchmark):
    """End-to-end linking completes in < 500ms with embeddings disabled."""
    query = "Show all orders with customer names and product details"

    result = benchmark(
        linking_service.link,
        query,
        sample_sdm.id,
        embeddings_enabled=False
    )

    assert benchmark.stats["mean"] < 0.500  # 500ms
```

---

## Enhancement Feature Tests

These tests validate optional G-series enhancement features. Run when features are enabled.

```bash
# Run with enhancement features enabled
ENABLE_VALUE_MATCHING=true ENABLE_DEMO_RETRIEVAL=true \
  uv run --project agent_platform_server pytest tests/schema_linking/test_enhancements.py -v
```

### G-1: Metadata Enrichment Tests

```python
class TestMetadataEnrichment:
    """Story G-1: Schema Metadata Enrichment"""

    def test_sample_values_included(self, enriched_cards):
        """Field cards include sample values for context."""
        field_cards = [c for c in enriched_cards if c.card_type == "field"]

        for card in field_cards:
            if card.metadata.get("is_enum"):
                assert card.metadata.get("sample_values") is not None

    def test_business_glossary_terms_included(self, enriched_cards, glossary):
        """Cards include linked business glossary terms."""
        # Find card for 'revenue' field
        revenue_card = next(c for c in enriched_cards if "revenue" in c.name.lower())

        assert glossary.get_term("revenue") in revenue_card.text
```

### G-2: Value Matching Tests

```python
class TestValueMatching:
    """Story G-2: Matched Value Retrieval"""

    def test_value_match_boosts_field(self, linking_service, sdm_with_values):
        """Literal values in query boost matching fields."""
        # Query mentions specific customer name
        result = linking_service.link(
            "Show orders for customer 'Acme Corp'",
            sdm_with_values.id
        )

        # customer_name field should be highly ranked
        customer_name_score = result.get_field_score("customers.name")
        assert customer_name_score > 0.8

    def test_value_match_latency(self, linking_service, sdm_with_values, benchmark):
        """Value matching adds < 200ms latency."""
        query = "Show orders for 'Acme Corp'"

        result = benchmark(linking_service.link, query, sdm_with_values.id)

        assert result.metadata["value_match_latency_ms"] < 200
```

### G-3: Demonstration Retrieval Tests

```python
class TestDemoRetrieval:
    """Story G-3: Demonstration Retrieval"""

    def test_similar_query_retrieves_demo(self, linking_service, sdm_with_verified_queries):
        """Similar NL query retrieves verified query as demonstration."""
        # Verified query: "Show monthly revenue by region"
        result = linking_service.link(
            "Display revenue per month grouped by territory",  # Similar
            sdm_with_verified_queries.id
        )

        assert len(result.demonstrations) > 0
        assert "monthly revenue" in result.demonstrations[0].nlq.lower()

    def test_demo_retrieval_latency(self, linking_service, sdm_with_verified_queries, benchmark):
        """Demo retrieval adds < 300ms latency."""
        query = "Show sales by product category"

        result = benchmark(linking_service.link, query, sdm_with_verified_queries.id)

        assert result.metadata["demo_retrieval_latency_ms"] < 300
```

### G-4: Question Decomposition Tests

```python
class TestQuestionDecomposition:
    """Story G-4: Question Decomposition"""

    def test_complex_query_decomposed(self, decomposition_service):
        """Complex queries are decomposed into sub-questions."""
        complex_query = (
            "Show the top 5 customers by total revenue in Q4 2025, "
            "along with their average order value and most purchased product category"
        )

        sub_questions = decomposition_service.decompose(complex_query)

        assert len(sub_questions) >= 2
        assert any("revenue" in sq.lower() for sq in sub_questions)
        assert any("order value" in sq.lower() for sq in sub_questions)

    def test_simple_query_not_decomposed(self, decomposition_service):
        """Simple queries are not unnecessarily decomposed."""
        simple_query = "Show all customers"

        sub_questions = decomposition_service.decompose(simple_query)

        assert len(sub_questions) == 1
        assert sub_questions[0] == simple_query
```

### G-5: Schema Enrichment Tests

```python
class TestSchemaEnrichment:
    """Story G-5: Schema Enrichment Beyond Minimal Set"""

    def test_sibling_fields_added(self, linking_service, sample_sdm):
        """Sibling fields from same table are added for context."""
        result = linking_service.link(
            "Show order total",
            sample_sdm.id,
            enrichment_mode="siblings"
        )

        # order_total selected → order_date, order_status also included
        order_fields = [f for f in result.linked_fields if f.startswith("orders.")]
        assert len(order_fields) > 1
```

### G-6: Verified Query Anchoring Tests

```python
class TestVerifiedQueryAnchoring:
    """Story G-6: Verified Query Anchoring"""

    def test_returns_verified_query_candidates(self, linking_service, sdm_with_verified_queries):
        """High-similarity queries surface verified-query candidates and metadata."""
        result = linking_service.link(
            "Show monthly revenue by region",
            sdm_with_verified_queries.id
        )

        assert len(result.verified_query_candidates) > 0
        assert result.verified_query_candidates[0].similarity_score >= 0.80

    def test_optional_anchoring_boosts_schema(self, linking_service, sdm_with_verified_queries):
        """Anchoring is optional and only applied when enabled."""
        result = linking_service.link(
            "Show monthly revenue by region",
            sdm_with_verified_queries.id,
            vq_anchoring_enabled=True
        )

        assert result.anchor_source in (None, "verified_query")
        assert "orders" in result.linked_tables

    def test_does_not_execute_verified_query_tool(self, linking_service, sdm_with_verified_queries):
        """Linking does not auto-execute verified queries; it only provides signals."""
        result = linking_service.link(
            "Show monthly revenue by region",
            sdm_with_verified_queries.id
        )

        assert result.executed_verified_query is False
```

### G-7: Skeleton Selection Tests

```python
class TestSkeletonSelection:
    """Story G-7: SQL Skeleton Demo Selection"""

    def test_skeleton_similarity_selects_demo(self, linking_service, sdm_with_verified_queries):
        """Queries with similar structure select matching SQL skeleton demos."""
        # Query needing GROUP BY + HAVING
        result = linking_service.link(
            "Show products with more than 100 orders",
            sdm_with_verified_queries.id
        )

        # Should select demo with GROUP BY + HAVING pattern
        assert any(
            "GROUP BY" in d.sql and "HAVING" in d.sql
            for d in result.demonstrations
        )
```

### G-8: Query Rewrite Tests

```python
class TestQueryRewrite:
    """Story G-8: Query Rewrite (Conditional)"""

    def test_low_confidence_triggers_rewrite(self, linking_service, sample_sdm):
        """Low-confidence linking triggers query rewrite."""
        # Ambiguous query
        result = linking_service.link(
            "Show the thing with the stuff",
            sample_sdm.id
        )

        if result.confidence < 0.6:
            assert result.rewritten_query is not None
            assert result.rewritten_query != "Show the thing with the stuff"
```

### G-9: Multi-Sample Tests

```python
class TestMultiSample:
    """Story G-9: Multi-Sample Union (Conditional)"""

    def test_low_confidence_triggers_multi_sample(self, linking_service, sample_sdm):
        """Low-confidence linking triggers multi-sample union."""
        result = linking_service.link(
            "Show ambiguous data metric",
            sample_sdm.id,
            multi_sample=True
        )

        if result.confidence < 0.6:
            assert result.sample_count > 1
            assert result.linked_tables == result.union_of_samples
```

---

## Guardrail Tests

These tests validate H-series guardrails that prevent hallucinations and errors.

```bash
# Run guardrail tests
uv run --project agent_platform_server pytest tests/schema_linking/test_guardrails.py -v
```

### H-1: Extractive Selection Constraint

```python
class TestExtractiveConstraint:
    """Story H-1: Extractive Selection Constraint"""

    def test_only_sdm_elements_selected(self, linking_service, sample_sdm):
        """Linked elements are always valid SDM IDs."""
        result = linking_service.link(
            "Show all orders with customer details",
            sample_sdm.id
        )

        valid_ids = get_all_sdm_element_ids(sample_sdm)

        for element in result.linked_elements:
            assert element.id in valid_ids, f"Hallucinated element: {element.id}"

    def test_hallucinated_table_rejected(self, linking_service, sample_sdm):
        """Linker does not return tables that don't exist in SDM."""
        result = linking_service.link(
            "Show data from the user_sessions table",  # Doesn't exist
            sample_sdm.id
        )

        assert "user_sessions" not in [t.name for t in result.linked_tables]
```

### H-2: Repair Loop on Execution Error

```python
class TestRepairLoop:
    """Story H-2: Repair Loop on Execution Error"""

    async def test_execution_error_triggers_repair(self, nl2sql_service, sample_sdm):
        """SQL execution error triggers schema repair and retry."""
        # Query that initially selects wrong table
        result = await nl2sql_service.execute(
            "Show orders with invalid_column",
            sample_sdm.id
        )

        if result.first_attempt_error:
            assert result.repair_attempted
            assert result.final_sql != result.first_attempt_sql

    async def test_repair_limited_to_one_retry(self, nl2sql_service, sample_sdm):
        """Repair loop is limited to prevent infinite retries."""
        # Intentionally broken query
        result = await nl2sql_service.execute(
            "Show completely_nonexistent_data",
            sample_sdm.id
        )

        assert result.attempt_count <= 2  # Original + 1 repair
```

### H-3: Complexity Classifier

```python
class TestComplexityClassifier:
    """Story H-3: Complexity Classifier (SLM)"""

    def test_simple_query_classified(self, complexity_classifier):
        """Simple queries are classified as simple."""
        query = "Show all customers"

        result = complexity_classifier.classify(query)

        assert result.complexity == "simple"
        assert result.estimated_joins == 0

    def test_complex_query_classified(self, complexity_classifier):
        """Complex queries with joins/aggregations are classified as complex."""
        query = (
            "Show the top 10 customers by total order value, "
            "including their most recent order date and preferred payment method"
        )

        result = complexity_classifier.classify(query)

        assert result.complexity == "complex"
        assert result.estimated_joins >= 2

    def test_classifier_latency(self, complexity_classifier, benchmark):
        """Complexity classification completes in < 50ms."""
        query = "Show orders grouped by month with running total"

        result = benchmark(complexity_classifier.classify, query)

        assert benchmark.stats["mean"] < 0.050  # 50ms
```

### H-4: SLM Reranker

```python
class TestSLMReranker:
    """Story H-4: SLM Reranker"""

    def test_reranker_improves_precision(self, reranker, retrieval_results):
        """Reranker improves precision of top-k results."""
        query = "Show customer order history"

        # Initial retrieval (may have noise)
        initial = retrieval_results[:50]

        # Reranked results
        reranked = reranker.rerank(query, initial, k=10)

        # Precision should improve (gold elements in top-10)
        gold_elements = get_gold_schema(query)
        initial_precision = len(set(initial[:10]) & gold_elements) / 10
        reranked_precision = len(set(reranked) & gold_elements) / 10

        assert reranked_precision >= initial_precision

    def test_reranker_latency(self, reranker, retrieval_results, benchmark):
        """Reranking completes in < 100ms for 50 candidates."""
        query = "Show sales by region"

        result = benchmark(reranker.rerank, query, retrieval_results[:50], k=10)

        assert benchmark.stats["mean"] < 0.100  # 100ms
```

### H-5: Confidence Calibration

```python
class TestConfidenceCalibration:
    """Story H-5: Learned Confidence Calibration"""

    def test_high_confidence_correlates_with_accuracy(
        self, linking_service, test_queries_with_gold
    ):
        """High confidence predictions have high accuracy."""
        high_conf_results = []

        for query, gold in test_queries_with_gold:
            result = linking_service.link(query)
            if result.confidence > 0.8:
                high_conf_results.append(
                    (result.linked_tables, gold.tables)
                )

        # High confidence should have > 90% recall
        recalls = [
            len(set(linked) & set(gold)) / len(gold)
            for linked, gold in high_conf_results
        ]
        avg_recall = sum(recalls) / len(recalls)

        assert avg_recall > 0.90

    def test_confidence_latency(self, confidence_predictor, linking_result, benchmark):
        """Confidence prediction completes in < 10ms."""
        result = benchmark(confidence_predictor.predict, linking_result)

        assert benchmark.stats["mean"] < 0.010  # 10ms
```

---

## End-to-End Validation (BIRD)

This section covers integration testing using the BIRD benchmark.

### Prerequisites

- ✅ Schema linking implementation complete (Phase 2+)
- ✅ BIRD benchmark infrastructure set up (`quality-test bird docker up`)
- ✅ SDMs generated for BIRD databases
- ✅ Feature flag implemented (`ENABLE_SCHEMA_LINKING`)

See [BIRD CLI Guide](../quality/docs/BIRD_CLI_GUIDE.md) for setup instructions.

---

### Testing Methodology

### 1. Baseline Run (No Schema Linking)

Run BIRD tests with schema linking **disabled** to establish baseline metrics.

```bash
# Set feature flag OFF
export ENABLE_SCHEMA_LINKING=false

# Run all BIRD tests
quality-test run \
  --tests=bird- \
  --output=results/baseline.json \
  --log-level=INFO
```

**What this captures:**

- Baseline EX accuracy (% tests passing)
- Baseline latency (per query)
- Baseline prompt token counts
- Baseline error rates

---

### 2. Treatment Run (With Schema Linking)

Run BIRD tests with schema linking **enabled**.

```bash
# Set feature flag ON
export ENABLE_SCHEMA_LINKING=true

# Run all BIRD tests (same set)
quality-test run \
  --tests=bird- \
  --output=results/treatment.json \
  --log-level=INFO
```

**What this captures:**

- Treatment EX accuracy
- Treatment latency
- Treatment prompt token counts
- Fallback rate (from logs)

---

### 3. Comparison

Compare baseline vs treatment results:

```bash
quality-test compare \
  results/baseline.json \
  results/treatment.json \
  --output=results/comparison-report.md
```

---

### Test Corpus Selection

#### Recommended: Use Full BIRD Dev Set

Test on **all 11 databases** for comprehensive validation:

```bash
quality-test run --tests=bird- --difficulty=all
```

**Why full set?**

- Diverse schema sizes (5 to 150+ tables)
- Multiple domains (finance, education, healthcare, etc.)
- Mixed difficulty levels (simple, moderate, challenging)

#### Alternative: Stratified Sample

For faster iteration during development:

```bash
# 40% simple, 40% moderate, 20% challenging (balanced)
quality-test run --tests=bird- --difficulty=simple --limit=40
quality-test run --tests=bird- --difficulty=moderate --limit=40
quality-test run --tests=bird- --difficulty=challenging --limit=20
```

---

## Metrics Collection

This section defines the metrics collected during both component and integration testing.

### 1. EX Accuracy (Primary Metric)

**Definition:** % of queries that execute correctly and return the expected result.

**Measurement:**

```bash
# Extract pass/fail from results
jq '.tests | map(select(.status == "passed")) | length' results/baseline.json
jq '.tests | map(select(.status == "passed")) | length' results/treatment.json
```

**Target:** 5-15% improvement (from specification)

**Example:**

- Baseline: 72/100 passed = 72%
- Treatment: 81/100 passed = 81%
- **Improvement: +9%** ✅

---

### 2. Latency

**Definition:** End-to-end time from NL question to SQL result.

**Measurement:** Extract from test logs or instrumentation.

```python
# In test execution
logger.info(
    "query_executed",
    test_id=test_id,
    duration_ms=duration_ms,
    schema_linking_enabled=True
)
```

**Analysis:**

```bash
# Average latency per run
jq '.tests | map(.duration_ms) | add / length' results/baseline.json
jq '.tests | map(.duration_ms) | add / length' results/treatment.json
```

**Target:** 20-40% faster (from specification)

**Example:**

- Baseline: 3200ms avg
- Treatment: 2100ms avg
- **Improvement: 34% faster** ✅

---

### 3. Prompt Token Count

**Definition:** Number of tokens in the schema portion of the prompt.

**Measurement:** Log token counts during linking.

```python
# In schema linking code
logger.info(
    "prompt_built",
    sdm_id=sdm_id,
    full_schema_tokens=len(full_schema_tokens),
    linked_schema_tokens=len(linked_schema_tokens),
    reduction_pct=100 * (1 - linked_tokens / full_tokens)
)
```

**Analysis:**

```bash
# Extract token counts from logs
grep "prompt_built" logs/treatment.log | jq '.reduction_pct' | awk '{sum+=$1; n++} END {print sum/n}'
```

**Target:** 30-60% reduction (from specification)

**Example:**

- Baseline: 2500 tokens avg
- Treatment: 1100 tokens avg
- **Reduction: 56%** ✅

---

### 4. Linking Recall & Precision

**Definition:**

- **Recall@10:** % queries where all gold schema elements appear in top-10 linked elements
- **Precision@10:** % linked elements that are actually needed

**Measurement:** Requires gold schema annotations (see Test Data Requirements in architecture doc).

```python
# Compare linked schema vs gold schema
recall = len(linked & gold) / len(gold)
precision = len(linked & gold) / len(linked)
```

**Target:**

- Recall@10: > 90%
- Precision@10: > 60%

---

### 5. Fallback Rate

**Definition:** % queries that trigger fallback to full schema (low confidence).

**Measurement:** Count fallback events from logs.

```bash
# Count fallback occurrences
grep "schema_linking_fallback" logs/treatment.log | wc -l

# Total queries
jq '.tests | length' results/treatment.json

# Fallback rate
echo "scale=2; $(grep -c "schema_linking_fallback" logs/treatment.log) * 100 / $(jq '.tests | length' results/treatment.json)" | bc
```

**Target:** < 10% (from specification)

---

### 6. Complex Query Accuracy

**Definition:** EX accuracy on queries with 3+ joins and aggregations.

**Measurement:** Filter by BIRD difficulty="challenging".

```bash
quality-test run --tests=bird- --difficulty=challenging
```

**Target:** 10-20% improvement (from specification)

---

## Validation Procedure

### Step-by-Step

1. **Prepare environment**

   ```bash
   # Start BIRD database
   quality-test bird docker up

   # Ensure agent server running
   # Ensure SDMs exist for all BIRD databases
   ```

2. **Run baseline**

   ```bash
   export ENABLE_SCHEMA_LINKING=false
   quality-test run --tests=bird- --output=results/baseline.json 2>&1 | tee logs/baseline.log
   ```

3. **Run treatment**

   ```bash
   export ENABLE_SCHEMA_LINKING=true
   quality-test run --tests=bird- --output=results/treatment.json 2>&1 | tee logs/treatment.log
   ```

4. **Extract metrics**

   ```bash
   # Use scripts/analyze_linking_results.py (create this helper)
   python scripts/analyze_linking_results.py \
     --baseline results/baseline.json \
     --treatment results/treatment.json \
     --logs logs/treatment.log \
     --output results/report.md
   ```

5. **Review report**
   - Check all metrics meet targets
   - Identify failure modes (if any)
   - Validate statistical significance

---

## Success Criteria

All targets from specification must be met:

| Metric                     | Target  | Baseline | Treatment     | Status |
| -------------------------- | ------- | -------- | ------------- | ------ |
| **EX Accuracy**            | +5-15%  | 72%      | 81% (+9%)     | ✅     |
| **Latency**                | -20-40% | 3200ms   | 2100ms (-34%) | ✅     |
| **Token Reduction**        | 30-60%  | 2500     | 1100 (-56%)   | ✅     |
| **Linking Recall@10**      | > 90%   | N/A      | 93%           | ✅     |
| **Linking Precision@10**   | > 60%   | N/A      | 67%           | ✅     |
| **Fallback Rate**          | < 10%   | N/A      | 7%            | ✅     |
| **Complex Query Accuracy** | +10-20% | 58%      | 72% (+14%)    | ✅     |

**Pass criteria:** All metrics meet or exceed targets.

---

## Reporting Template

### Executive Summary

```markdown
# Schema Linking Validation Report

**Date:** 2026-01-XX  
**Test Corpus:** BIRD benchmark (11 databases, 500 queries)  
**Environment:** [staging/production]

## Results Summary

✅ **All success criteria met**

- EX Accuracy: **+9%** (target: +5-15%)
- Latency: **-34%** (target: -20-40%)
- Token Reduction: **-56%** (target: 30-60%)
- Fallback Rate: **7%** (target: <10%)

## Recommendation

✅ **Approve for production rollout**

Schema linking demonstrates consistent improvements across all metrics with no regressions.
```

### Detailed Metrics

```markdown
## Detailed Metrics

### 1. Accuracy

| Database           | Baseline EX | Treatment EX | Improvement |
| ------------------ | ----------- | ------------ | ----------- |
| california_schools | 85%         | 92%          | +7%         |
| financial          | 68%         | 79%          | +11%        |
| card_games         | 90%         | 95%          | +5%         |
| ...                | ...         | ...          | ...         |

**Average:** 72% → 81% (+9%)

### 2. Latency

| Percentile | Baseline | Treatment | Improvement |
| ---------- | -------- | --------- | ----------- |
| p50        | 2800ms   | 1900ms    | -32%        |
| p90        | 5200ms   | 3300ms    | -37%        |
| p99        | 8100ms   | 5200ms    | -36%        |

### 3. Failure Analysis

| Failure Mode     | Count | % of Total |
| ---------------- | ----- | ---------- |
| Timeout          | 3     | 1%         |
| Parse error      | 2     | 0.5%       |
| Missing join key | 8     | 2%         |

**Action items:**

- Improve FK path closure for missing join keys
```

---

## Troubleshooting

### Issue: Embeddings Disabled / SQLite-Only Mode

**Symptoms:** Retrieval recall drops; no embedding logs; BM25-only behavior observed.

**Diagnosis:**

```bash
# Check config flags
grep "embeddings_enabled" logs/treatment.log | tail -n 5
grep "storage_mode" logs/treatment.log | tail -n 5
```

**Expected behavior:**

- BM25-only retrieval (no vector similarity)
- Lower recall at top-k for fuzzy semantic matches
- Overall system still functional

**Common causes:**

- No embedding model configured → Configure embeddings or accept BM25-only mode
- SQLite-only environment → Expected limitation until Studio is decommissioned

---

### Issue: High Fallback Rate (>10%)

**Symptoms:** Many queries use full schema instead of linked schema.

**Diagnosis:**

```bash
# Check fallback reasons
grep "schema_linking_fallback" logs/treatment.log | jq '.reason' | sort | uniq -c
```

**Common causes:**

- `confidence_low` threshold too high → Lower to 0.55
- Poor retrieval quality → Tune embedding model or BM25 weights
- Missing relationships in SDM → Enrich SDM with FK metadata

---

### Issue: Accuracy Regression

**Symptoms:** Treatment EX accuracy < baseline EX accuracy.

**Diagnosis:**

```bash
# Find queries that passed baseline but failed treatment
jq -s '.[0].tests as $base | .[1].tests as $treat |
  [$base, $treat] | transpose |
  map(select(.[0].status == "passed" and .[1].status == "failed")) |
  map({id: .[0].id, baseline_sql: .[0].sql, treatment_sql: .[1].sql})' \
  results/baseline.json results/treatment.json
```

**Common causes:**

- Missing critical tables in linking → Check recall@10 < 90%
- FK path closure bug → Review deterministic refinement logic
- Embeddings disabled or misconfigured → Verify embedding config and runtime flags

---

### Issue: No Latency Improvement

**Symptoms:** Treatment latency ≈ baseline latency.

**Diagnosis:**

```bash
# Check if linking is actually running
grep "schema_linking_completed" logs/treatment.log | wc -l
# Should equal number of queries
```

**Common causes:**

- Feature flag not working → Verify env var set
- Linking always falling back → Check fallback rate
- Bottleneck elsewhere → Profile end-to-end timing

---

## Continuous Monitoring

After production rollout, monitor these metrics continuously:

```python
# Production metrics
metrics.gauge("schema_linking.accuracy_ex", ex_accuracy)
metrics.gauge("schema_linking.latency_p50", latency_p50)
metrics.gauge("schema_linking.token_reduction_pct", token_reduction)
metrics.gauge("schema_linking.fallback_rate", fallback_rate)
```

**Alert thresholds:**

- EX accuracy drops > 5% from baseline → Investigate immediately
- Fallback rate > 15% → Check retrieval quality
- Latency increases > 20% → Check for performance regression

---

## Appendix: Helper Scripts

### `scripts/analyze_linking_results.py`

Create this helper script to automate metric extraction:

```python
#!/usr/bin/env python3
"""Analyze schema linking validation results."""

import json
import sys
from pathlib import Path

def analyze(baseline_path: Path, treatment_path: Path) -> dict:
    """Compare baseline and treatment results."""

    with open(baseline_path) as f:
        baseline = json.load(f)
    with open(treatment_path) as f:
        treatment = json.load(f)

    # Calculate EX accuracy
    baseline_passed = sum(1 for t in baseline["tests"] if t["status"] == "passed")
    treatment_passed = sum(1 for t in treatment["tests"] if t["status"] == "passed")

    baseline_accuracy = baseline_passed / len(baseline["tests"]) * 100
    treatment_accuracy = treatment_passed / len(treatment["tests"]) * 100

    # Calculate latency
    baseline_latency = sum(t["duration_ms"] for t in baseline["tests"]) / len(baseline["tests"])
    treatment_latency = sum(t["duration_ms"] for t in treatment["tests"]) / len(treatment["tests"])

    return {
        "accuracy": {
            "baseline": baseline_accuracy,
            "treatment": treatment_accuracy,
            "improvement": treatment_accuracy - baseline_accuracy
        },
        "latency": {
            "baseline": baseline_latency,
            "treatment": treatment_latency,
            "improvement_pct": (baseline_latency - treatment_latency) / baseline_latency * 100
        }
    }

if __name__ == "__main__":
    results = analyze(Path(sys.argv[1]), Path(sys.argv[2]))
    print(json.dumps(results, indent=2))
```

---

## References

- [Schema Linking Specification](./schema-linking-specification.md) - Success metrics and requirements
- [Schema Linking Architecture](./schema-linking-architecture.md) - Implementation details
- [BIRD CLI Guide](../quality/docs/BIRD_CLI_GUIDE.md) - Benchmark infrastructure setup
- [BIRD Benchmark Paper](https://arxiv.org/abs/2305.03111) - Background on benchmark design
