"""再起動してもサインインが保たれる（e2e/run.sh が、2 つの段の間で中継のコンテナを作り直す）。

mock モードのトークンの期限は 60 秒なので、作り直しの間に期限が切れていたら、保存したリフレッシュトークンで
更新してから呼ぶ（ブラウザでのサインインはしない。更新が通ること自体が、保管先が作り直しの後も残っている証拠になる）。
"""

from __future__ import annotations

import time

import pytest
from conftest import ENDPOINTS
from support.mcp_client import McpOAuthClient


@pytest.mark.restart_prepare
@pytest.mark.parametrize("endpoint", ENDPOINTS)
async def test_prepare_sign_in_before_restart(endpoint: str) -> None:
    client = McpOAuthClient(endpoint=endpoint, name=f"restart-{endpoint}")
    client.sign_in("alice")
    is_error, _ = await client.execute("get-current-user")
    assert not is_error
    client.save_state(f"restart-{endpoint}")


@pytest.mark.restart_verify
@pytest.mark.parametrize("endpoint", ENDPOINTS)
async def test_verify_same_token_works_after_restart(endpoint: str) -> None:
    client = McpOAuthClient.load_state(f"restart-{endpoint}", name=f"restart-{endpoint}-after")
    assert client.tokens is not None
    if client.tokens.expires_in and time.time() > client.tokens.obtained_at + client.tokens.expires_in - 5:
        client.refresh()
    token = client.tokens.access_token
    async with client.client(token=token) as mcp:
        if endpoint == "discovery":
            result = await mcp.call_tool("execute-tool", {"tool_name": "get-current-user", "parameters": {}}, raise_on_error=False)
        else:
            result = await mcp.call_tool("get-current-user", {}, raise_on_error=False)
    assert not result.is_error, result.content
    assert "Alice Mock" in result.content[0].text
