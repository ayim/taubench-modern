# Evaluations Data Model

This document illustrates how the evaluations pipeline stitches together batch runs, scenario runs, and individual trials.

## Entity Relationships

```mermaid
erDiagram
    Agent ||--o{ Scenario : "owns"
    ScenarioBatchRun }o--|| Agent : "scheduled for"
    ScenarioBatchRun ||--o{ ScenarioRun : "spawns"
    Scenario ||--o{ ScenarioRun : "source of"
    ScenarioRun ||--o{ Trial : "contains"
```

- Each `Scenario` belongs to exactly one agent, but an agent may define many scenarios.
- A `ScenarioBatchRun` is created per agent and captures a snapshot of the scenarios selected at scheduling time.
- Every `ScenarioRun` references the scenario it replays and may optionally reference the originating batch run.
- `Trial` rows are the atomic work units executed by the background worker; runs can request multiple trials to capture variability.

## Batch Composition Details

```mermaid
flowchart LR
    Batch["ScenarioBatchRun<br/>status: PENDING/RUNNING/etc."] -->|scenario_ids| Snapshot["Scenario IDs list<br/>(captured at creation)"]
    Batch -->|creates| Run1["ScenarioRun (scenario A)"]
    Batch -->|creates| Run2["ScenarioRun (scenario B)"]
    Run1 -->|num_trials| TrialGroupA["Trials A0..An"]
    Run2 -->|num_trials| TrialGroupB["Trials B0..Bn"]
```

Notes:

- The batch stores the scenario identifier list so it can recalculate completion stats even if new scenarios are added later.
- Each scenario run produces `num_trials` rows immediately; the async worker dequeues them globally, so batches finish when all their trials reach a terminal status.
