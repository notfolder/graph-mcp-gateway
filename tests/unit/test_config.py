"""設定（Settings.from_env）の単体テスト。"""

from __future__ import annotations

import pytest
from conftest import BASE_ENV, TEST_FERNET_KEY, make_env

from graph_mcp_gateway.config import Settings


def _error_text(env: dict[str, str]) -> str:
    with pytest.raises(ValueError) as info:
        Settings.from_env(env)
    return str(info.value)


def test_reads_required_values() -> None:
    settings = Settings.from_env(make_env())
    assert settings.client_id == BASE_ENV["APP_CLIENT_ID"]
    assert settings.base_url == "https://gw.test/full"
    assert settings.required_scopes == ("mcp.access",)
    assert settings.graph_scopes == ("User.Read", "Mail.ReadWrite")
    assert settings.entra_base_authority is None
    assert settings.storage_redis_url is None
    assert settings.require_consent is None
    assert settings.stateless_http is None


@pytest.mark.parametrize("name", sorted(BASE_ENV))
def test_missing_required_value_names_item_without_values(name: str) -> None:
    env = make_env()
    del env[name]
    text = _error_text(env)
    assert name in text
    for other, value in BASE_ENV.items():
        if other != name:
            assert value not in text


def test_collects_all_errors_into_one_exception() -> None:
    env = make_env(APP_CLIENT_ID="", APP_BASE_URL="http://gw.test/full", APP_REQUIRED_SCOPES=",")
    text = _error_text(env)
    assert "APP_CLIENT_ID" in text
    assert "APP_BASE_URL" in text
    assert "APP_REQUIRED_SCOPES" in text
    assert "http://gw.test" not in text


def test_secret_is_not_in_error_text() -> None:
    text = _error_text(make_env(APP_TENANT_ID="common"))
    assert BASE_ENV["APP_CLIENT_SECRET"] not in text


@pytest.mark.parametrize("tenant", ["common", "organizations", "consumers", "Common", "ORGANIZATIONS"])
def test_rejects_multi_tenant_values(tenant: str) -> None:
    assert "APP_TENANT_ID" in _error_text(make_env(APP_TENANT_ID=tenant))


def test_rejects_non_https_base_url() -> None:
    assert "APP_BASE_URL" in _error_text(make_env(APP_BASE_URL="http://gw.test/full"))


@pytest.mark.parametrize("url", ["https://ms365-full:3000/mcp", "ms365-full:3000/mcp"])
def test_rejects_non_http_upstream_url(url: str) -> None:
    assert "APP_UPSTREAM_MCP_URL" in _error_text(make_env(APP_UPSTREAM_MCP_URL=url))


def test_empty_string_is_treated_as_unset() -> None:
    settings = Settings.from_env(
        make_env(
            APP_ENTRA_BASE_AUTHORITY="",
            APP_JWT_SIGNING_KEY="",
            APP_REQUIRE_CONSENT="",
            APP_ENABLE_CIMD="",
            APP_ACCESS_TOKEN_EXPIRY_SECONDS="",
            APP_STATELESS_HTTP="",
            APP_ALLOWED_CLIENT_REDIRECT_URIS="",
        )
    )
    assert settings.entra_base_authority is None
    assert settings.jwt_signing_key is None
    assert settings.require_consent is None
    assert settings.enable_cimd is None
    assert settings.access_token_expiry_seconds is None
    assert settings.stateless_http is None
    assert settings.allowed_client_redirect_uris is None


def test_empty_required_value_is_missing() -> None:
    assert "APP_CLIENT_SECRET" in _error_text(make_env(APP_CLIENT_SECRET=""))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("true", True), ("false", False), ("remember", "remember"), ("external", "external"), ("TRUE", True)],
)
def test_reads_consent_choice(raw: str, expected: object) -> None:
    assert Settings.from_env(make_env(APP_REQUIRE_CONSENT=raw)).require_consent == expected


def test_rejects_unknown_consent_choice() -> None:
    assert "APP_REQUIRE_CONSENT" in _error_text(make_env(APP_REQUIRE_CONSENT="always"))


@pytest.mark.parametrize("name", ["APP_ENABLE_CIMD", "APP_STATELESS_HTTP"])
def test_reads_booleans(name: str) -> None:
    attr = {"APP_ENABLE_CIMD": "enable_cimd", "APP_STATELESS_HTTP": "stateless_http"}[name]
    assert getattr(Settings.from_env(make_env(**{name: "true"})), attr) is True
    assert getattr(Settings.from_env(make_env(**{name: "false"})), attr) is False
    assert name in _error_text(make_env(**{name: "yes"}))


