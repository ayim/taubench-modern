import pytest

from agent_platform.core.platforms.bedrock.parameters import BedrockPlatformParameters


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
            "config_params": {},
            "updated_at": params.updated_at.isoformat(),
            "created_at": params.created_at.isoformat(),
            "platform_id": params.platform_id,
            "name": "bedrock-parameters",
            "models": {"anthropic": ["claude-3-5-sonnet"]},
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
            "config_params": {},
            "updated_at": params.updated_at.isoformat(),
            "created_at": params.created_at.isoformat(),
            "platform_id": params.platform_id,
            "name": "bedrock-parameters",
            "models": {"anthropic": ["claude-3-5-sonnet"]},
            "description": None,
            "alias": None,
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


class TestBedrockPlatformParametersExtended:
    """
    Extra behavioural and regression tests that complement the basic CRUD checks.
    """

    # ------------------------------------------------------------------ #
    # 1.  Extra Config kwargs handled on construction                     #
    # ------------------------------------------------------------------ #
    def test_init_with_extra_config_kwargs(self) -> None:
        params = BedrockPlatformParameters(
            region_name="us-east-1",
            config_params={"connect_timeout": 3, "read_timeout": 30},
        )

        # The advanced keys are preserved in a plain dict
        assert params.config_params == {"connect_timeout": 3, "read_timeout": 30}

    # ------------------------------------------------------------------ #
    # 2.  model_dump emits serialisable data, not live objects           #
    # ------------------------------------------------------------------ #
    def test_dump_contains_config_params_not_config_object(self) -> None:
        params = BedrockPlatformParameters(
            region_name="us-east-1",
            config_params={"retries": {"max_attempts": 5}},
        )

        dumped = params.model_dump()
        assert dumped["config_params"] == {"retries": {"max_attempts": 5}}
        assert "config" not in dumped  # raw Config object must never leak out

    # ------------------------------------------------------------------ #
    # 3.  dump --> validate round-trip (canonical new format)            #
    # ------------------------------------------------------------------ #
    def test_round_trip_via_dump_and_validate(self) -> None:
        original = BedrockPlatformParameters(
            region_name="us-east-1",
            config_params={"retries": {"max_attempts": 5}},
        )
        loaded = BedrockPlatformParameters.model_validate(original.model_dump())

        assert loaded == original

    # ------------------------------------------------------------------ #
    # 4.  Legacy payloads are still accepted                             #
    # ------------------------------------------------------------------ #
    @pytest.mark.parametrize(
        ("legacy_payload", "expected_config"),
        [
            (
                # a) old dataclasses.asdict() shape
                {
                    "region_name": "us-east-1",
                    "_extra_config_params": {"tcp_keepalive": True},
                    "aws_access_key_id": "bkah...blah...",
                },
                {"tcp_keepalive": True},
            ),
            (
                # b) stray Config-like keys at the top level
                {
                    "region_name": "us-east-1",
                    "tcp_keepalive": True,
                    "connect_timeout": 2,
                },
                {"tcp_keepalive": True, "connect_timeout": 2},
            ),
        ],
    )
    def test_validate_accepts_legacy_shapes(self, legacy_payload: dict, expected_config: dict) -> None:
        params = BedrockPlatformParameters.model_validate(legacy_payload)
        assert params.region_name == "us-east-1"
        assert params.config_params == expected_config

    # ------------------------------------------------------------------ #
    # 5.  Unknown kwargs picked up during validate (not __init__)        #
    # ------------------------------------------------------------------ #
    def test_unknown_top_level_keys_become_config_params(self) -> None:
        data = {"region_name": "us-east-1", "max_pool_connections": 50}
        params = BedrockPlatformParameters.model_validate(data)

        assert params.config_params == {"max_pool_connections": 50}

    # ------------------------------------------------------------------ #
    # 6.  model_copy preserves & merges config_params                    #
    # ------------------------------------------------------------------ #
    def test_model_copy_with_config_param_updates(self) -> None:
        base = BedrockPlatformParameters(
            region_name="us-east-1",
            config_params={"connect_timeout": 2},
        )
        clone = base.model_copy(update={"config_params": {"read_timeout": 60}})

        # original untouched
        assert base.config_params == {"connect_timeout": 2}

        # clone has overwritten the original config_params
        assert clone.config_params == {"read_timeout": 60}

    # ------------------------------------------------------------------ #
    # 7.  Equality considers config_params                               #
    # ------------------------------------------------------------------ #
    def test_equality_considers_config_params(self) -> None:
        a = BedrockPlatformParameters(region_name="us-east-1")
        b = BedrockPlatformParameters(
            region_name="us-east-1",
            config_params={"connect_timeout": 1},
        )
        assert a != b

    # ------------------------------------------------------------------ #
    # 8.  model_validate merges stray keys with existing config_params,  #
    #     giving precedence to stray keys                                #
    # ------------------------------------------------------------------ #
    def test_model_validate_merges_stray_keys_into_config_params_with_precedence(
        self,
    ) -> None:
        """
        Tests that model_validate merges stray keys into an existing config_params
        dictionary and that stray keys take precedence in case of conflict.
        """
        data = {
            "region_name": "us-east-1",
            "config_params": {
                "existing_key": "original_value",
                "overridden_key": "original_config_value",
            },
            "new_stray_key": "new_value",
            "overridden_key": "stray_value_takes_precedence",  # This should overwrite
        }
        params = BedrockPlatformParameters.model_validate(data)

        assert params.region_name == "us-east-1"
        assert params.config_params == {
            "existing_key": "original_value",
            "overridden_key": "stray_value_takes_precedence",
            "new_stray_key": "new_value",
        }
