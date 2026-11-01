"""中継の結合テスト。

中継のサーバーをプロセスの中で組み立て（認証は試験用の検証器）、中継先をプロセスの中の試験用の MCP サーバー
（受けたヘッダーを記録し、決まったツールを返す）にして、HTTP の形のまま呼ぶ。外部への接続はしない。
"""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx2
import pytest
from conftest import make_env
from fastmcp import Client, FastMCP
from fastmcp.client.transports import ClientTransport, StreamableHttpTransport
from fastmcp.server.auth.providers.azure import AzureProvider
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier
from fastmcp.server.dependencies import get_http_headers

from graph_mcp_gateway.config import Settings
from graph_mcp_gateway.server import create_server

USER_TOKEN = "entra-user-token"
GRAPH_TOKEN = "graph-token-from-obo"


def _asgi_client_factory(app: Any, base_url: str) -> Callable[..., httpx2.AsyncClient]:
    def factory(headers: dict[str, str] | None = None, timeout: Any = None, auth: Any = None, **_: Any) -> Any:
        return httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app), base_url=base_url, headers=headers, timeout=timeout, auth=auth
        )

    return factory


@dataclass
class Upstream:
    """試験用の中継先（ms-365-mcp-server の代わり）。"""

    headers: list[dict[str, str]] = field(default_factory=list)
    up: bool = True

    def build(self) -> Any:
        server = FastMCP("upstream")

        @server.tool
        def get_current_user() -> str:
            """利用者のプロフィールを返す。"""
            self.headers.append(get_http_headers(include_all=True))
            return json.dumps({"displayName": "Alice Mock"})

        @server.tool
        def failing_graph_call() -> dict[str, Any]:
            """Graph のエラーを返す。"""
            raise RuntimeError("Microsoft Graph API error: 404 Not Found")

        return server.http_app(path="/mcp", json_response=True, stateless_http=True)


@dataclass
class OboRecorder:
    """OBO の呼び出しを記録する（AzureProvider.get_obo_credential の差し替え）。"""

    assertions: list[str] = field(default_factory=list)
    fail: bool = False


@pytest.fixture
def obo(monkeypatch: pytest.MonkeyPatch) -> OboRecorder:
    recorder = OboRecorder()

    class Credential:
        async def get_token(self, *scopes: str) -> Any:
            if recorder.fail:
                raise RuntimeError("AADSTS65001: consent_required")

            class Token:
                token = GRAPH_TOKEN

            return Token()

    async def fake_get_obo_credential(self: AzureProvider, user_assertion: str) -> Credential:
        recorder.assertions.append(user_assertion)
        return Credential()

    monkeypatch.setattr(AzureProvider, "get_obo_credential", fake_get_obo_credential)
    return recorder


@asynccontextmanager
async def relay_client(upstream: Upstream, bearer: str | None) -> AsyncIterator[Client]:
    """中継のサーバーを組み立て、AI ツールの代わりのクライアントで接続する。"""
    up_app = upstream.build()

    def transport_factory(url: str, headers: dict[str, str]) -> ClientTransport:
        if not upstream.up:
            return StreamableHttpTransport("http://127.0.0.1:9/mcp", headers=headers)
        return StreamableHttpTransport(url, headers=headers, httpx_client_factory=_asgi_client_factory(up_app, url))

    server = create_server(Settings.from_env(make_env()), transport_factory)
    server.auth = StaticTokenVerifier({USER_TOKEN: {"client_id": "ai-tool", "scopes": ["mcp.access"]}})
    app = server.http_app(path="/mcp", json_response=True)
    headers = {"X-Custom-Header": "do-not-forward"}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    transport = StreamableHttpTransport(
        "http://relay/mcp", headers=headers, httpx_client_factory=_asgi_client_factory(app, "http://relay")
    )
    async with up_app.router.lifespan_context(up_app), app.router.lifespan_context(app):
        async with Client(transport) as client:
            yield client


