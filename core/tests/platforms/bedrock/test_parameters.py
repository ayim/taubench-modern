from agent_platform_core.platforms.bedrock.parameters import BedrockPlatformParameters


class TestBedrockPlatformParameters:
    """Tests for the Bedrock platform parameters."""

    def test_initialization_with_defaults(self) -> None:
        """Test that the parameters initialize with default values."""
        params = BedrockPlatformParameters()

        # Check default values
        assert params.region_name is None
        assert params.aws_access_key_id is None
        assert params.aws_secret_access_key is None
        assert params.aws_session_token is None
        assert params.endpoint_url is None

    def test_initialization_with_values(self) -> None:
        """Test that the parameters initialize with specified values."""
        params = BedrockPlatformParameters(
            region_name="us-west-2",
            aws_access_key_id="test-access-key",
            aws_secret_access_key="test-secret-key",
            aws_session_token="test-session-token",
            endpoint_url="https://example.com",
        )

        # Check specified values
        assert params.region_name == "us-west-2"
        assert params.aws_access_key_id == "test-access-key"
        assert params.aws_secret_access_key == "test-secret-key"
        assert params.aws_session_token == "test-session-token"
        assert params.endpoint_url == "https://example.com"

    def test_model_dump(self) -> None:
        """Test that model_dump works correctly with exclude_none=True."""
        params = BedrockPlatformParameters(
            region_name="us-west-2",
            aws_access_key_id="test-access-key",
            aws_secret_access_key="test-secret-key",
        )

        result = params.model_dump(exclude_none=True)

        # Check result
        assert result == {
            "kind": "bedrock",
            "region_name": "us-west-2",
            "aws_access_key_id": "test-access-key",
            "aws_secret_access_key": "test-secret-key",
        }

        # Fields with None values should be excluded
        assert "aws_session_token" not in result
        assert "profile_name" not in result
        assert "endpoint_url" not in result

    def test_model_dump_include_none(self) -> None:
        """Test that model_dump works correctly with exclude_none=False."""
        params = BedrockPlatformParameters(
            region_name="us-west-2",
            aws_access_key_id="test-access-key",
            aws_secret_access_key="test-secret-key",
        )

        result = params.model_dump(exclude_none=False)

        # Check result
        assert result == {
            "kind": "bedrock",
            "region_name": "us-west-2",
            "api_version": None,
            "use_ssl": None,
            "verify": None,
            "endpoint_url": None,
            "aws_access_key_id": "test-access-key",
            "aws_secret_access_key": "test-secret-key",
            "aws_session_token": None,
            "config": None,
        }

    def test_model_copy(self) -> None:
        """Test that model_copy works correctly."""
        params = BedrockPlatformParameters(
            region_name="us-west-2",
            aws_access_key_id="test-access-key",
            aws_secret_access_key="test-secret-key",
        )

        # Make a copy with updated values
        updated_params = params.model_copy(
            update={
                "region_name": "us-east-1",
                "endpoint_url": "https://example.com",
            },
        )

        # Check that the original params are unchanged
        assert params.region_name == "us-west-2"
        assert params.aws_access_key_id == "test-access-key"
        assert params.aws_secret_access_key == "test-secret-key"
        assert params.endpoint_url is None

        # Check that the updated params have the new values
        assert updated_params.region_name == "us-east-1"
        assert updated_params.aws_access_key_id == "test-access-key"
        assert updated_params.aws_secret_access_key == "test-secret-key"
        assert updated_params.endpoint_url == "https://example.com"
