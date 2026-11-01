"""認証と保管先の組み立て（build_auth_provider・build_client_storage）の単体テスト。"""

from __future__ import annotations

from typing import Any

import pytest
from conftest import TEST_FERNET_KEY, make_env
from key_value.aio.wrappers.encryption import FernetEncryptionWrapper
from key_value.aio.wrappers.prefix_collections import PrefixCollectionsWrapper

from graph_mcp_gateway import auth as auth_module
from graph_mcp_gateway.auth import build_auth_provider, build_client_storage
from graph_mcp_gateway.config import Settings

OPTIONAL_KEYS = {
    "base_authority",
    "jwt_signing_key",
    "client_storage",
    "require_authorization_consent",
    "allowed_client_redirect_uris",
    "enable_cimd",
    "fastmcp_access_token_expiry_seconds",
}


@pytest.fixture
def captured(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """AzureProvider に渡した引数を記録する。"""
    record: dict[str, Any] = {}

    def fake_provider(**kwargs: Any) -> dict[str, Any]:
        record.update(kwargs)
        return kwargs

    monkeypatch.setattr(auth_module, "AzureProvider", fake_provider)
    return record


def _redis_env(**extra: str) -> dict[str, str]:
    return make_env(
        APP_STORAGE_REDIS_URL="redis://redis:6379/0",
        APP_STORAGE_ENCRYPTION_KEY=TEST_FERNET_KEY,
        APP_STORAGE_PREFIX="full",
        **extra,
    )


def test_unset_optional_values_are_not_passed(captured: dict[str, Any]) -> None:
    build_auth_provider(Settings.from_env(make_env()))
    assert OPTIONAL_KEYS.isdisjoint(captured)
    assert "redirect_path" not in captured
    assert captured["client_id"] == "11111111-1111-1111-1111-111111111111"
    assert captured["client_secret"] == "test-secret-value"
    assert captured["tenant_id"] == "00000000-0000-0000-0000-000000000001"
    assert captured["base_url"] == "https://gw.test/full"
    assert captured["required_scopes"] == ["mcp.access"]


def test_additional_scopes_match_graph_scopes(captured: dict[str, Any]) -> None:
    settings = Settings.from_env(make_env(APP_GRAPH_SCOPES="User.Read Mail.Send Chat.ReadWrite"))
    build_auth_provider(settings)
    assert captured["additional_authorize_scopes"] == list(settings.graph_scopes)


def test_set_optional_values_are_passed(captured: dict[str, Any]) -> None:
    env = _redis_env(
        APP_ENTRA_BASE_AUTHORITY="mock-entra:8443",
        APP_JWT_SIGNING_KEY="signing-key-for-tests",
        APP_REQUIRE_CONSENT="remember",
        APP_ALLOWED_CLIENT_REDIRECT_URIS="http://127.0.0.1:*,https://owui.test/*",
        APP_ENABLE_CIMD="false",
        APP_ACCESS_TOKEN_EXPIRY_SECONDS="900",
    )
    build_auth_provider(Settings.from_env(env))
    assert captured["base_authority"] == "mock-entra:8443"
    assert captured["jwt_signing_key"] == "signing-key-for-tests"
    assert captured["require_authorization_consent"] == "remember"
    assert captured["allowed_client_redirect_uris"] == ["http://127.0.0.1:*", "https://owui.test/*"]
    assert captured["enable_cimd"] is False
    assert captured["fastmcp_access_token_expiry_seconds"] == 900
    assert isinstance(captured["client_storage"], FernetEncryptionWrapper)


def test_real_provider_uses_graph_scopes_and_callback_under_base_url() -> None:
    provider = build_auth_provider(Settings.from_env(make_env(APP_ENTRA_BASE_AUTHORITY="mock-entra:8443")))
    assert provider.additional_authorize_scopes == ["User.Read", "Mail.ReadWrite", "offline_access"]
    assert str(provider.base_url).rstrip("/") == "https://gw.test/full"
    assert provider._redirect_path == "/auth/callback"


def test_storage_is_none_without_redis() -> None:
    assert build_client_storage(Settings.from_env(make_env())) is None


def test_storage_is_wrapped_with_prefix_and_encryption() -> None:
    storage = build_client_storage(Settings.from_env(_redis_env()))
    assert isinstance(storage, FernetEncryptionWrapper)
    inner = storage.key_value
    assert isinstance(inner, PrefixCollectionsWrapper)
    assert inner.prefix == "full"
