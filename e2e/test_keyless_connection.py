"""鍵なしで登録・サインインし、ツールを使える（両方の受け口、DCR と CIMD）。"""

from __future__ import annotations

import json

import pytest
from conftest import real_user
from support.mcp_client import McpOAuthClient, work_dir


@pytest.mark.parametrize("registration", ["dcr", pytest.param("cimd", marks=pytest.mark.mock_only)])
async def test_register_sign_in_and_get_profile(endpoint: str, registration: str) -> None:
    client = McpOAuthClient(endpoint=endpoint, name=f"keyless-{endpoint}-{registration}", registration=registration)
    client.register()
    client.sign_in(real_user(1))
    assert client.mcp_url.startswith("https://")

    if endpoint == "discovery":
        is_error, found = await client.call_text("search-tools", {"query": "current user profile"})
        assert not is_error
        assert "get-current-user" in found
        is_error, schema = await client.call_text("get-tool-schema", {"tool_name": "get-current-user"})
        assert not is_error
        assert "get-current-user" in schema
    is_error, profile = await client.execute("get-current-user")
    assert not is_error, profile
    if registration == "dcr" or True:
        assert "displayName" in json.loads(profile)

    result_path = work_dir() / "records" / "keyless-results.jsonl"
    with result_path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps({"endpoint": endpoint, "registration": registration, "client_id": client.client_id, "ok": True}) + "\n")
