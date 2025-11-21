---
'@sema4ai/spar-ui': minor
---

Refactor DocIntel ExtractOnly components for better state management and DRY principles

- Consolidate duplicate loading states into shared constants
- Remove redundant state tracking (schemaResult, canReExtract, disabled prop)
- Replace raw state setters with semantic actions (initializeFromExisting)
- Improve "Add Field" UX with empty placeholder instead of auto-generated names
- Remove unused mock data files
- Add clear comments documenting state purpose
