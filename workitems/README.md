# Work-Items

A sub-project of the agent-server which asynchronously invokes agents.

All commands in this README should be executed in the _repository root directory_.

## Setup

1. Make sure `workitems/alembic.ini` has your postgres credentials of choice.

2. Run migrations `uv run --package agent_platform_workitems alembic -c workitems/alembic.ini upgrade head`

3. `make run-server` for a combined agent-server and work-items-server experience

work-items is available at `http://localhost:8000/api/work-items/v1/work-items`

## Create new migrations

```
$ uv run --package agent_platform_workitems alembic -c workitems/alembic.ini revision --autogenerate -m "descriptive message about changes"
```

## Run tests

These tests are self-encapsulated, but include testing units of work as well as end-to-end tests of Workitems inside AgentServer.

```
$ make test-workitems
```

The top level `make test-unit` and `make test-integration` will run the corresponding workitem tests implicitly.
