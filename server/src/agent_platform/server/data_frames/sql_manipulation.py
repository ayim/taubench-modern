import typing
from typing import Any

if typing.TYPE_CHECKING:
    from sqlglot import exp

DESTRUCTIVE_KEYS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "MERGE",
    "TRUNCATE",
    "CREATE",
    "ALTER",
    "DROP",
    "RENAME",
    "GRANT",
    "REVOKE",
    "CALL",
    "EXECUTE",
    "COPY",
    "LOAD",
    "REFRESH",
    "VACUUM",
    "OPTIMIZE",
    "ANALYZE",
    "BEGIN",
    "COMMIT",
    "ROLLBACK",
    "SET",
    "USE",
}

READONLY_TOPLEVEL = {"SELECT", "UNION", "EXCEPT", "INTERSECT", "VALUES", "WITH"}


def _root_key(e: "exp.Expression") -> str:
    # Unwrap wrappers to get to the "real" statement
    from sqlglot import exp

    while isinstance(e, exp.With | exp.Subquery | exp.Paren):
        e = e.this
    return (e.key or "").upper()


def _contains_destructive(e: "exp.Expression") -> str | None:
    # Walk the whole tree looking for any destructive node
    for node in e.walk():
        k = (node.key or "").upper()
        if k in DESTRUCTIVE_KEYS:
            return k
    return None


def get_destructive_reasons(stmt: "exp.Expression") -> list[str]:
    """
    Returns reasons for why the statement is destructive.
    """
    reasons: list[str] = []
    root = _root_key(stmt)
    if root not in READONLY_TOPLEVEL:
        reasons.append(
            f"Only read-only top-levels are allowed. Found non-read-only top-level: {root}"
        )
        return reasons
    which = _contains_destructive(stmt)
    if which is not None:
        reasons.append(f"Only read-only statements are allowed. Found destructive clause: {which}")
        return reasons
    return reasons


def build_ctes(name_to_cte_ast: dict[str, Any]):
    from sqlglot import exp

    # Build CTE expressions: WITH name AS (<parsed query>)
    ctes = [
        exp.CTE(
            this=p,  # the subquery AST
            alias=exp.TableAlias(this=exp.to_identifier(name)),
        )
        for name, p in name_to_cte_ast.items()
    ]
    return ctes


def update_with_clause(main_sql_ast, ctes: list[Any]):
    """
    Update the with clause of the main sql ast with the new CTEs.
    """
    from sqlglot import exp

    if not ctes:
        return main_sql_ast  # Nothing to change

    existing_with = main_sql_ast.args.get("with")
    if existing_with is not None:
        existing_with.expressions.extend(ctes)
    else:
        main_sql_ast.set("with", exp.With(expressions=ctes, recursive=False))
    return main_sql_ast


def update_table_names(main_sql_ast, logical_table_name_to_actual_table_name: dict[str, str]):
    """
    Update the table name of the main sql ast with the new table name.
    """
    from sqlglot import exp

    if not logical_table_name_to_actual_table_name:
        return main_sql_ast  # Nothing to change

    for table in main_sql_ast.find_all(exp.Table):
        if table.name in logical_table_name_to_actual_table_name:
            table.set(
                "this", exp.Identifier(this=logical_table_name_to_actual_table_name[table.name])
            )
    return main_sql_ast


def extract_variable_names_required_from_sql_computation(sql_ast: Any) -> "set[str]":
    import sqlglot.expressions

    tables = sql_ast.find_all(sqlglot.expressions.Table)

    required_variable_names = {t.name for t in tables if t.name}
    cte_tables = sql_ast.find_all(sqlglot.expressions.CTE)
    for cte in cte_tables:
        required_variable_names.discard(cte.alias)
    return required_variable_names


def validate_sql_query(sql_query: str, dialect: str) -> Any:
    """
    Validate the SQL query and return the AST.
    """
    import sqlglot

    from agent_platform.core.errors.base import PlatformError

    expressions = sqlglot.parse(sql_query, dialect=dialect)
    if len(expressions) != 1:
        raise PlatformError(
            message=f"SQL query must be a single expression. Found: {len(expressions)} "
            f"SQL query: {sql_query!r}"
        )

    expr = expressions[0]
    if expr is None or not hasattr(expr, "key"):
        raise PlatformError(message=f"SQL query is not a valid expression: {sql_query!r}")

    reasons = get_destructive_reasons(expr)
    if reasons:
        raise PlatformError(
            message=f"Unable to create data frame from SQL query: {sql_query} (Errors: {reasons})"
        )
    return expr
