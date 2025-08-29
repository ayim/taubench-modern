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
