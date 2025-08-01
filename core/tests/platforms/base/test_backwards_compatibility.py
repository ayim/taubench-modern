from datetime import datetime

from agent_platform.core.platforms.azure import AzureOpenAIPlatformParameters
from agent_platform.core.platforms.base import PlatformParameters
from agent_platform.core.platforms.bedrock import BedrockPlatformParameters
from agent_platform.core.platforms.cortex import CortexPlatformParameters
from agent_platform.core.platforms.openai import OpenAIPlatformParameters
from agent_platform.core.utils import SecretString


class TestPlatformParametersBackwardsCompatibility:
    """Test backwards compatibility with legacy stored platform configuration data."""

    def test_legacy_openai_config_deserialization(self):
        """Test that legacy OpenAI configuration data (missing base fields) can be loaded."""
        # This is what's actually stored in the database for legacy OpenAI configs
        legacy_data = {"kind": "openai", "openai_api_key": "sk-test-key-12345"}

        # Should deserialize without errors
        params = PlatformParameters.model_validate(legacy_data)

        # Verify it's the right type
        assert isinstance(params, OpenAIPlatformParameters)
        assert params.kind == "openai"
        assert params.openai_api_key is not None
        assert params.openai_api_key.get_secret_value() == "sk-test-key-12345"

        # Verify base class fields get proper defaults
        assert params.platform_id is not None  # Gets UUID default
        assert params.name == "openai-parameters"  # Gets auto-generated name
        assert params.description is None  # Default
        assert isinstance(params.created_at, datetime)  # Gets datetime default
        assert isinstance(params.updated_at, datetime)  # Gets datetime default

        # Verify we defaulted the allowlist to 4.1 (what server _used to pick_
        # when there was no constraint for this Platform)
        assert params.models == {"openai": ["gpt-4-1"]}

    def test_legacy_bedrock_config_deserialization(self):
        """Test that legacy Bedrock configuration data can be loaded."""
        legacy_data = {
            "kind": "bedrock",
            "region_name": "us-east-1",
            "aws_access_key_id": "ABCDEFGHIJKLMNOP",
            "aws_secret_access_key": "secretkey123",
            "config_params": {},
        }

        params = PlatformParameters.model_validate(legacy_data)

        assert isinstance(params, BedrockPlatformParameters)
        assert params.kind == "bedrock"
        assert params.region_name == "us-east-1"
        assert params.aws_access_key_id == "ABCDEFGHIJKLMNOP"
        assert params.aws_secret_access_key == "secretkey123"
        assert params.config_params == {}

        # Base class fields should get defaults
        assert params.platform_id is not None
        assert params.name == "bedrock-parameters"
        assert isinstance(params.created_at, datetime)
        assert isinstance(params.updated_at, datetime)

        # Verify we defaulted the allowlist to claude-3-5-sonnet
        # (what server _used to pick_ when there was no constraint for this Platform)
        assert params.models == {"anthropic": ["claude-3-5-sonnet"]}

    def test_legacy_cortex_config_deserialization(self):
        """Test that legacy Cortex configuration data can be loaded."""
        legacy_data = {
            "kind": "cortex",
            "snowflake_username": "",
            "snowflake_account": "",
            "snowflake_warehouse": "",
            "snowflake_database": "",
            "snowflake_schema": "",
            "snowflake_role": "",
        }

        params = PlatformParameters.model_validate(legacy_data)

        assert isinstance(params, CortexPlatformParameters)
        assert params.kind == "cortex"
        assert params.snowflake_username == ""
        assert params.snowflake_account == ""

        # Base class fields should get defaults
        assert params.platform_id is not None
        assert params.name == "cortex-parameters"
        assert isinstance(params.created_at, datetime)
        assert isinstance(params.updated_at, datetime)

        # Verify we defaulted the allowlist to claude-3-5-sonnet
        # (what server _used to pick_ when there was no constraint for this Platform)
        assert params.models == {"anthropic": ["claude-3-5-sonnet"]}

    def test_legacy_data_with_some_base_fields(self):
        """Test legacy data that has some but not all base class fields."""
        legacy_data = {
            "kind": "openai",
            "openai_api_key": "sk-test-key",
            "name": "My Custom Config",  # Has custom name
            "description": "Legacy config with partial fields",
            # Missing: platform_id, models, created_at, updated_at
        }

        params = PlatformParameters.model_validate(legacy_data)

        assert isinstance(params, OpenAIPlatformParameters)
        assert params.name == "My Custom Config"  # Preserves existing name
        assert params.description == "Legacy config with partial fields"

        # Missing fields should get defaults
        assert params.platform_id is not None
        assert isinstance(params.created_at, datetime)
        assert isinstance(params.updated_at, datetime)

        # Verify we defaulted the allowlist to 4.1 (what server _used to pick_
        # when there was no constraint for this Platform)
        assert params.models == {"openai": ["gpt-4-1"]}

    def test_legacy_data_with_string_timestamps(self):
        """Test legacy data that has timestamps as ISO strings."""
        legacy_data = {
            "kind": "openai",
            "openai_api_key": "sk-test-key",
            "created_at": "2023-01-15T10:30:00+00:00",
            "updated_at": "2023-06-20T14:45:30+00:00",
        }

        params = PlatformParameters.model_validate(legacy_data)

        assert isinstance(params, OpenAIPlatformParameters)

        # Timestamps should be converted from strings to datetime objects
        assert isinstance(params.created_at, datetime)
        assert isinstance(params.updated_at, datetime)
        assert params.created_at.year == 2023
        assert params.created_at.month == 1
        assert params.created_at.day == 15
        assert params.updated_at.year == 2023
        assert params.updated_at.month == 6
        assert params.updated_at.day == 20

    def test_direct_subclass_validation_with_legacy_data(self):
        """Test that calling model_validate directly on subclasses works with legacy data."""
        legacy_data = {
            # Note: No "kind" field - this simulates direct subclass usage
            "openai_api_key": "sk-direct-test",
            "created_at": "2023-01-01T00:00:00+00:00",  # String timestamp
        }

        # This should work when called directly on the subclass
        params = OpenAIPlatformParameters.model_validate(legacy_data)

        assert isinstance(params, OpenAIPlatformParameters)
        assert params.openai_api_key is not None
        assert params.openai_api_key.get_secret_value() == "sk-direct-test"

        # Timestamp should be converted from string to datetime
        assert isinstance(params.created_at, datetime)
        assert params.created_at.year == 2023

        # Missing fields should get defaults
        assert params.platform_id is not None
        assert params.name == "openai-parameters"
        assert isinstance(params.updated_at, datetime)

    def test_model_dump_roundtrip_compatibility(self):
        """Test that data saved with model_dump() can be loaded back correctly."""
        # Create a parameter instance
        original = OpenAIPlatformParameters(
            name="Test Config",
            description="Test description",
            openai_api_key=SecretString("sk-test-key"),
        )

        # Simulate saving to database (convert to dict, then back)
        dumped_data = original.model_dump()

        # Simulate loading from database
        loaded = PlatformParameters.model_validate(dumped_data)

        assert isinstance(loaded, OpenAIPlatformParameters)
        assert loaded.name == original.name
        assert loaded.description == original.description
        assert loaded.openai_api_key is not None
        assert original.openai_api_key is not None
        assert (
            loaded.openai_api_key.get_secret_value() == original.openai_api_key.get_secret_value()
        )
        assert loaded.platform_id == original.platform_id

        # Note: timestamps might be slightly different due to serialization/deserialization,
        # but they should both be datetime objects
        assert isinstance(loaded.created_at, datetime)
        assert isinstance(loaded.updated_at, datetime)

    def test_post_init_converts_string_datetimes(self):
        """Test that __post_init__ converts string datetimes to datetime objects."""
        # This tests the safety net in __post_init__ for cases where string datetimes
        # might slip through model_validate or be passed directly to constructor

        # We need to use a concrete subclass and bypass normal validation
        # by directly setting field values after construction
        params = OpenAIPlatformParameters(
            openai_api_key=SecretString("sk-test-key"),
        )

        # Simulate what might happen if string datetimes slip through somehow
        # (using object.__setattr__ to bypass frozen dataclass protection)
        import datetime as dt

        object.__setattr__(params, "created_at", "2023-01-15T10:30:00+00:00")
        object.__setattr__(params, "updated_at", "2023-06-20T14:45:30+00:00")

        # Trigger __post_init__ conversion by creating a new instance
        # with string datetime values (testing the safety net)
        new_params = OpenAIPlatformParameters(
            openai_api_key=SecretString("sk-test-key"),
            created_at="2023-01-15T10:30:00+00:00",  # type: ignore
            updated_at="2023-06-20T14:45:30+00:00",  # type: ignore
            name="test-config",
        )

        # The __post_init__ should have converted the strings to datetime objects
        assert isinstance(new_params.created_at, dt.datetime)
        assert isinstance(new_params.updated_at, dt.datetime)
        assert new_params.created_at.year == 2023
        assert new_params.created_at.month == 1
        assert new_params.created_at.day == 15
        assert new_params.updated_at.year == 2023
        assert new_params.updated_at.month == 6
        assert new_params.updated_at.day == 20

    def test_post_init_rejects_invalid_datetime_strings(self):
        """Test that __post_init__ raises clear errors for invalid datetime strings."""
        import pytest

        # Test invalid created_at format
        with pytest.raises(
            ValueError, match=r"Invalid datetime string for created_at.*Expected ISO format"
        ):
            OpenAIPlatformParameters(
                openai_api_key=SecretString("sk-test-key"),
                created_at="not-a-valid-datetime",  # type: ignore
                name="test-config",
            )

        # Test invalid updated_at format
        with pytest.raises(
            ValueError, match=r"Invalid datetime string for updated_at.*Expected ISO format"
        ):
            OpenAIPlatformParameters(
                openai_api_key=SecretString("sk-test-key"),
                updated_at="2023-13-40T25:70:80",  # type: ignore  # Invalid date/time components
                name="test-config",
            )

    def test_model_dump_handles_datetime_objects_bedrock(self):
        """Test that model_dump correctly serializes datetime objects using Bedrock parameters."""
        # Create a Bedrock parameter instance with datetime objects (normal case)
        params = BedrockPlatformParameters(
            name="Test Bedrock Config",
            region_name="us-east-1",
        )

        # Ensure we have datetime objects
        assert isinstance(params.created_at, datetime)
        assert isinstance(params.updated_at, datetime)

        # model_dump should convert datetime objects to ISO strings
        dumped = params.model_dump()

        assert isinstance(dumped["created_at"], str)
        assert isinstance(dumped["updated_at"], str)
        # Should be valid ISO format
        assert "T" in dumped["created_at"]
        assert "T" in dumped["updated_at"]
        # Should be able to parse back to datetime
        datetime.fromisoformat(dumped["created_at"])
        datetime.fromisoformat(dumped["updated_at"])

    def test_model_dump_handles_string_datetimes_azure(self):
        """Test that model_dump handles string datetime values gracefully using Azure parameters."""
        # Create an Azure parameter instance first
        params = AzureOpenAIPlatformParameters(
            name="Test Azure Config",
            azure_endpoint_url="https://test.openai.azure.com",
            azure_api_key=SecretString("test-key"),
        )

        # Simulate the scenario where somehow we have string datetime values
        # (this mimics the original bug scenario)
        string_created_at = "2023-01-15T10:30:00+00:00"
        string_updated_at = "2023-06-20T14:45:30+00:00"

        # Force string values (bypassing frozen dataclass protection)
        object.__setattr__(params, "created_at", string_created_at)
        object.__setattr__(params, "updated_at", string_updated_at)

        # Verify they are strings now
        assert isinstance(params.created_at, str)
        assert isinstance(params.updated_at, str)

        # model_dump should handle string values gracefully (not crash)
        dumped = params.model_dump()

        # String values should pass through unchanged
        assert dumped["created_at"] == string_created_at
        assert dumped["updated_at"] == string_updated_at
        assert isinstance(dumped["created_at"], str)
        assert isinstance(dumped["updated_at"], str)

    def test_model_dump_handles_mixed_datetime_types_bedrock(self):
        """Test model_dump with one datetime object and one string datetime."""
        # Create a Bedrock parameter instance
        params = BedrockPlatformParameters(
            name="Mixed Test Config",
            region_name="us-west-2",
        )

        # Mix: keep created_at as datetime, make updated_at a string
        string_updated_at = "2023-06-20T14:45:30+00:00"
        object.__setattr__(params, "updated_at", string_updated_at)

        # Verify mixed types
        assert isinstance(params.created_at, datetime)
        assert isinstance(params.updated_at, str)

        # model_dump should handle both correctly
        dumped = params.model_dump()

        # created_at (datetime) should be converted to string
        assert isinstance(dumped["created_at"], str)
        assert "T" in dumped["created_at"]

        # updated_at (string) should pass through unchanged
        assert dumped["updated_at"] == string_updated_at
        assert isinstance(dumped["updated_at"], str)
