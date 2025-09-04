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
