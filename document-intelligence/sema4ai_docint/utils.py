import json
import re
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path
from typing import Any


class ReservedSQLKeywords(StrEnum):
    """Reserved SQL keywords that cannot be used as top-level property names in
    extraction schemas."""

    ADD = "add"
    ALL = "all"
    ALTER = "alter"
    AND = "and"
    ANY = "any"
    AS = "as"
    ASC = "asc"
    AUTHORIZATION = "authorization"
    BETWEEN = "between"
    BY = "by"
    CASE = "case"
    CAST = "cast"
    CHECK = "check"
    COLLATE = "collate"
    COLUMN = "column"
    CONSTRAINT = "constraint"
    CREATE = "create"
    CROSS = "cross"
    CURRENT = "current"
    CURRENT_CATALOG = "current_catalog"
    CURRENT_DATE = "current_date"
    CURRENT_ROLE = "current_role"
    CURRENT_SCHEMA = "current_schema"
    CURRENT_TIME = "current_time"
    CURRENT_TIMESTAMP = "current_timestamp"
    CURRENT_USER = "current_user"
    DEFAULT = "default"
    DELETE = "delete"
    DESC = "desc"
    DISTINCT = "distinct"
    DROP = "drop"
    ELSE = "else"
    END = "end"
    EXCEPT = "except"
    EXISTS = "exists"
    FETCH = "fetch"
    FOR = "for"
    FOREIGN = "foreign"
    FROM = "from"
    FULL = "full"
    GRANT = "grant"
    GROUP = "group"
    GROUP_BY = "group by"
    HAVING = "having"
    IN = "in"
    INNER = "inner"
    INSERT = "insert"
    INTERSECT = "intersect"
    INTO = "into"
    IS = "is"
    JOIN = "join"
    LEADING = "leading"
    LEFT = "left"
    LIKE = "like"
    LIMIT = "limit"
    MERGE = "merge"
    NATURAL = "natural"
    NOT = "not"
    NULL = "null"
    OFFSET = "offset"
    ON = "on"
    OR = "or"
    ORDER = "order"
    ORDER_BY = "order by"
    OUTER = "outer"
    OVER = "over"
    PARTITION = "partition"
    PRIMARY = "primary"
    PRIMARY_KEY = "primary key"
    REFERENCES = "references"
    RIGHT = "right"
    ROLLBACK = "rollback"
    ROW = "row"
    ROWS = "rows"
    SAVEPOINT = "savepoint"
    SELECT = "select"
    SESSION_USER = "session_user"
    SET = "set"
    SOME = "some"
    TABLE = "table"
    THEN = "then"
    TOP = "top"
    TRAILING = "trailing"
    TRANSACTION = "transaction"
    TRUNCATE = "truncate"
    UNION = "union"
    UNIQUE = "unique"
    UPDATE = "update"
    USING = "using"
    VALUES = "values"
    VIEW = "view"
    WHEN = "when"
    WHERE = "where"
    WINDOW = "window"
    WITH = "with"


def normalize_name(name: str) -> str:
    """Normalize name by removing special characters, replacing spaces with underscores,
    and converting to lowercase.

    Args:
        name: The name to normalize

    Returns:
        The normalized name
    """
    # Remove special characters (keep only alphanumerics and spaces)
    cleaned = re.sub(r"[^\w\s]", "", name.strip())

    # Replace spaces with underscores and convert to lowercase
    return "_".join(cleaned.split()).lower()


# TODO: This method is being used for data model validation as well. Currently, extraction
# schemas and data model schemas are the same, but they may become separate, at which point
# we need to support both validation concerns.
def validate_extraction_schema(json_schema: str | dict[str, Any]) -> dict[str, Any]:
    """Validates a JSON schema for use with Reducto as an extraction schema.

    Args:
        json_schema: The JSON schema to validate

    Returns:
        The parsed schema

    Raises:
        Exception: If the schema is invalid or not compatible with Reducto
    """
    from jsonschema.validators import validator_for

    if isinstance(json_schema, str):
        parsed_schema = json.loads(json_schema)
    else:
        parsed_schema = json_schema

    # Get the appropriate validator for this schema (note that usually we won't get a schema
    # with a $schema keyword, so we will likely be using the default validator)
    # TODO: Reducto's extraction schema is a subset of JSONschema, be more specific.
    validator_class = validator_for(parsed_schema)
    validator = validator_class(parsed_schema)

    # Validate that the schema itself is valid according to JSON Schema specification
    validator.check_schema(parsed_schema)

    # Reducto requires schemas to be of type "object"
    schema_type = parsed_schema.get("type")
    if schema_type != "object":
        raise ValueError(f"Schema must be of type 'object', got type '{schema_type}'")
    properties = parsed_schema.get("properties")
    if properties is None or not isinstance(properties, dict):
        raise ValueError("Schema must have a non-null 'properties' field of type 'object'")

    return parsed_schema


def _filter_jsonschema(schema: Any, key_filter: Callable[[str], bool]) -> Any:
    """Filter a JSON schema by removing keys that match the filter function.

    Args:
        schema: The JSON schema to filter
        key_filter: Keys matching the filter will be removed from the schema

    Returns:
        The filtered schema
    """
    if not isinstance(schema, dict):
        return schema

    result = {}
    for key, value in schema.items():
        if key_filter(key):
            continue

        if isinstance(value, dict):
            result[key] = _filter_jsonschema(value, key_filter)
        elif isinstance(value, list):
            result[key] = [
                _filter_jsonschema(item, key_filter) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value

    return result


def _replace_jsonschema_values(schema: Any, replacements: dict[str, str]) -> Any:
    """Replace values in a JSON schema with values from different keys at the same level.

    Args:
        schema: The JSON schema to modify
        replacements: Dictionary mapping target_key -> source_key for replacements

    Returns:
        The schema with replaced values
    """
    if not isinstance(schema, dict):
        return schema

    result = {}
    for key, value in schema.items():
        if isinstance(value, dict):
            result[key] = _replace_jsonschema_values(value, replacements)
        elif isinstance(value, list):
            result[key] = [
                _replace_jsonschema_values(item, replacements) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value

    # Apply replacements at this level. If the replacement doesn't exist, we leave
    # the original value.
    for target_key, source_key in replacements.items():
        if target_key in result and source_key in result:
            result[target_key] = result[source_key]

    return result


def compute_document_id(file_path: Path) -> str:
    """Generate a deterministic UUID for a file based on its contents."""
    import hashlib
    import uuid

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)

    hash_hex = sha256_hash.hexdigest()
    return str(uuid.UUID(hash_hex[:32]))
