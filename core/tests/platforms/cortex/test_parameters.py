import pytest

from agent_platform.core.platforms.cortex.parameters import CortexPlatformParameters
from agent_platform.core.utils import SecretString


class TestCortexPlatformParameters:
    """Tests for the Cortex platform parameters."""

    @pytest.fixture(autouse=True)
    def _clear_snowflake_env_vars(self, monkeypatch):
        """Ensure Snowflake environment variables are
        unset for all tests in this class."""
        monkeypatch.delenv("SNOWFLAKE_ACCOUNT", raising=False)
        monkeypatch.delenv("SNOWFLAKE_HOST", raising=False)
        # You may want to clear other Snowflake env vars as well
        monkeypatch.delenv("SNOWFLAKE_USERNAME", raising=False)
        monkeypatch.delenv("SNOWFLAKE_PASSWORD", raising=False)
        monkeypatch.delenv("SNOWFLAKE_WAREHOUSE", raising=False)
        monkeypatch.delenv("SNOWFLAKE_DATABASE", raising=False)
        monkeypatch.delenv("SNOWFLAKE_SCHEMA", raising=False)
        monkeypatch.delenv("SNOWFLAKE_ROLE", raising=False)

    def test_initialization_with_defaults(self) -> None:
        """Test that the parameters initialize with default values."""
        params = CortexPlatformParameters()

        # Check default values
        assert params.snowflake_account is None
        assert params.snowflake_host is None
        assert params.snowflake_username is None
        assert params.snowflake_password is None
        assert params.snowflake_warehouse is None
        assert params.snowflake_database is None
        assert params.snowflake_schema is None
        assert params.snowflake_role is None

    def test_initialization_with_values(self) -> None:
        """Test that the parameters initialize with specified values."""
        params = CortexPlatformParameters(
            snowflake_account="test-account",
            snowflake_username="test-user",
            snowflake_password=SecretString("test-password"),
            snowflake_warehouse="test-warehouse",
            snowflake_database="test-database",
            snowflake_schema="test-schema",
            snowflake_role="test-role",
        )

        # Check specified values
        assert params.snowflake_account == "test-account"
        assert params.snowflake_username == "test-user"
        assert params.snowflake_password is not None
        assert params.snowflake_password.get_secret_value() == "test-password"
        assert params.snowflake_warehouse == "test-warehouse"
        assert params.snowflake_database == "test-database"
        assert params.snowflake_schema == "test-schema"
        assert params.snowflake_role == "test-role"

        # Host is computed from account
        assert params.snowflake_host == "test-account.snowflakecomputing.com"

    def test_model_dump(self) -> None:
        """Test that model_dump works correctly with exclude_none=True."""
        params = CortexPlatformParameters()

        result = params.model_dump(exclude_none=True)

        # Check result
        assert result == {
            "kind": "cortex",
            "name": "cortex-parameters",
            "created_at": params.created_at.isoformat(),
            "updated_at": params.updated_at.isoformat(),
            "platform_id": params.platform_id,
            "models": {"anthropic": ["claude-3-5-sonnet"]},
        }

        # Fields with None values should be excluded
        assert "snowflake_account" not in result
        assert "snowflake_host" not in result
        assert "snowflake_username" not in result
        assert "snowflake_password" not in result
        assert "snowflake_warehouse" not in result
        assert "snowflake_database" not in result
        assert "snowflake_schema" not in result
        assert "snowflake_role" not in result

    def test_model_dump_include_none(self) -> None:
        """Test that model_dump works correctly with exclude_none=False."""
        params = CortexPlatformParameters()

        result = params.model_dump(exclude_none=False)

        # Check result
        assert result == {
            "kind": "cortex",
            "name": "cortex-parameters",
            "alias": None,
            "description": None,
            "models": {"anthropic": ["claude-3-5-sonnet"]},
            "created_at": params.created_at.isoformat(),
            "updated_at": params.updated_at.isoformat(),
            "platform_id": params.platform_id,
            "snowflake_account": None,
            "snowflake_host": None,
            "snowflake_username": None,
            "snowflake_password": None,
            "snowflake_warehouse": None,
            "snowflake_database": None,
            "snowflake_schema": None,
            "snowflake_role": None,
        }

    def test_model_copy(self) -> None:
        """Test that model_copy works correctly."""
        params = CortexPlatformParameters()

        # Make a copy with updated values
        updated_params = params.model_copy(
            update={
                "snowflake_account": "test-account",
                "snowflake_username": "test-user",
                "snowflake_password": SecretString("test-password"),
                "snowflake_warehouse": "test-warehouse",
                "snowflake_database": "test-database",
                "snowflake_schema": "test-schema",
                "snowflake_role": "test-role",
            },
        )

        # Check that the original params are unchanged
        assert params.snowflake_account is None
        assert params.snowflake_host is None
        assert params.snowflake_username is None
        assert params.snowflake_password is None
        assert params.snowflake_warehouse is None
        assert params.snowflake_database is None
        assert params.snowflake_schema is None
        assert params.snowflake_role is None

        # Check that the updated params have the new values
        assert updated_params.snowflake_account == "test-account"
        assert updated_params.snowflake_username == "test-user"
        assert updated_params.snowflake_password is not None
        assert updated_params.snowflake_password.get_secret_value() == "test-password"
        assert updated_params.snowflake_warehouse == "test-warehouse"
        assert updated_params.snowflake_database == "test-database"
        assert updated_params.snowflake_schema == "test-schema"
        assert updated_params.snowflake_role == "test-role"

        # Host is computed from account
        assert updated_params.snowflake_host == "test-account.snowflakecomputing.com"
