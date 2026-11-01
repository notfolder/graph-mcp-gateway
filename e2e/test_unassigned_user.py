"""割り当ての無い利用者はサインインできず、MCP サーバーのトークンが発行されない。"""

from __future__ import annotations

import pytest
from support.mcp_client import McpOAuthClient, SignInRejected

pytestmark = pytest.mark.mock_only


def test_unassigned_user_is_rejected(endpoint: str) -> None:
    client = McpOAuthClient(endpoint=endpoint, name=f"unassigned-{endpoint}")
    client.register()
    with pytest.raises(SignInRejected) as info:
        client.sign_in("carol")
    assert "AADSTS50105" in info.value.body
    assert client.tokens is None
