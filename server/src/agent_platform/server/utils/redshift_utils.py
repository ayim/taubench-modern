"""Utility functions for Redshift-specific operations.

Redshift is based on PostgreSQL but has several incompatibilities that require
special handling when using Ibis's PostgreSQL backend.

This module contains connection patching logic that is required for Redshift
to work properly with Ibis.

NOTE: Query execution logic has been moved to:
    agent_platform.server.semantic_data_models.handlers.redshift
"""

from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    import ibis.expr.schema as sch

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _patched_current_database(self) -> str:
    """Get current schema using Redshift-compatible SQL."""
    con = self.con
    with con.cursor() as cursor, con.transaction():
        # Use direct SQL that works on Redshift
        cursor.execute("SELECT current_schema()")
        result = cursor.fetchone()
        if result:
            return result[0]
        return "public"  # fallback to public schema


def _patched_get_schema(
    self,
    name: str,
    *,
    catalog: str | None = None,
    database: str | None = None,
) -> "sch.Schema":
    """Get schema for a table, avoiding pg_enum queries.

    Redshift doesn't have pg_catalog.pg_enum table that PostgreSQL
    uses for enum types. We override this to use a simpler query
    that only gets basic column information.
    """
    import ibis.expr.schema as sch

    # Use information_schema which Redshift does support
    query = """
        SELECT column_name, data_type, character_maximum_length,
               numeric_precision, numeric_scale
        FROM information_schema.columns
        WHERE table_name = %s
    """
    params = [name]

    # Add schema filter if database is provided
    if database:
        query += " AND table_schema = %s"
        params.append(database)
    elif hasattr(self, "current_database"):
        # Use current schema if available
        query += " AND table_schema = %s"
        params.append(self.current_database)

    query += " ORDER BY ordinal_position"

    con = self.con
    with con.cursor() as cursor:
        cursor.execute(query, params)
        rows = cursor.fetchall()

    # Build schema from results
    fields: dict[str, Any] = {}
    for row in rows:
        col_name = row[0]
        data_type = row[1]
        # Map Redshift types to Ibis types
        ibis_type = _map_redshift_type_to_ibis(data_type, row[2], row[3], row[4])
        fields[col_name] = ibis_type

    return sch.Schema(fields)  # type: ignore[arg-type]


def _patched_get_schema_using_query(self, query: str) -> "sch.Schema":
    """Get schema using a query, using temp table instead of temp view.

    Redshift doesn't support CREATE TEMPORARY VIEW, only temp tables.
    This method creates a temp table with the query results, inspects
    the schema, then drops the table.
    """
    import uuid

    # Generate unique table name using UUID to avoid collisions
    # Format: ibis_redshift_temp_<uuid_hex>
    unique_id = uuid.uuid4().hex[:16]  # Use first 16 chars of UUID
    name = f"ibis_redshift_temp_{unique_id}"

    # Use CREATE TEMP TABLE instead of CREATE TEMPORARY VIEW
    create_stmt = f"CREATE TEMP TABLE {name} AS {query}"
    drop_stmt = f"DROP TABLE IF EXISTS {name}"

    con = self.con
    with con.cursor() as cursor, con.transaction():
        cursor.execute(create_stmt)

    try:
        return self.get_schema(name)
    finally:
        with con.cursor() as cursor, con.transaction():
            cursor.execute(drop_stmt)


def patch_redshift_connection(connection: Any) -> Any:
    """Patch a Redshift connection to work around Ibis PostgreSQL incompatibilities.

    Redshift is based on PostgreSQL but has key differences:
    1. current_schema is generated incorrectly by sqlglot
    2. pg_my_temp_schema() function doesn't exist
    3. pg_catalog.pg_enum table doesn't exist
    4. CREATE TEMPORARY VIEW is not supported (only temp tables)

    This function applies patches to make Ibis work correctly with Redshift.

    Args:
        connection: An Ibis PostgreSQL connection connected to Redshift

    Returns:
        The patched connection object with Redshift-specific workarounds
    """
    import types

    logger.debug("Patching Redshift connection")

    # ========================================================================
    # STEP 1: Mark connection as Redshift and cache metadata
    # ========================================================================
    # Set flag for fast backend detection (avoids querying stv_slices)
    connection._is_redshift = True

    # Cache current database/schema (avoids repeated SQL queries)
    connection._cached_current_database = _patched_current_database(connection)

    # ========================================================================
    # STEP 2: Patch instance methods (get_schema, _get_schema_using_query)
    # ========================================================================
    # These can be patched directly on the instance
    connection.get_schema = types.MethodType(_patched_get_schema, connection)
    connection._get_schema_using_query = types.MethodType(
        _patched_get_schema_using_query, connection
    )

    # ========================================================================
    # STEP 3: Patch class properties (current_database, _session_temp_db)
    # ========================================================================
    # Properties must be patched at class level, but we make them
    # instance-aware
    _patch_connection_properties(connection)

    # ========================================================================
    # STEP 4: Configure optimal fetch size for cluster type
    # ========================================================================
    _configure_redshift_fetch_size(connection)

    return connection


