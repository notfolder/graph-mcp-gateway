"""E2E の共通の部品。

mock モードはコンテナ `e2e` の中で、real モードは手元で実行する（`E2E_MODE`）。
シナリオの分け方（マーカー）は `e2e/run.sh` の手順に合わせる。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from support.mcp_client import McpOAuthClient  # noqa: E402

ENDPOINTS = ["full", "discovery"]

MARKERS = {
    "phase5": "上限と直接出すツールの設定を重ねて作り直した後に実行する",
    "restart_prepare": "中継の作り直しの前にサインインして状態を保存する",
    "restart_verify": "中継の作り直しの後に、保存したトークンで呼ぶ",
    "multi": "台数を増やした構成で実行する",
    "final": "全部の手順の後に、保存したログと記録を調べる",
    "mock_only": "mock モードの模擬の ID や設定に頼るので、real モードでは飛ばす",
}


def pytest_configure(config: pytest.Config) -> None:
    for name, text in MARKERS.items():
        config.addinivalue_line("markers", f"{name}: {text}")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if mode() == "real":
        skip = pytest.mark.skip(reason="mock モードの模擬に頼るシナリオ（real モードでは real-checklist.md で確かめる）")
        for item in items:
            if "mock_only" in item.keywords:
                item.add_marker(skip)


def mode() -> str:
    """`mock` か `real`。"""
    return os.environ.get("E2E_MODE", "mock")


def real_user(index: int) -> str:
    """real モードの利用者（login_hint）。mock モードでは alice / bob。"""
    if mode() == "real":
        return os.environ.get(f"E2E_REAL_USER_{index}", "")
    return ["alice", "bob"][index - 1]


_cache: dict[tuple[str, str, str], McpOAuthClient] = {}


def signed_in(endpoint: str, user: str = "alice", registration: str = "dcr") -> McpOAuthClient:
    """サインイン済みのテスト用クライアントを返す（同じ組み合わせは使い回す）。"""
    key = (endpoint, user, registration)
    if key not in _cache:
        client = McpOAuthClient(endpoint=endpoint, name=f"{endpoint}-{user}-{registration}", registration=registration)
        client.sign_in(user)
        _cache[key] = client
    return _cache[key]


@pytest.fixture(params=ENDPOINTS)
def endpoint(request: pytest.FixtureRequest) -> str:
    """2 つの受け口のそれぞれでシナリオを実行する。"""
    return request.param


@pytest.fixture
def alice(endpoint: str) -> McpOAuthClient:
    """その受け口にサインインした利用者 A（mock は alice）。"""
    return signed_in(endpoint, real_user(1))
