"""台数を増やした構成（e2e/compose.multi.yaml）で、登録・サインイン・呼び出し・更新が通る。

各コンテナに要求が届いたことは、e2e/host/test_scale_out_spread.py がホストから確かめる。
"""

from __future__ import annotations

import pytest
from conftest import ENDPOINTS
from support.mcp_client import McpOAuthClient

CALLS = 20


@pytest.mark.multi
@pytest.mark.parametrize("endpoint", ENDPOINTS)
async def test_register_sign_in_call_and_refresh(endpoint: str) -> None:
    client = McpOAuthClient(endpoint=endpoint, name=f"multi-{endpoint}")
    client.register()
    client.sign_in("alice")
    for _ in range(CALLS):
        is_error, text = await client.execute("get-current-user")
        assert not is_error, text
    client.refresh()
    is_error, text = await client.execute("get-current-user")
    assert not is_error, text