def _patch_connection_properties(connection: Any) -> None:
    """Patch connection properties to be Redshift-compatible.

    Properties in Python must be defined at the class level, not at the
    instance level. We patch the class but make the behavior instance-aware
    by checking for instance-specific flags and cached values.

    This approach:
    - Patches the class once (affects all instances)
    - But wrappers check instance attributes
    - Redshift instances use cached values
    - PostgreSQL instances use original behavior

    Args:
        connection: The connection instance to patch
    """
    connection_class = type(connection)

    # Save original property getters (only once per class)
    if not hasattr(connection_class, "_original_current_database_fget"):
        connection_class._original_current_database_fget = connection_class.current_database.fget
        connection_class._original_session_temp_db_fget = connection_class._session_temp_db.fget

    # Get references to original getters
    original_current_database = connection_class._original_current_database_fget
    original_session_temp_db = connection_class._original_session_temp_db_fget

    # Define wrapper for current_database property
    def current_database_wrapper(self):
        """Return cached database for Redshift, original for PostgreSQL."""
        if hasattr(self, "_cached_current_database"):
            return self._cached_current_database
        return original_current_database(self)

    # Define wrapper for _session_temp_db property
    def session_temp_db_wrapper(self):
        """Return None for Redshift, original for PostgreSQL."""
        if hasattr(self, "_is_redshift") and self._is_redshift:
            return None
        return original_session_temp_db(self)

    # Apply patches at class level
    connection_class.current_database = property(current_database_wrapper)
    connection_class._session_temp_db = property(session_temp_db_wrapper)


def _configure_redshift_fetch_size(connection: Any) -> None:
    """Configure cursor fetch size for Redshift compatibility.

    Redshift single-node clusters have a maximum fetch size of 1000.
    Multi-node clusters support larger fetch sizes (up to 1,000,000+).
    This detects the cluster type and caches the optimal arraysize
    on the connection instance for fast retrieval.
    """
    try:
        # Access the underlying psycopg connection
        if hasattr(connection, "con"):
            # Detect if single-node or multi-node cluster
            arraysize = _get_optimal_arraysize(connection.con)
            # Cache the optimal arraysize on the connection instance
            connection._redshift_arraysize = arraysize
            # Also set the default arraysize for this connection
            connection.con.arraysize = arraysize
    except Exception:
        # If configuration fails, log but don't fail the connection
        logger.warning("Failed to configure Redshift fetch size", exc_info=True)


def _get_optimal_arraysize(con: Any) -> int:
    """Detect Redshift cluster type and return optimal arraysize.

    Single-node clusters have a max fetch size of 1000.
    Multi-node clusters can handle up to 1,000,000 or more.

    Performance considerations:
    - Larger arraysize = fewer round trips, faster for large result sets
    - Larger arraysize = more client memory usage
    - For typical inspection queries (sampling data), 1M is reasonable

    Args:
        con: The psycopg connection object

    Returns:
        Optimal arraysize for the cluster type
    """
    try:
        with con.cursor() as cursor:
            # Query to count compute nodes in the cluster
            # stv_slices shows all slices across all nodes
            # Each node has multiple slices, so we count distinct nodes
            cursor.execute(
                """
                SELECT COUNT(DISTINCT node) as node_count
                FROM stv_slices
                """
            )
            result = cursor.fetchone()
            if result and result[0]:
                node_count = result[0]
                if node_count == 1:
                    # Single-node: max fetch size is 1000
                    logger.debug("Detected Redshift single-node cluster, using arraysize=1000")
                    return 1000
                else:
                    # Multi-node: can use large fetch size
                    # Use 1,000,000 for optimal performance
                    # This matches psycopg3's default and works well
                    # for typical data inspection queries
                    logger.debug(
                        f"Detected Redshift multi-node cluster "
                        f"({node_count} nodes), using arraysize=1000000"
                    )
                    return 1_000_000
    except Exception as e:
        # If detection fails, use conservative default
        logger.warning(
            f"Failed to detect Redshift cluster type: {e!r}, using conservative arraysize=1000"
        )

    # Default to 1000 (safe for single-node)
    return 1000


