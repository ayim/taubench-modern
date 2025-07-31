from datetime import datetime

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
