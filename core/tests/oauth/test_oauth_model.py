def test_oauth_config_authentication_metadata_handling():
    from agent_platform.core.oauth.oauth_models import AuthenticationMetadataClientCredentials, OAuthConfig

    # Test with None authentication metadata
    srv1 = OAuthConfig(authentication_metadata=None)
    assert srv1.authentication_metadata is None

    # Test with empty authentication metadata
    srv2 = OAuthConfig(authentication_metadata={})
    assert srv2.authentication_metadata == {}

    # Test with populated authentication metadata
    srv3 = OAuthConfig(
        authentication_metadata=dict(
            client_id="client_id",
            client_secret="client_secret",
            scope="scope",
            endpoint="endpoint",
        ),
    )
    assert isinstance(srv3.authentication_metadata, AuthenticationMetadataClientCredentials)
