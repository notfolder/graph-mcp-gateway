"""期限切れのトークンは拒否され、リフレッシュトークンで更新すれば使い続けられる。

mock モードは Entra ID の模擬のアクセストークンの期限を 60 秒にしてある（MCP サーバーのトークンも同じ期限になる）。
"""

from __future__ import annotations

import time

import httpx2
import pytest
from conftest import mode, real_user
from support.mcp_client import McpOAuthClient, ca_bundle

from test_invalid_token import INITIALIZE


def _status(client: McpOAuthClient, token: str) -> int:
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    with httpx2.Client(verify=ca_bundle(), timeout=30) as http:
        return http.post(client.mcp_url, json=INITIALIZE, headers=headers).status_code


@pytest.mark.mock_only
async def test_expired_token_is_rejected_and_refresh_keeps_working() -> None:
    clients = {}
    for endpoint in ("full", "discovery"):
        client = McpOAuthClient(endpoint=endpoint, name=f"refresh-{endpoint}")
        client.sign_in(real_user(1))
        clients[endpoint] = client
    first = clients["full"].tokens
    assert first is not None and first.expires_in and first.expires_in <= 120
    time.sleep(max(0.0, first.obtained_at + first.expires_in + 5 - time.time()))

    for client in clients.values():
        assert client.tokens is not None
        old = client.tokens.access_token
        assert _status(client, old) == 401
        client.refresh()
        assert client.tokens.access_token != old
        is_error, profile = await client.execute("get-current-user")
        assert not is_error, profile


@pytest.mark.skipif(mode() != "real", reason="real モードだけ")
def test_real_refresh_token_is_issued() -> None:
    client = McpOAuthClient(endpoint="full", name="refresh-real")
    client.sign_in(real_user(1))
    assert client.tokens is not None and client.tokens.refresh_token
    client.refresh()
