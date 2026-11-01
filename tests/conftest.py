"""テスト共通の値と部品。値はすべて試験用の固定値で、秘密ではない。"""

from __future__ import annotations

from typing import Any

import pytest

BASE_ENV: dict[str, str] = {
    "APP_CLIENT_ID": "11111111-1111-1111-1111-111111111111",
    "APP_CLIENT_SECRET": "test-secret-value",
    "APP_TENANT_ID": "00000000-0000-0000-0000-000000000001",
    "APP_BASE_URL": "https://gw.test/full",
    "APP_UPSTREAM_MCP_URL": "http://ms365-full:3000/mcp",
    "APP_REQUIRED_SCOPES": "mcp.access",
    "APP_GRAPH_SCOPES": "User.Read Mail.ReadWrite",
}

TEST_FERNET_KEY = "x3gVhQ7H8m1kRk6rIhB1lQnq0b7r3ZcO2m1n2p3q4r8="


@pytest.fixture
def base_env() -> dict[str, str]:
    """必須の値だけを入れた環境変数の対応表。"""
    return dict(BASE_ENV)


def make_env(**overrides: Any) -> dict[str, str]:
    """必須の値に上書きを足した環境変数の対応表を返す。"""
    env = dict(BASE_ENV)
    env.update({k: str(v) for k, v in overrides.items()})
    return env
