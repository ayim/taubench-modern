import json
from collections.abc import Callable
from pathlib import Path
from textwrap import dedent

import pytest

from agent_platform.core.platforms.cortex.connect import (
    SnowflakeAuthenticationError,
    SPCSConnnectionConfig,
    get_connection_details,
)
from agent_platform.server.configuration_manager import ConfigurationService

# ---------------------------------------------------------------------------
# helpers / fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    """Remove Snowflake-related env-vars for every test."""
    for var in (
        "SNOWFLAKE_ACCOUNT",
        "SNOWFLAKE_HOST",
        "SNOWFLAKE_USERNAME",
        "SNOWFLAKE_PASSWORD",
        "SNOWFLAKE_WAREHOUSE",
        "SNOWFLAKE_DATABASE",
        "SNOWFLAKE_SCHEMA",
        "SNOWFLAKE_ROLE",
    ):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture(autouse=True)
def _reset_config_service():
    saved = ConfigurationService.get_instance(reinitialize=True)
    ConfigurationService.set_for_testing(saved)
    yield
    ConfigurationService.reset()


def _patch_token_file(
    monkeypatch,
    exists: bool,
    content: str | None = None,
):
    """
    Globally monkey-patch Path.exists / read_text so we can
    fake the container token presence *without* touching the FS.
    """
    real_exists = Path.exists
    real_read_text = Path.read_text

    def fake_exists(self: Path) -> bool:
        return (
            self.as_posix() == "/snowflake/session/token" and exists
        ) or real_exists(self)

    def fake_read_text(self: Path, *a, **kw):
        if self.as_posix() == "/snowflake/session/token":
            return content or ""
        return real_read_text(self, *a, **kw)

    monkeypatch.setattr(Path, "exists", fake_exists, raising=False)
    monkeypatch.setattr(Path, "read_text", fake_read_text, raising=False)


def _write_sf_auth(tmp_path: Path, payload: dict) -> Path:
    auth_dir = tmp_path / ".sema4ai"
    auth_dir.mkdir()
    fp = auth_dir / "sf-auth.json"
    fp.write_text(json.dumps(payload))
    return fp


def _patch_home(monkeypatch, new_home: Path):
    """Force Path.home() --> tmp dir so code reads our fake auth file."""
    monkeypatch.setattr(Path, "home", staticmethod(lambda: new_home), raising=False)


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------


def test_user_password_auth_success(monkeypatch):
    """Explicit user/pass wins even if other auth artefacts exist."""
    # Make sure token path looks absent
    _patch_token_file(monkeypatch, exists=False)

    result = get_connection_details(
        role="MYROLE",
        username="myuser",
        password="mypass",
        account="myaccount",
    )

    assert result == {
        "account": "myaccount",
        "user": "myuser",
        "password": "mypass",
        "role": "MYROLE",
    }


def test_spcs_auth_success(monkeypatch):
    """Token file + patched SPCS config produces OAUTH connection info."""
    _patch_token_file(monkeypatch, exists=True, content="TOKEN123")

    # Patch the dataclass *class* attributes (they're Fields by default)
    manager = ConfigurationService.get_instance()
    manager.update_configuration(
        SPCSConnnectionConfig,
        SPCSConnnectionConfig(
            host="spcs-host.acme.com",
            account="acme_account",
            role="DEFAULT_ROLE",
            warehouse="DEF_WH",
            database="DEF_DB",
            schema="PUBLIC",
            port=443,
        ),
    )

    cfg = get_connection_details(schema="ALT_SCHEMA")

    assert cfg["host"] == "spcs-host.acme.com"
    assert cfg["account"] == "acme_account"
    assert cfg["authenticator"] == "OAUTH"
    assert cfg["token"] == "TOKEN123"
    assert cfg["schema"] == "ALT_SCHEMA"  # param overrides default
    assert cfg["warehouse"] == "DEF_WH"
    assert cfg["client_session_keep_alive"] is True
    # Port / protocol are pinned
    assert cfg["port"] == 443
    assert cfg["protocol"] == "https"