def test_reads_positive_integer_expiry() -> None:
    assert Settings.from_env(make_env(APP_ACCESS_TOKEN_EXPIRY_SECONDS="600")).access_token_expiry_seconds == 600
    assert "APP_ACCESS_TOKEN_EXPIRY_SECONDS" in _error_text(make_env(APP_ACCESS_TOKEN_EXPIRY_SECONDS="0"))
    assert "APP_ACCESS_TOKEN_EXPIRY_SECONDS" in _error_text(make_env(APP_ACCESS_TOKEN_EXPIRY_SECONDS="ten"))


def test_reads_entra_base_authority_host_and_port() -> None:
    assert Settings.from_env(make_env(APP_ENTRA_BASE_AUTHORITY="mock-entra:8443")).entra_base_authority == (
        "mock-entra:8443"
    )
    assert "APP_ENTRA_BASE_AUTHORITY" in _error_text(make_env(APP_ENTRA_BASE_AUTHORITY="https://mock-entra:8443/"))


def test_reads_redirect_uri_list_without_empty_items() -> None:
    settings = Settings.from_env(make_env(APP_ALLOWED_CLIENT_REDIRECT_URIS="http://127.0.0.1:*, ,https://a.test/*,"))
    assert settings.allowed_client_redirect_uris == ("http://127.0.0.1:*", "https://a.test/*")


def test_reads_required_scopes_comma_separated_without_empty_items() -> None:
    assert Settings.from_env(make_env(APP_REQUIRED_SCOPES="a, ,b,")).required_scopes == ("a", "b")


def test_reads_graph_scopes_whitespace_separated() -> None:
    settings = Settings.from_env(make_env(APP_GRAPH_SCOPES="  User.Read\tMail.Send   Chat.ReadWrite "))
    assert settings.graph_scopes == ("User.Read", "Mail.Send", "Chat.ReadWrite")
    assert "APP_GRAPH_SCOPES" in _error_text(make_env(APP_GRAPH_SCOPES="   "))


def test_redis_storage_requires_key_and_prefix() -> None:
    settings = Settings.from_env(
        make_env(
            APP_STORAGE_REDIS_URL="redis://redis:6379/0",
            APP_STORAGE_ENCRYPTION_KEY=TEST_FERNET_KEY,
            APP_STORAGE_PREFIX="full",
        )
    )
    assert settings.storage_redis_url == "redis://redis:6379/0"
    assert settings.storage_prefix == "full"

    text = _error_text(make_env(APP_STORAGE_REDIS_URL="redis://redis:6379/0"))
    assert "APP_STORAGE_ENCRYPTION_KEY" in text
    assert "APP_STORAGE_PREFIX" in text


def test_redis_url_scheme_is_checked() -> None:
    env = make_env(
        APP_STORAGE_REDIS_URL="http://redis:6379/0", APP_STORAGE_ENCRYPTION_KEY=TEST_FERNET_KEY, APP_STORAGE_PREFIX="a"
    )
    assert "APP_STORAGE_REDIS_URL" in _error_text(env)
    env["APP_STORAGE_REDIS_URL"] = "rediss://redis:6380/0"
    assert Settings.from_env(env).storage_redis_url == "rediss://redis:6380/0"


def test_encryption_key_must_be_fernet_key() -> None:
    env = make_env(
        APP_STORAGE_REDIS_URL="redis://redis:6379/0", APP_STORAGE_ENCRYPTION_KEY="not-a-key", APP_STORAGE_PREFIX="full"
    )
    text = _error_text(env)
    assert "APP_STORAGE_ENCRYPTION_KEY" in text
    assert "not-a-key" not in text


def test_encryption_key_without_redis_is_error() -> None:
    assert "APP_STORAGE_ENCRYPTION_KEY" in _error_text(make_env(APP_STORAGE_ENCRYPTION_KEY=TEST_FERNET_KEY))


@pytest.mark.parametrize("prefix", ["Full", "full1", "fu-ll"])
def test_prefix_must_be_lowercase_letters(prefix: str) -> None:
    env = make_env(
        APP_STORAGE_REDIS_URL="redis://redis:6379/0", APP_STORAGE_ENCRYPTION_KEY=TEST_FERNET_KEY, APP_STORAGE_PREFIX=prefix
    )
    assert "APP_STORAGE_PREFIX" in _error_text(env)


def test_prefix_without_redis_is_allowed() -> None:
    assert Settings.from_env(make_env(APP_STORAGE_PREFIX="discovery")).storage_prefix == "discovery"


def test_reads_os_environment_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in make_env().items():
        monkeypatch.setenv(name, value)
    assert Settings.from_env().client_id == BASE_ENV["APP_CLIENT_ID"]


def test_settings_are_immutable() -> None:
    settings = Settings.from_env(make_env())
    with pytest.raises(AttributeError):
        settings.client_id = "other"  # type: ignore[misc]