async def test_upstream_receives_exchanged_token_only(obo: OboRecorder) -> None:
    upstream = Upstream()
    async with relay_client(upstream, USER_TOKEN) as client:
        result = await client.call_tool("get_current_user", {})
    assert json.loads(result.content[0].text) == {"displayName": "Alice Mock"}
    received = upstream.headers[-1]
    assert received["authorization"] == f"Bearer {GRAPH_TOKEN}"
    assert USER_TOKEN not in json.dumps(received)
    assert "x-custom-header" not in received


async def test_tool_error_is_returned_unchanged(obo: OboRecorder) -> None:
    async with relay_client(Upstream(), USER_TOKEN) as client:
        result = await client.call_tool("failing_graph_call", {}, raise_on_error=False)
    assert result.is_error is True
    assert "Microsoft Graph API error: 404 Not Found" in result.content[0].text


async def test_tool_list_errors_when_upstream_is_down(obo: OboRecorder) -> None:
    upstream = Upstream(up=False)
    async with relay_client(upstream, USER_TOKEN) as client:
        with pytest.raises(Exception) as info:
            await client.list_tools()
    assert "tools" not in str(info.value).lower() or "0" not in str(info.value)


async def test_tool_list_errors_when_exchange_fails(obo: OboRecorder) -> None:
    obo.fail = True
    async with relay_client(Upstream(), USER_TOKEN) as client:
        with pytest.raises(Exception) as info:
            await client.list_tools()
    assert "AADSTS65001" not in str(info.value)
    assert USER_TOKEN not in str(info.value)


async def test_tool_call_error_is_masked_when_exchange_fails(obo: OboRecorder) -> None:
    upstream = Upstream()
    async with relay_client(upstream, USER_TOKEN) as client:
        await client.list_tools()
        obo.fail = True
        result = await client.call_tool("get_current_user", {}, raise_on_error=False)
    assert result.is_error is True
    assert "AADSTS65001" not in result.content[0].text
    assert upstream.headers == []


async def test_exchange_runs_for_each_relay(obo: OboRecorder) -> None:
    async with relay_client(Upstream(), USER_TOKEN) as client:
        await client.list_tools()
        await client.call_tool("get_current_user", {})
        await client.call_tool("get_current_user", {})
    assert obo.assertions == [USER_TOKEN, USER_TOKEN, USER_TOKEN]


async def test_without_user_token_upstream_is_not_called(obo: OboRecorder) -> None:
    upstream = Upstream()
    with pytest.raises(Exception):
        async with relay_client(upstream, None) as client:
            await client.list_tools()
    assert upstream.headers == []
    assert obo.assertions == []


def _pkce() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(b"v" * 40).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


@pytest.mark.parametrize("endpoint", ["full", "discovery"])
async def test_two_endpoints_have_own_resource_and_callback(endpoint: str) -> None:
    base = f"https://gw.test/{endpoint}"
    settings = Settings.from_env(make_env(APP_BASE_URL=base, APP_REQUIRE_CONSENT="false"))
    app = create_server(settings).http_app(path="/mcp", json_response=True)
    async with app.router.lifespan_context(app):
        async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url="http://relay") as http:
            meta = (await http.get(f"/.well-known/oauth-protected-resource/{endpoint}/mcp")).json()
            assert meta["resource"] == f"{base}/mcp"
            assert meta["authorization_servers"] == [base]

            registered = (
                await http.post(
                    "/register",
                    json={"redirect_uris": ["http://127.0.0.1:33418/callback"], "token_endpoint_auth_method": "none"},
                )
            ).json()
            _, challenge = _pkce()
            response = await http.get(
                "/authorize",
                params={
                    "response_type": "code",
                    "client_id": registered["client_id"],
                    "redirect_uri": "http://127.0.0.1:33418/callback",
                    "code_challenge": challenge,
                    "code_challenge_method": "S256",
                    "state": "s1",
                    "resource": f"{base}/mcp",
                },
            )
    assert response.status_code in (302, 307)
    upstream_query = parse_qs(urlparse(response.headers["location"]).query)
    assert upstream_query["redirect_uri"] == [f"{base}/auth/callback"]