def test_spcs_auth_missing_account_raises(monkeypatch):
    """SPCS path but account field still at default --> error."""
    _patch_token_file(monkeypatch, exists=True, content="TOKEN")

    manager = ConfigurationService.get_instance()
    manager.update_configuration(
        SPCSConnnectionConfig,
        SPCSConnnectionConfig(
            host="spcs-host.acme.com",
        ),
    )
    # Leave `account` as the original Field --> falsy check triggers

    with pytest.raises(SnowflakeAuthenticationError):
        get_connection_details()


def _local_auth_payload(
    auth_type: str = "SNOWFLAKE_JWT",
    extra_linking_fields: dict | None = None,
) -> dict:
    payload = {
        "version": "1.0.0",
        "linkingDetails": {
            "account": "myacct",
            "user": "myuser",
            "role": "MYROLE",
            "applicationUrl": "https://app",
            "privateKeyPath": "/keys/key.p8",
            "privateKeyPassphrase": "hunter2",
            "authenticator": auth_type,
            **(extra_linking_fields or {}),
        },
    }
    return payload


@pytest.mark.parametrize(
    "extra_field",
    [None, {"unusedField": "won't harm us"}],
    ids=["minimal", "tolerates_extra_fields"],
)
def test_local_jwt_auth_success(
    tmp_path,
    monkeypatch,
    extra_field,
):
    """Valid JWT file returns correct config, ignoring unknown fields."""
    _patch_token_file(monkeypatch, exists=False)  # ensure not in container

    _patch_home(monkeypatch, tmp_path)
    _write_sf_auth(tmp_path, _local_auth_payload(extra_linking_fields=extra_field))

    cfg = get_connection_details(
        warehouse="OVERRIDE_WH",
        database="OVERRIDE_DB",
        schema="OVERRIDE_SCHEMA",
    )

    assert cfg["account"] == "myacct"
    assert cfg["user"] == "myuser"
    assert cfg["role"] == "MYROLE"
    assert cfg["authenticator"] == "SNOWFLAKE_JWT"
    assert cfg["warehouse"] == "OVERRIDE_WH"
    assert cfg["private_key_file"] == "/keys/key.p8"
    assert cfg["private_key_file_pwd"] == "hunter2"
    assert cfg["client_session_keep_alive"] is True


def test_local_unsupported_authenticator_raises(tmp_path, monkeypatch):
    """File exists but authenticator != JWT --> error."""
    _patch_token_file(monkeypatch, exists=False)
    _patch_home(monkeypatch, tmp_path)
    _write_sf_auth(tmp_path, _local_auth_payload(auth_type="OAUTH"))

    with pytest.raises(SnowflakeAuthenticationError):
        get_connection_details()


@pytest.mark.parametrize(
    "authoring_fn",
    [
        # Malformed JSON
        lambda p: p.write_text("{ not json ]"),
        # Missing linking details
        lambda p: p.write_text(
            dedent("""
            { "version": "1.0.0",
              "linkingDetails": null }""")
        ),
    ],
    ids=["malformed_json", "missing_linking_details"],
)
def test_local_bad_file_raises(
    tmp_path,
    monkeypatch,
    authoring_fn: Callable[[Path], None],
):
    """Bad sf-auth.json contents bubble up as SnowflakeAuthenticationError."""
    _patch_token_file(monkeypatch, exists=False)
    _patch_home(monkeypatch, tmp_path)

    path = tmp_path / ".sema4ai"
    path.mkdir()
    authoring_fn(path / "sf-auth.json")

    with pytest.raises(SnowflakeAuthenticationError):
        get_connection_details()


