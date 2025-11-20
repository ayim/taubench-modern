# SlotExecutor Lifecycle

### 1. Main `SlotExecutor.run` Loop

```mermaid
flowchart TD
    A[run entry]
    A --> B[Init SlotStates from quotas]
    B --> C[Create DB reader task]
    B --> D[Create slot executor tasks]
    C --> E[Create task update event]
    D --> E
    E --> F
    subgraph Main Loop
        F[Build wait set: shutdown + reader + slots + update waiter] --> G[asyncio.wait FIRST_COMPLETED]
        G -->|Only update waiter fired| H[Clear event + rebuild wait set]
        H --> P
        G -->|Shutdown task done| I[Handle Shutdown]
        G -->|Reader crashed| J[_handle_reader_crash: restart reader]
        G -->|Slot crashed| K[_handle_slot_crash: restart slot]
        G -->|Resize-cancelled task| L[Ignore; expected]
        J -->|Restart wait| P[Back to start]
        K --> P
        L --> P
        P --> F
    end
    I --> M[Set executor shutdown event]
    M --> N[_graceful_shutdown: reader + slots + return queue]
    N --> O[Shutdown complete]
```

### 2. Database Reader Task

```mermaid
flowchart TD
    subgraph ReaderLoop[While shutdown not set]
        L[Start iteration]
        L --> M[Fetch desired slot count from Quotas]
        M --> N{Desired != current?}
        N -->|Yes| O[_resize_slots]
        N -->|No| P[Skip resize]
        O --> S[Compute slots_to_fill = free slots - queue size]
        P --> S
        S --> T{slots_to_fill > 0?}
        T -->|Yes| U[storage.get_pending_work_item_ids]
        U --> W[Enqueue work items]
        W --> AA[wait worker_interval or shutdown]
        T -->|No| AA
    end
    AA --> AB{Shutdown set?}
    AB -->|No| L
    AB -->|Yes| AC[Exit loop]
```

### 3. Single Slot Execution

```mermaid
flowchart TD
    subgraph SlotTaskLoop[Per-slot task]
        AA[Start loop]
        AA --> AB[Wait on queue item or shutdown or cancellation]
        AB --> |Shutdown requested| AC{Shutdown}
        AC -->|Yes, have item| AD[_return_work_item_to_pool_on_shutdown]
        AC -->|Yes, no item| AE[Break loop]
        AD --> AE
        AB -->|Got WorkItem | AG[Mark slot executing + fetch timeout]
        AB -->|Task cancelled| AO[_handle_slot_cancelled]
        AB -->|Unexpected exception| AP[Mark item as ERROR]
        AP --> AZ
        AG --> AQ[_execute_work_item_in_slot]

        subgraph Execute one Work Item
            AQ --> AS[Create work item task]
            AS --> AT{Run WorkItem w/ Timeout}
            AT -->|Yes| AU[Log success]
            AT -->|Timeout| AV[Cancel task + mark ERROR]
            AT -->|Exception| AW[Mark ERROR]
            AU --> AR
            AV --> AR
            AW --> AR
        end

        AR[Cleanup] --> AZ[Go to start]
        AZ --> AA
    end
    AO --> AX[Quit]
    AE --> AX
```
