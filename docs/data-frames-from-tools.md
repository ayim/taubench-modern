# Data frames and tools/actions integration

Whenever a tool/action returns a `Table` (or `Response[Table]`), a data frame should be created automatically.

A table is defined as a dict with the following keys:

- columns: list[str]
- rows: list[list[Any]]

The data frame should be created with the following properties:

Example:

```json
{
  "columns": ["column1", "column2"],
  "rows": [
    [1, 2],
    [3, 4]
  ]
}
```

Alternatively, a `Response[Table]` can also be returned.

i.e.:

```json
{
  "result": {
    "columns": ["column1", "column2"],
    "rows": [
      [1, 2],
      [3, 4]
    ]
  }
}
```

Example of an action that returns a table (which would
be automatically converted to a data frame):

```python
from sema4ai.actions import Response, Table, action


@action
def my_named_query() -> Response[Table]:
    """
    A named query that returns a table.
    """
    rows = []
    for i in range(200):
        rows.append([i, i + 1])
    return Response(result=Table(columns=["col1", "col2"], rows=rows))
```