def test_local_missing_file_raises(tmp_path, monkeypatch):
    """No sf-auth.json at all ⇒ SnowflakeAuthenticationError."""
    _patch_token_file(monkeypatch, exists=False)
    _patch_home(monkeypatch, tmp_path)  # but don't create the file

    with pytest.raises(SnowflakeAuthenticationError):
        get_connection_details()


def test_user_pass_beats_spcs(monkeypatch, tmp_path):
    """If explicit creds are given, we ignore the container token."""
    _patch_token_file(monkeypatch, exists=True, content="SHOULD_NOT_USE")
    cfg = get_connection_details(
        username="user",
        password="pw",
        account="acct",
    )
    assert cfg["password"] == "pw"  # came from direct input
    assert "token" not in cfg  # proves SPCS path skipped


def test_user_pass_without_account_raises(monkeypatch, tmp_path):
    """User/pass but NO account and no other auth artefacts -> error."""
    _patch_token_file(monkeypatch, exists=False)
    _patch_home(monkeypatch, tmp_path)  # but don't create the file

    with pytest.raises(SnowflakeAuthenticationError):
        get_connection_details(username="user", password="pw")


def test_spcs_auth_missing_host_raises(monkeypatch):
    """
    SPCS token present but SNOWFLAKE_HOST unset --> SnowflakeAuthenticationError.
    Account is provided so we exercise the *host* branch specifically.
    """
    _patch_token_file(monkeypatch, exists=True, content="TOK")
    monkeypatch.setattr(SPCSConnnectionConfig, "account", "some_account")
    # leave SPCSConnnectionConfig.host untouched / falsy
    with pytest.raises(SnowflakeAuthenticationError):
        get_connection_details()


def test_local_jwt_defaults_authenticator(monkeypatch, tmp_path):
    """
    sf-auth.json omits 'authenticator' key; code must default to SNOWFLAKE_JWT.
    """
    _patch_token_file(monkeypatch, exists=False)
    _patch_home(monkeypatch, tmp_path)

    payload = {
        "version": "1.0.0",
        "linkingDetails": {
            "account": "acct",
            "user": "user",
            "role": "ROLE",
            "applicationUrl": "https://app",
            "privateKeyPath": "/keys/key.p8",
            # note: no 'authenticator' here!
        },
    }
    _write_sf_auth(tmp_path, payload)

    cfg = get_connection_details()
    assert cfg["authenticator"] == "SNOWFLAKE_JWT"


@pytest.mark.parametrize("passphrase_key", [None, ""])
def test_local_jwt_no_passphrase_ok(monkeypatch, tmp_path, passphrase_key):
    """
    If privateKeyPassphrase is missing or empty, private_key_file_pwd should be absent.
    """
    _patch_token_file(monkeypatch, exists=False)
    _patch_home(monkeypatch, tmp_path)

    linking = {
        "account": "acct",
        "user": "user",
        "role": "ROLE",
        "applicationUrl": "https://app",
        "privateKeyPath": "/keys/key.p8",
    }
    if passphrase_key is not None:
        linking["privateKeyPassphrase"] = passphrase_key  # empty string

    _write_sf_auth(
        tmp_path,
        {"version": "1.0.0", "linkingDetails": linking},
    )

    cfg = get_connection_details()
    assert cfg["private_key_file"] == "/keys/key.p8"
    assert "private_key_file_pwd" not in cfg


def test_local_jwt_missing_private_key_path_raises(monkeypatch, tmp_path):
    """
    privateKeyPath is required for SNOWFLAKE_JWT; absence should raise.
    """
    _patch_token_file(monkeypatch, exists=False)
    _patch_home(monkeypatch, tmp_path)

    bad_linking_details = {
        "account": "acct",
        "user": "user",
        "role": "ROLE",
        "applicationUrl": "https://app",
        # <-- deliberately no privateKeyPath
    }
    _write_sf_auth(
        tmp_path,
        {"version": "1.0.0", "linkingDetails": bad_linking_details},
    )

    with pytest.raises(SnowflakeAuthenticationError):
        get_connection_details()
