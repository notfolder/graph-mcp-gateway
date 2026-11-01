"""無効なトークンが拒否される（期限切れは test_token_refresh.py で確かめる）。"""

from __future__ import annotations

import httpx2
import pytest
from conftest import real_user, signed_in
from support.mcp_client import ca_bundle

INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "e2e", "version": "1"}},
}


def _post(url: str, token: str | None) -> httpx2.Response:
    headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with httpx2.Client(verify=ca_bundle(), timeout=30) as http:
        return http.post(url, json=INITIALIZE, headers=headers)


def _tampered(token: str) -> str:
    head, payload, signature = token.split(".")
    flipped = ("A" if signature[0] != "A" else "B") + signature[1:]
    return f"{head}.{payload}.{flipped}"


def test_no_token_is_rejected(endpoint: str) -> None:
    client = signed_in(endpoint, real_user(1))
    response = _post(client.mcp_url, None)
    assert response.status_code == 401
    assert "resource_metadata" in response.headers.get("www-authenticate", "")


def test_bad_signature_is_rejected(endpoint: str) -> None:
    client = signed_in(endpoint, real_user(1))
    assert client.tokens is not None
    assert _post(client.mcp_url, _tampered(client.tokens.access_token)).status_code == 401


def test_other_endpoints_token_is_rejected(endpoint: str) -> None:
    other = "discovery" if endpoint == "full" else "full"
    client = signed_in(endpoint, real_user(1))
    other_client = signed_in(other, real_user(1))
    other_client.ensure_fresh()
    assert other_client.tokens is not None
    assert _post(client.mcp_url, other_client.tokens.access_token).status_code == 401


@pytest.mark.parametrize("token", ["not-a-jwt", "a.b.c"])
def test_garbage_token_is_rejected(endpoint: str, token: str) -> None:
    client = signed_in(endpoint, real_user(1))
    assert _post(client.mcp_url, token).status_code == 401
