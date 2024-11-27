"""Vendored utils from langgraph-checkpoint-postgres library."""

from typing import Any, Dict, Literal, Sequence, Tuple

import orjson
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import get_checkpoint_id
from psycopg.types.json import Jsonb
from pydantic import BaseModel

from sema4ai_agent_server.schema import AgentServerRunnableConfig
from sema4ai_agent_server.utils import get_thread_id_from_config


def _metadata_predicate(
    metadata_filter: Dict[str, Any], flavor: Literal["sqlite", "postgres"]
) -> Tuple[Sequence[str], Sequence[Any]]:
    """Return WHERE clause predicates for (a)search() given metadata filter.

    This method returns a tuple of a string and a tuple of values. The string
    is the parametered WHERE clause predicate (excluding the WHERE keyword):
    "column1 = ? AND column2 IS ?". The tuple of values contains the values
    for each of the corresponding parameters.
    """

    def _where_value(query_value: Any) -> Tuple[str, Any]:
        """Return tuple of operator and value for WHERE clause predicate."""
        if query_value is None:
            return ("IS %s" if flavor == "postgres" else "IS ?", None)
        elif (
            isinstance(query_value, str)
            or isinstance(query_value, int)
            or isinstance(query_value, float)
        ):
            return ("= %s" if flavor == "postgres" else "= ?", query_value)
        elif isinstance(query_value, bool):
            return ("= %s" if flavor == "postgres" else "= ?", 1 if query_value else 0)
        elif isinstance(query_value, dict) or isinstance(query_value, list):
            # query value for JSON object cannot have trailing space after separators (, :)
            # SQLite json_extract() returns JSON string without whitespace
            return (
                "= %s" if flavor == "postgres" else "= ?",
                orjson.dumps(query_value).decode("utf-8"),
            )
        else:
            return ("= %s" if flavor == "postgres" else "= ?", str(query_value))

    predicates = []
    param_values = []

    # process metadata query
    for query_key, query_value in metadata_filter.items():
        operator, param_value = _where_value(query_value)
        if flavor == "sqlite":
            predicates.append(
                f"json_extract(CAST(metadata AS TEXT), '$.{query_key}') {operator}"
            )
        else:  # flavor == "postgres"
            predicates.append(f"metadata->>'{query_key}' {operator}")
        param_values.append(param_value)

    return (predicates, param_values)


def search_where(
    config: AgentServerRunnableConfig | RunnableConfig | None,
    filter: Dict[str, Any] | None,
    before: AgentServerRunnableConfig | RunnableConfig | None = None,
    flavor: Literal["sqlite", "postgres"] = "sqlite",
) -> Tuple[str, Sequence[Any]]:
    """Return WHERE clause predicates for (a)search() given metadata filter
    and `before` config.

    This method returns a tuple of a string and a tuple of values. The string
    is the parametered WHERE clause predicate (including the WHERE keyword):
    "WHERE column1 = ? AND column2 IS ?". The tuple of values contains the
    values for each of the corresponding parameters.
    """
    wheres = []
    param_values = []

    # construct predicate for config filter
    if config is not None:
        wheres.append("thread_id = ?" if flavor == "sqlite" else "thread_id = %s")
        param_values.append(get_thread_id_from_config(config))
        checkpoint_ns = config["configurable"].get("checkpoint_ns")
        if checkpoint_ns is not None:
            wheres.append(
                "checkpoint_ns = ?" if flavor == "sqlite" else "checkpoint_ns = %s"
            )
            param_values.append(checkpoint_ns)

        if checkpoint_id := get_checkpoint_id(config):
            wheres.append(
                "checkpoint_id = ?" if flavor == "sqlite" else "checkpoint_id = %s"
            )
            param_values.append(checkpoint_id)

    # construct predicate for metadata filter
    if filter:
        metadata_predicates, metadata_values = _metadata_predicate(filter, flavor)
        wheres.extend(metadata_predicates)
        param_values.extend(metadata_values)

    # construct predicate for `before`
    if before is not None:
        wheres.append(
            "checkpoint_id < ?" if flavor == "sqlite" else "checkpoint_id < %s"
        )
        param_values.append(get_checkpoint_id(before))

    return ("WHERE " + " AND ".join(wheres) if wheres else "", param_values)


# There is likely a better way to implement these model dumps by using some sort
# of fancy WrapSerializers in the schema. I tried that but Pydantic refused to
# work for me so I must be missing something. These are the simplest workarounds
# that preserves the idea that the schema should be the source of truth for the
# data model. - @kylie-bee
def model_dump_for_postgres(
    obj: BaseModel, context: dict[str, Any] | None = None, **kwargs: Any
) -> Dict[str, Any]:
    """Dump a Pydantic model to a JSON-serializable dict for PostgreSQL.

    This method converts a Pydantic model to a dict, wrapping any fields
    annotated in the model with 'db_json' in the PostgreSQL Jsonb wrapper.
    """
    dumped = obj.model_dump(context=context, **kwargs)
    for key in dumped.keys():
        key_metadata = obj.model_fields[key].metadata
        if "db_json" in key_metadata:
            dumped[key] = Jsonb(dumped[key])

    return dumped


def model_dump_for_sqlite(
    obj: BaseModel, context: dict[str, Any] | None = None, **kwargs: Any
) -> Dict[str, Any]:
    """Dump a Pydantic model to JSON-serializable dict for SQLite.

    This method dumps any nested models marked with 'db_json' metadata as JSON
    strings for SQLite.
    """
    dumped = obj.model_dump(context=context, **kwargs)
    for key in dumped.keys():
        key_metadata = obj.model_fields[key].metadata
        if "db_json" in key_metadata:
            dumped[key] = orjson.dumps(dumped[key]).decode("utf-8")

    return dumped
