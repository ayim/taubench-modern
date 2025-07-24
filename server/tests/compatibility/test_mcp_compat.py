from agent_platform.server.api.private_v2.compatibility.agent_compat import MCPVariableCompat


class DummyVar:
    def __init__(self, t: str, **kwargs):
        self.type = t
        for k, v in kwargs.items():
            setattr(self, k, v)


def test_from_variable_string():
    var = DummyVar("string", description="desc", value="val")
    compat = MCPVariableCompat.from_variable(var)
    assert isinstance(compat, MCPVariableCompat)
    assert compat.type == "string"
    assert compat.description == "desc"
    if isinstance(compat, MCPVariableCompat):
        assert compat.value == "**********"  # masked by default
    compat = MCPVariableCompat.from_variable(var, reveal_sensitive=True)
    if isinstance(compat, MCPVariableCompat):
        assert compat.value == "val"


def test_from_variable_secret():
    var = DummyVar("secret", description="desc", value="secretval")
    compat = MCPVariableCompat.from_variable(var)
    assert isinstance(compat, MCPVariableCompat)
    assert compat.type == "secret"
    assert compat.description == "desc"
    if isinstance(compat, MCPVariableCompat):
        assert compat.value == "**********"
    compat = MCPVariableCompat.from_variable(var, reveal_sensitive=True)
    if isinstance(compat, MCPVariableCompat):
        assert compat.value == "secretval"


def test_from_variable_oauth2_secret():
    var = DummyVar(
        "oauth2-secret",
        provider="prov",
        scopes=["scope1", "scope2"],
        description="desc",
        value="oauthval",
    )
    compat = MCPVariableCompat.from_variable(var)
    assert isinstance(compat, MCPVariableCompat)
    assert compat.type == "oauth2-secret"
    assert compat.provider == "prov"
    assert compat.scopes == ["scope1", "scope2"]
    assert compat.description == "desc"
    if isinstance(compat, MCPVariableCompat):
        assert compat.value == "**********"
    compat = MCPVariableCompat.from_variable(var, reveal_sensitive=True)
    if isinstance(compat, MCPVariableCompat):
        assert compat.value == "oauthval"


def test_from_variable_data_server_info():
    var = DummyVar("data-server-info", value="datainfo")
    compat = MCPVariableCompat.from_variable(var)
    assert isinstance(compat, MCPVariableCompat)
    assert compat.type == "data-server-info"
    if isinstance(compat, MCPVariableCompat):
        assert compat.value == "**********"
    compat = MCPVariableCompat.from_variable(var, reveal_sensitive=True)
    if isinstance(compat, MCPVariableCompat):
        assert compat.value == "datainfo"


def test_from_variable_legacy_string():
    # Legacy: just a string
    result = MCPVariableCompat.from_variable("sensitive", reveal_sensitive=False)
    assert isinstance(result, str)
    assert result == "**********"
    result = MCPVariableCompat.from_variable("nonsensitive", reveal_sensitive=True)
    assert isinstance(result, str)
    assert result == "nonsensitive"


def test_from_variable_fallback():
    # Unknown type, should fallback to str(var)
    class Unknown:
        pass

    var = Unknown()
    result = MCPVariableCompat.from_variable(var)
    assert isinstance(result, str)
    assert result == str(var)
