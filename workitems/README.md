## Setup

_From the repository root_

1. Make sure `workitems/alembic.ini` has your postgres credentials of choice.

2. Run migrations `uv run --package agent_platform_workitems alembic -c workitems/alembic.ini upgrade head`

3. From repository root, `make run-server` (agent-server and work-items) or `make run-workitems` (just work-items)

work-items is available at `http://localhost:8000/api/work-items/v1/work-items`

## Create new migrations

```
$ uv run --package agent_platform_workitems alembic -c workitems/alembic.ini revision --autogenerate -m "descriptive message about changes"
```
