"""2 つの受け口が決めたとおりにツールを見せる。"""

from __future__ import annotations

import json

import pytest
from conftest import real_user, signed_in

EXCLUDED = {"get-download-url", "get-upload-url"}
DISCOVERY_TOOLS = {"search-tools", "get-tool-schema", "execute-tool"}
DOMAIN_QUERIES = {
    "profile": ("current user", "get-current-user"),
    "mail": ("mail messages", "list-mail-messages"),
    "calendar": ("calendar view", "get-calendar-view"),
    "onedrive": ("drive folder files", "list-folder-files"),
    "sharepoint": ("sharepoint site", "search-sharepoint-sites"),
    "teams": ("chat messages", "list-chat-messages"),
    "excel": ("excel range", "get-excel-range"),
}


async def test_full_endpoint_lists_all_tools_under_one_mebibyte() -> None:
    tools = await signed_in("full", real_user(1)).list_tools()
    names = {t.name for t in tools}
    assert len(tools) == 173
    assert not names & EXCLUDED
    size = len(json.dumps([t.model_dump(mode="json", by_alias=True, exclude_none=True) for t in tools]).encode())
    assert size < 1024 * 1024, size


async def test_discovery_endpoint_lists_three_tools() -> None:
    tools = await signed_in("discovery", real_user(1)).list_tools()
    assert {t.name for t in tools} == DISCOVERY_TOOLS


@pytest.mark.parametrize("domain", sorted(DOMAIN_QUERIES))
async def test_discovery_finds_tools_of_each_domain(domain: str) -> None:
    query, expected = DOMAIN_QUERIES[domain]
    full_names = {t.name for t in await signed_in("full", real_user(1)).list_tools()}
    is_error, text = await signed_in("discovery", real_user(1)).call_text("search-tools", {"query": query, "limit": 50})
    assert not is_error, text
    found = {tool["name"] for tool in json.loads(text)["tools"]}
    assert expected in found
    assert found <= full_names
    assert not found & EXCLUDED


@pytest.mark.phase5
async def test_eager_tool_is_listed_on_discovery_endpoint() -> None:
    tools = await signed_in("discovery", real_user(1)).list_tools()
    assert {t.name for t in tools} == DISCOVERY_TOOLS | {"get-current-user"}
