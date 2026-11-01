"""OAuth プロキシ（AzureProvider）と、認証の状態の保管先を組み立てる。"""

from __future__ import annotations

from typing import Any

from cryptography.fernet import Fernet
from fastmcp.server.auth.providers.azure import AzureProvider
from key_value.aio.protocols import AsyncKeyValue
from key_value.aio.stores.redis import RedisStore
from key_value.aio.wrappers.encryption import FernetEncryptionWrapper
from key_value.aio.wrappers.prefix_collections import PrefixCollectionsWrapper

from .config import Settings


def build_client_storage(settings: Settings) -> AsyncKeyValue | None:
    """共有の保管先（Redis）を組み立てる。

    Redis の URL が設定されていれば、受け口ごとの前置きで名前空間を分け、Fernet で暗号化して包んだ
    Redis の保管先を返す。設定されていなければ None を返し、FastMCP の既定の保管先（暗号化したファイル）を使わせる。

    Args:
        settings: 中継の設定。

    Returns:
        包んだ保管先、または None。
    """
    if settings.storage_redis_url is None:
        return None
    assert settings.storage_encryption_key is not None
    assert settings.storage_prefix is not None
    store = RedisStore(url=settings.storage_redis_url)
    prefixed = PrefixCollectionsWrapper(store, prefix=settings.storage_prefix)
    return FernetEncryptionWrapper(prefixed, fernet=Fernet(settings.storage_encryption_key.encode()))


def build_auth_provider(settings: Settings) -> AzureProvider:
    """OAuth プロキシ（FastMCP の AzureProvider）を組み立てる。

    常に渡すのは、クライアント ID、シークレット、テナント ID、公開 URL、API のスコープ名、
    サインイン時に要求する追加のスコープ（Graph の権限の一覧）。
    Entra ID の接続先、署名鍵、保管先、接続の確認画面の出し方、AI ツールの戻り先の制限、CIMD の受け付け、
    トークンの有効期限は、設定されたときだけ渡す。戻り先のパスは渡さない（既定の `/auth/callback`）。

    Args:
        settings: 中継の設定。

    Returns:
        組み立てた AzureProvider。
    """
    kwargs: dict[str, Any] = {
        "client_id": settings.client_id,
        "client_secret": settings.client_secret,
        "tenant_id": settings.tenant_id,
        "base_url": settings.base_url,
        "required_scopes": list(settings.required_scopes),
        "additional_authorize_scopes": list(settings.graph_scopes),
    }
    if settings.entra_base_authority is not None:
        kwargs["base_authority"] = settings.entra_base_authority
    if settings.jwt_signing_key is not None:
        kwargs["jwt_signing_key"] = settings.jwt_signing_key
    storage = build_client_storage(settings)
    if storage is not None:
        kwargs["client_storage"] = storage
    if settings.require_consent is not None:
        kwargs["require_authorization_consent"] = settings.require_consent
    if settings.allowed_client_redirect_uris is not None:
        kwargs["allowed_client_redirect_uris"] = list(settings.allowed_client_redirect_uris)
    if settings.enable_cimd is not None:
        kwargs["enable_cimd"] = settings.enable_cimd
    if settings.access_token_expiry_seconds is not None:
        kwargs["fastmcp_access_token_expiry_seconds"] = settings.access_token_expiry_seconds
    return AzureProvider(**kwargs)
