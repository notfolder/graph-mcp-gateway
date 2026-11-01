"""応答の大きさの上限が働く（既定の上限と、上限を小さくした設定）。"""

from __future__ import annotations

import json

import pytest
from support.mcp_client import McpOAuthClient

pytestmark = pytest.mark.mock_only

LARGE_FILE = "/drives/mock-drive-onedrive/items/mock-item-large/content"


async def _endless(client: McpOAuthClient) -> tuple[list, dict]:
    arguments = {"mailFolderId": "mock-folder-endless", "fetchAllPages": True}
    if client.endpoint == "discovery":
        result = await client.call("execute-tool", {"tool_name": "list-mail-folder-messages", "parameters": arguments})
    else:
        result = await client.call("list-mail-folder-messages", arguments)
    assert not result.is_error, result.content
    body = json.loads(result.content[0].text)
    meta = dict(result.meta or {})
    return body["value"], {**meta, **(body.get("_meta") or {})}


def _has_more(meta: dict, text_body: list) -> bool:
    return bool(meta.get("result_has_more"))


async def test_default_limits_cut_endless_list(alice: McpOAuthClient) -> None:
    items, meta = await _endless(alice)
    assert len(items) <= 250
    assert len(items) == 50
    assert _has_more(meta, items), meta


async def test_default_limits_allow_small_file(alice: McpOAuthClient) -> None:
    is_error, text = await alice.execute("download-bytes", {"target": LARGE_FILE})
    assert not is_error, text[:200]


async def test_default_top_is_capped(alice: McpOAuthClient) -> None:
    is_error, _ = await alice.execute("list-mail-messages", {"top": 100})
    assert not is_error


@pytest.mark.phase5
async def test_smaller_limits_cut_list_by_items(alice: McpOAuthClient) -> None:
    items, meta = await _endless(alice)
    assert len(items) == 30
    assert _has_more(meta, items), meta


@pytest.mark.phase5
async def test_smaller_limits_reject_large_file(alice: McpOAuthClient) -> None:
    is_error, text = await alice.execute("download-bytes", {"target": LARGE_FILE})
    assert is_error
    assert "4096" in text


@pytest.mark.phase5
async def test_smaller_top_is_capped(alice: McpOAuthClient) -> None:
    is_error, _ = await alice.execute("list-mail-messages", {"top": 50})
    assert not is_error