def _map_string_type(data_type_lower: str) -> Any:
    """Map Redshift string types to Ibis types."""
    import ibis.expr.datatypes as dt

    if data_type_lower in (
        "character varying",
        "varchar",
        "character",
        "char",
        "text",  # TEXT is an alias for VARCHAR in Redshift
        "bpchar",  # Internal name for CHAR
    ):
        return dt.String()
    return None


def _map_numeric_type(
    data_type_lower: str,
    numeric_precision: int | None,
    numeric_scale: int | None,
) -> Any:
    """Map Redshift numeric types to Ibis types."""
    import ibis.expr.datatypes as dt

    # Handle decimal types with precision/scale
    if data_type_lower in ("decimal", "numeric"):
        if numeric_precision and numeric_scale:
            return dt.Decimal(numeric_precision, numeric_scale)
        return dt.Decimal(18, 0)  # Default precision

    # Map other numeric types using a dictionary
    type_map = {
        "smallint": dt.Int16(),
        "int2": dt.Int16(),
        "integer": dt.Int32(),
        "int": dt.Int32(),
        "int4": dt.Int32(),
        "bigint": dt.Int64(),
        "int8": dt.Int64(),
        "real": dt.Float32(),
        "float4": dt.Float32(),
        "double precision": dt.Float64(),
        "float8": dt.Float64(),
        "float": dt.Float64(),
    }

    return type_map.get(data_type_lower)


def _map_temporal_type(data_type_lower: str) -> Any:
    """Map Redshift date/time types to Ibis types."""
    import ibis.expr.datatypes as dt

    if data_type_lower == "date":
        return dt.Date()
    elif data_type_lower in ("timestamp", "timestamp without time zone"):
        return dt.Timestamp()
    elif data_type_lower in ("timestamp with time zone", "timestamptz"):
        return dt.Timestamp(timezone="UTC")
    elif data_type_lower in ("time", "time without time zone"):
        return dt.Time()
    elif data_type_lower in ("time with time zone", "timetz"):
        # Ibis doesn't have a time type with timezone, use regular time
        return dt.Time()
    return None


def _map_special_type(data_type_lower: str) -> Any:
    """Map Redshift special types (binary, JSON, spatial) to Ibis types."""
    import ibis.expr.datatypes as dt

    # Binary types
    if data_type_lower in ("bytea", "varbyte"):
        return dt.Binary()
    # Boolean
    elif data_type_lower in ("boolean", "bool"):
        return dt.Boolean()
    # Semi-structured data (SUPER type for JSON-like data)
    elif data_type_lower == "super":
        return dt.JSON()
    # Spatial/Geospatial types (Redshift supports GEOMETRY and GEOGRAPHY)
    elif data_type_lower in ("geometry", "geography"):
        # Use string as fallback since we don't know specific geometry type
        return dt.String()
    return None


def _map_redshift_type_to_ibis(
    data_type: str,
    char_max_length: int | None,
    numeric_precision: int | None,
    numeric_scale: int | None,
) -> Any:
    """Map Redshift data types to Ibis types.

    Redshift supports a subset of PostgreSQL types plus some unique types:
    - String: VARCHAR, CHAR, TEXT (alias for VARCHAR)
    - Numeric: SMALLINT, INTEGER, BIGINT, DECIMAL, REAL, DOUBLE PRECISION
    - Boolean: BOOLEAN
    - Date/Time: DATE, TIMESTAMP, TIMESTAMPTZ, TIME, TIMETZ
    - Binary: VARBYTE (variable-length binary)
    - Semi-structured: SUPER (JSON-like data)
    - Spatial: GEOMETRY, GEOGRAPHY

    Redshift does NOT support:
    - Arrays, JSONB, UUID, ENUM, BLOB (PostgreSQL types)

    Args:
        data_type: The Redshift data type name from information_schema
        char_max_length: Maximum length for character types
        numeric_precision: Precision for numeric types
        numeric_scale: Scale for numeric types

    Returns:
        An Ibis data type

    References:
        - Redshift data types:
          https://docs.aws.amazon.com/redshift/latest/dg/c_Supported_data_types.html
        - Ibis data types: https://ibis-project.org/reference/datatypes
    """
    import ibis.expr.datatypes as dt

    data_type_lower = data_type.lower()

    # Try each category of types
    result = _map_string_type(data_type_lower)
    if result is not None:
        return result

    result = _map_numeric_type(data_type_lower, numeric_precision, numeric_scale)
    if result is not None:
        return result

    result = _map_temporal_type(data_type_lower)
    if result is not None:
        return result

    result = _map_special_type(data_type_lower)
    if result is not None:
        return result

    # Default to string for unknown types (safe fallback)
    return dt.String()
