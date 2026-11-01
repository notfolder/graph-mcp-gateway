"""中継の設定を環境変数から読む。"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from cryptography.fernet import Fernet

ConsentMode = bool | Literal["remember", "external"]

_MULTI_TENANT_VALUES = {"common", "organizations", "consumers"}
_CONSENT_VALUES: dict[str, ConsentMode] = {
    "true": True,
    "false": False,
    "remember": "remember",
    "external": "external",
}
_BOOL_VALUES = {"true": True, "false": False}
_HOST_PORT = re.compile(r"^[A-Za-z0-9.-]+(:[0-9]{1,5})?$")
_PREFIX = re.compile(r"^[a-z]+$")


@dataclass(frozen=True)
class Settings:
    """中継の設定値（変更不可）。未設定の任意の値は None。

    Attributes:
        client_id: アプリ（クライアント）ID。
        client_secret: クライアントシークレット。
        tenant_id: テナント ID。
        base_url: その受け口の公開 URL（https）。
        upstream_mcp_url: 中継先の ms-365-mcp-server の URL（http）。
        required_scopes: API の公開で作るスコープ名。
        graph_scopes: Graph の権限の一覧。
        entra_base_authority: Entra ID の接続先のホスト。
        jwt_signing_key: MCP サーバーのトークンの署名鍵。
        storage_redis_url: 共有の保管先の Redis の URL。
        storage_encryption_key: Redis に書く中身の暗号化キー（Fernet）。
        storage_prefix: Redis の名前空間の前置き。
        require_consent: 接続の確認画面の出し方。
        allowed_client_redirect_uris: AI ツールの戻り先の制限。
        enable_cimd: CIMD の受け付け。
        access_token_expiry_seconds: MCP サーバーのアクセストークンの有効期限（秒）。
        stateless_http: MCP のセッションを持たない動作。
    """

    client_id: str
    client_secret: str
    tenant_id: str
    base_url: str
    upstream_mcp_url: str
    required_scopes: tuple[str, ...]
    graph_scopes: tuple[str, ...]
    entra_base_authority: str | None = None
    jwt_signing_key: str | None = None
    storage_redis_url: str | None = None
    storage_encryption_key: str | None = None
    storage_prefix: str | None = None
    require_consent: ConsentMode | None = None
    allowed_client_redirect_uris: tuple[str, ...] | None = None
    enable_cimd: bool | None = None
    access_token_expiry_seconds: int | None = None
    stateless_http: bool | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        """環境変数の対応表から設定を読む。

        空文字は未設定として扱う。誤りはすべて集めてから 1 つの例外にする。

        Args:
            env: 環境変数の対応表。None なら OS の環境変数。

        Returns:
            読み取った設定。

        Raises:
            ValueError: 誤りが 1 つでもあった場合。文言には項目名だけを含め、値は含めない。
        """
        source = os.environ if env is None else env
        errors: list[str] = []

        def get(name: str) -> str | None:
            value = source.get(name, "")
            value = value.strip() if value else ""
            return value or None

        def required(name: str) -> str:
            value = get(name)
            if value is None:
                errors.append(name)
                return ""
            return value

        def split_list(name: str, separator: str | None) -> tuple[str, ...] | None:
            value = get(name)
            if value is None:
                return None
            items = value.split(separator) if separator else value.split()
            return tuple(item.strip() for item in items if item.strip())

        def required_list(name: str, separator: str | None) -> tuple[str, ...]:
            items = split_list(name, separator)
            if not items:
                errors.append(name)
                return ()
            return items

        def choice(name: str, values: Mapping[str, Any]) -> Any:
            value = get(name)
            if value is None:
                return None
            key = value.lower()
            if key not in values:
                errors.append(name)
                return None
            return values[key]

        client_id = required("APP_CLIENT_ID")
        client_secret = required("APP_CLIENT_SECRET")

        tenant_id = required("APP_TENANT_ID")
        if tenant_id and tenant_id.lower() in _MULTI_TENANT_VALUES:
            errors.append("APP_TENANT_ID")

        base_url = required("APP_BASE_URL")
        if base_url and not base_url.startswith("https://"):
            errors.append("APP_BASE_URL")

        upstream_mcp_url = required("APP_UPSTREAM_MCP_URL")
        if upstream_mcp_url and not upstream_mcp_url.startswith("http://"):
            errors.append("APP_UPSTREAM_MCP_URL")

        required_scopes = required_list("APP_REQUIRED_SCOPES", ",")
        graph_scopes = required_list("APP_GRAPH_SCOPES", None)

        entra_base_authority = get("APP_ENTRA_BASE_AUTHORITY")
        if entra_base_authority is not None and not _HOST_PORT.match(entra_base_authority):
            errors.append("APP_ENTRA_BASE_AUTHORITY")

        jwt_signing_key = get("APP_JWT_SIGNING_KEY")

        storage_redis_url = get("APP_STORAGE_REDIS_URL")
        if storage_redis_url is not None and not storage_redis_url.startswith(("redis://", "rediss://")):
            errors.append("APP_STORAGE_REDIS_URL")

        storage_encryption_key = get("APP_STORAGE_ENCRYPTION_KEY")
        storage_prefix = get("APP_STORAGE_PREFIX")
        if storage_redis_url is not None:
            if storage_encryption_key is None or not _is_fernet_key(storage_encryption_key):
                errors.append("APP_STORAGE_ENCRYPTION_KEY")
            if storage_prefix is None or not _PREFIX.match(storage_prefix):
                errors.append("APP_STORAGE_PREFIX")
        else:
            if storage_encryption_key is not None:
                errors.append("APP_STORAGE_ENCRYPTION_KEY")
            if storage_prefix is not None and not _PREFIX.match(storage_prefix):
                errors.append("APP_STORAGE_PREFIX")

        require_consent = choice("APP_REQUIRE_CONSENT", _CONSENT_VALUES)
        allowed_client_redirect_uris = split_list("APP_ALLOWED_CLIENT_REDIRECT_URIS", ",")
        enable_cimd = choice("APP_ENABLE_CIMD", _BOOL_VALUES)

        access_token_expiry_seconds: int | None = None
        expiry = get("APP_ACCESS_TOKEN_EXPIRY_SECONDS")
        if expiry is not None:
            try:
                access_token_expiry_seconds = int(expiry)
            except ValueError:
                errors.append("APP_ACCESS_TOKEN_EXPIRY_SECONDS")
            else:
                if access_token_expiry_seconds < 1:
                    errors.append("APP_ACCESS_TOKEN_EXPIRY_SECONDS")
                    access_token_expiry_seconds = None

        stateless_http = choice("APP_STATELESS_HTTP", _BOOL_VALUES)

        if errors:
            raise ValueError("設定に誤りがあります: " + ", ".join(dict.fromkeys(errors)))

        return cls(
            client_id=client_id,
            client_secret=client_secret,
            tenant_id=tenant_id,
            base_url=base_url.rstrip("/"),
            upstream_mcp_url=upstream_mcp_url,
            required_scopes=required_scopes,
            graph_scopes=graph_scopes,
            entra_base_authority=entra_base_authority,
            jwt_signing_key=jwt_signing_key,
            storage_redis_url=storage_redis_url,
            storage_encryption_key=storage_encryption_key,
            storage_prefix=storage_prefix,
            require_consent=require_consent,
            allowed_client_redirect_uris=allowed_client_redirect_uris,
            enable_cimd=enable_cimd,
            access_token_expiry_seconds=access_token_expiry_seconds,
            stateless_http=stateless_http,
        )


def _is_fernet_key(value: str) -> bool:
    """Fernet の鍵として読めるかを返す。"""
    try:
        Fernet(value.encode())
    except ValueError:
        return False
    return True
