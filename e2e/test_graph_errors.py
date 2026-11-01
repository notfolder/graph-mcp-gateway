"""Graph のエラーが伝わり、一時的なエラーで再試行する（再試行の回数は手順 9 で Dev Proxy の記録から確かめる）。"""

from __future__ import annotations

import re
import time

import pytest
from conftest import signed_in
from support.mcp_client import McpOAuthClient

pytestmark = pytest.mark.mock_only

JWT = re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.")


@pytest.mark.parametrize(("message_id", "status"), [("mock-401", 401), ("mock-403", 403), ("mock-404", 404)])
async def test_graph_error_is_returned_with_status_and_body(alice: McpOAuthClient, message_id: str, status: int) -> None:
    is_error, text = await alice.execute("get-mail-message", {"messageId": message_id})
    assert is_error
    assert f"Microsoft Graph API error: {status}" in text
    assert '"code"' in text or "code" in text
    assert not JWT.search(text)


async def test_429_once_is_retried_and_succeeds() -> None:
    client = signed_in("full", "alice")
    started = time.monotonic()
    is_error, text = await client.execute("get-mail-message", {"messageId": "mock-429-then-ok"})
    assert not is_error, text
    assert time.monotonic() - started >= 0.9


async def test_429_always_fails_after_retries(alice: McpOAuthClient) -> None:
    started = time.monotonic()
    is_error, text = await alice.execute("get-mail-message", {"messageId": "mock-429-always"})
    assert is_error
    assert "429" in text
    assert time.monotonic() - started >= 2.5


async def test_503_read_fails_after_retries(alice: McpOAuthClient) -> None:
    is_error, text = await alice.execute("get-mail-message", {"messageId": "mock-503"})
    assert is_error
    assert "503" in text


async def test_503_send_is_not_retried_and_other_user_is_not_blocked(alice: McpOAuthClient) -> None:
    started = time.monotonic()
    is_error, text = await alice.execute(
        "send-mail",
        {
            "body": {
                "message": {
                    "subject": "mock-503",
                    "body": {"contentType": "Text", "content": "retry check"},
                    "toRecipients": [{"emailAddress": {"address": "bob@contoso.test"}}],
                }
            }
        },
    )
    assert is_error
    assert "503" in text
    assert time.monotonic() - started < 2.0

    bob = signed_in(alice.endpoint, "bob")
    is_error, profile = await bob.execute("get-current-user")
    assert not is_error, profile


async def test_obo_failure_is_masked(endpoint: str) -> None:
    signed_in(endpoint, "alice")
    dave = signed_in(endpoint, "dave")
    if endpoint == "full":
        await signed_in("full", "alice").list_tools()
        result = await dave.call("get-current-user")
    else:
        result = await dave.call("search-tools", {"query": "user"})
    text = result.content[0].text if result.content else ""
    assert result.is_error
    assert "AADSTS" not in text
    assert not JWT.search(text)
