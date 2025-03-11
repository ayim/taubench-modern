import os
import math
from typing import Any, List, TYPE_CHECKING

from langchain.embeddings.base import Embeddings
from pydantic import BaseModel, Field, SecretStr, model_validator
import structlog

from agent_architecture.chat_models.chat_snowflake_utils import get_connection_details

# Try to import NumPy, but continue if not available
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

if TYPE_CHECKING:
    from snowflake.snowpark import Session


logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class SnowflakeCortexEmbeddings(BaseModel, Embeddings):
    """
    A Snowflake Cortex-powered Embeddings client that calls Snowflake's built-in
    EMBED_TEXT_768 or EMBED_TEXT_1024 functions to generate embeddings. 
    Uses a Snowpark session for authentication and SQL queries.
    """

    # -------------------------------------------------------------------------
    # Connection/Auth fields
    # -------------------------------------------------------------------------
    snowflake_username: str | None = Field(
        default=None, description="Snowflake username"
    )
    snowflake_password: SecretStr | None = Field(
        default=None, description="Snowflake password"
    )
    snowflake_host: str | None = Field(
        default=None,
        description="Full Snowflake host domain (overrides auto-building from account).",
    )
    snowflake_account: str | None = Field(
        default=None,
        description="Snowflake account identifier, e.g. 'xy12345.us-east-2'",
    )
    snowflake_role: str | None = Field(
        default=None, description="Snowflake role identifier, e.g. 'MY_ROLE'"
    )
    snowflake_warehouse: str | None = Field(
        default=None, description="Snowflake warehouse identifier, e.g. 'COMPUTE_WH'"
    )
    snowflake_database: str | None = Field(
        default=None, description="Snowflake database identifier, e.g. 'MY_DB'"
    )
    snowflake_schema: str | None = Field(
        default=None, description="Snowflake schema identifier, e.g. 'MY_SCHEMA'"
    )

    # -------------------------------------------------------------------------
    # Embedding configuration
    # -------------------------------------------------------------------------
    model: str = Field(
        default="snowflake-arctic-embed-m",
        description="Name of the Snowflake embedding model. E.g. 'snowflake-arctic-embed-m'"
    )
    dimension: int = Field(
        default=768,
        description="Dimension of the returned embeddings. Must match the function (768 or 1024)."
    )
    normalize: bool = Field(
        default=True,
        description="Whether to normalize embeddings into unit-length vectors."
    )

    # -------------------------------------------------------------------------
    # Internal state
    # -------------------------------------------------------------------------
    _session: Any = None  # Will hold a Snowpark Session once connected

    @model_validator(mode="before")
    def validate_auth(cls, values: dict[str, Any]) -> dict[str, Any]:
        """
        A pre-check validator that sets up `snowflake_host` from the account info or
        environment variable if not explicitly provided.
        """
        if not values.get("snowflake_host"):
            acct = values.get("snowflake_account")
            if acct:
                values["snowflake_host"] = f"{acct}.snowflakecomputing.com"

        container_host = os.environ.get("SNOWFLAKE_HOST")
        if container_host:
            values["snowflake_host"] = container_host

        # Replace any underscores with hyphens in the hostname for SSL certificate compliance
        # According to RFC 1035 (and related standards), underscores are not allowed in 
        # hostnames, which can cause SSL certificate validation to fail. 
        if values.get("snowflake_host"):
            values["snowflake_host"] = values["snowflake_host"].replace("_", "-")

        return values

    def _get_or_create_session(self) -> "Session":
        """
        Creates and caches a Snowpark session using the stored configuration
        (role, warehouse, database, schema, username, password, account).
        
        Returns:
            A live Snowflake Snowpark Session object.
        """
        if self._session is not None:
            logger.debug("Returning existing Snowflake session.")
            return self._session

        try:
            from snowflake.snowpark import Session
        except ImportError as e:
            logger.exception(f"snowflake-snowpark-python is not installed or failed to import: {e}")
            raise ImportError(
                "snowflake-snowpark-python is required for SnowflakeCortexEmbeddings. "
                "Please install via `pip install snowflake-snowpark-python`."
            ) from e

        conn_details = get_connection_details(
            role=self.snowflake_role,
            warehouse=self.snowflake_warehouse,
            database=self.snowflake_database,
            schema=self.snowflake_schema,
            username=self.snowflake_username,
            password=self.snowflake_password.get_secret_value() if self.snowflake_password else None,
            account=self.snowflake_account,
        )

        logger.info(
            f"Creating new Snowflake session. "
            f"account={self.snowflake_account}, role={self.snowflake_role}, "
            f"warehouse={self.snowflake_warehouse}, database={self.snowflake_database}, "
            f"schema={self.snowflake_schema}"
        )

        self._session = Session.builder.configs(conn_details).getOrCreate()
        
        # Handle warehouse selection to prevent "No active warehouse selected" errors
        if conn_details["warehouse"]:
            logger.debug(f"Setting active warehouse to: {conn_details['warehouse']}")
            self._session.sql(f"USE WAREHOUSE {conn_details['warehouse']}").collect()
        else:
            # Try to automatically find an available warehouse if none was specified
            logger.info("No warehouse specified. Attempting to find an available warehouse...")
            try:
                # Get list of warehouses the user has access to
                warehouses_df = self._session.sql("SHOW WAREHOUSES").collect()
                if warehouses_df and len(warehouses_df) > 0:
                    # Extract warehouse names (Snowflake returns column names in uppercase)
                    available_warehouses = [row["name"] for row in warehouses_df]
                    if available_warehouses:
                        selected_warehouse = available_warehouses[0]
                        logger.info(f"Automatically selected warehouse: {selected_warehouse}")
                        self._session.sql(f"USE WAREHOUSE {selected_warehouse}").collect()
                        # Save for future reference
                        self.snowflake_warehouse = selected_warehouse
                    else:
                        logger.warning("No warehouses found that the user has access to.")
                else:
                    logger.warning("Failed to retrieve warehouse list. Embeddings may fail.")
            except Exception as e:
                logger.warning(f"Error when trying to automatically select a warehouse: {e}")
                logger.warning("Cortex embeddings require a compute warehouse. Operations may fail.")

        logger.info("Snowflake session created successfully.")
        return self._session

    def close(self) -> None:
        """
        Close the Snowpark session if it exists. This method can be used to 
        explicitly close the session once you're done with embeddings.
        """
        if self._session is not None:
            logger.debug("Closing Snowflake session.")
            try:
                self._session.close()
            except Exception as e:
                logger.warning(f"Failed to close Snowflake session cleanly: {e}")
            self._session = None

    def __del__(self) -> None:
        """Destructor hook to ensure the Snowpark session is closed."""
        self.close()

    def _get_sql_function_name(self) -> str:
        """
        Return the correct EMBED_TEXT function name: EMBED_TEXT_768 or EMBED_TEXT_1024,
        depending on self.dimension.

        Raises:
            ValueError: If the dimension is not supported.
        """
        if self.dimension == 768:
            return "EMBED_TEXT_768"
        elif self.dimension == 1024:
            return "EMBED_TEXT_1024"
        else:
            logger.error(f"Unsupported embedding dimension: {self.dimension}")
            raise ValueError(
                f"Unsupported embedding dimension '{self.dimension}'. Must be 768 or 1024."
            )

    def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Call Snowflake's EMBED_TEXT_* function on a batch of texts using Snowpark.

        Args:
            texts (List[str]): The list of texts to embed.

        Returns:
            A list of embeddings (list of floats) corresponding to each text.
        """
        if not texts:
            logger.debug("No texts provided to embed; returning empty list.")
            return []

        try:
            from snowflake.snowpark.functions import call_function, col as snowpark_col
            from snowflake.snowpark.types import StructField, StructType, StringType
        except ImportError as e:
            logger.exception(f"Failed to import snowflake.snowpark modules: {e}")
            raise ImportError(
                "snowflake-snowpark-python is required for SnowflakeCortexEmbeddings. "
                "Please install via `pip install snowflake-snowpark-python`."
            ) from e

        session = self._get_or_create_session()
        func_name = self._get_sql_function_name()

        logger.debug(
            f"Embedding batch of texts in Snowflake. model={self.model}, "
            f"dimension={self.dimension}, normalize={self.normalize}, "
            f"batch_size={len(texts)}, sql_function={func_name}"
        )

        text_rows = [(t,) for t in texts]
        text_schema = StructType([StructField("text", StringType())])
        df_input = session.create_dataframe(text_rows, schema=text_schema)

        embed_udf_call = call_function(
            f"SNOWFLAKE.CORTEX.{func_name}",
            self.model,
            snowpark_col("text")
        ).alias("embedding")

        df_embeds = df_input.select(embed_udf_call)
        rows = df_embeds.collect()
        logger.debug(f"Collected embeddings from Snowflake. row_count={len(rows)}")

        embeddings = []
        for r in rows:
            emb = list(r["EMBEDDING"])  # Convert Snowflake Vector to a Python list
            if self.normalize:
                emb = self._normalize_vector(emb)
            embeddings.append(emb)

        logger.debug(f"Batch embedding completed. resulting_count={len(embeddings)}")
        return embeddings

    @staticmethod
    def _normalize_vector(vec: List[float]) -> List[float]:
        """
        Normalize a vector to unit length. Uses NumPy if available,
        otherwise falls back to a pure Python approach.

        Args:
            vec (List[float]): Vector to be normalized.

        Returns:
            (List[float]): The unit-normalized vector, or the original 
            vector if its norm is zero.
        """
        if NUMPY_AVAILABLE:
            arr = np.array(vec, dtype=np.float32)
            norm = np.linalg.norm(arr)
            if norm == 0.0:
                logger.debug("Encountered zero-length vector during normalization.")
                return vec
            return (arr / norm).tolist()
        else:
            norm = math.sqrt(sum(x * x for x in vec))
            if norm == 0.0:
                logger.debug("Encountered zero-length vector during normalization.")
                return vec
            return [x / norm for x in vec]

    # ------------------------------
    # LangChain Embeddings interface
    # ------------------------------
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Compute embeddings for a list of documents using Snowflake Cortex.
        """
        logger.info(f"Embedding multiple documents. num_documents={len(texts)}")
        return self._embed_batch(texts)

    def embed_query(self, text: str) -> List[float]:
        """
        Compute an embedding for a single query text.

        Args:
            text (str): The text for which to generate an embedding.

        Returns:
            The embedding as a list of floats.
        """
        logger.info(f"Embedding a single query. text_length={len(text)}")
        if not text:
            logger.debug("Received empty text for query embedding.")
            return []
        return self._embed_batch([text])[0]
