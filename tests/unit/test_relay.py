"""中継（GraphTokenExchanger・RelayClientFactory）の単体テスト。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from fastmcp.client.transports import ClientTransport, StreamableHttpTransport
from fastmcp.server.auth.auth import AccessToken
from fastmcp.server.providers.proxy import ProxyClient

from graph_mcp_gateway import relay as relay_module
from graph_mcp_gateway.relay import GraphTokenExchanger, RelayClientFactory


@dataclass
class FakeToken:
    token: str


class FakeCredential:
    """OBO の資格情報の代わり。要求された権限を記録する。"""

    def __init__(self, error: Exception | None = None) -> None:
        self.scopes: tuple[str, ...] = ()
        self.error = error

    async def get_token(self, *scopes: str) -> FakeToken:
        self.scopes = scopes
        if self.error is not None:
            raise self.error
        return FakeToken("graph-token")


class FakeProvider:
    """AzureProvider の代わり。OBO に渡された利用者のトークンを記録する。"""

    def __init__(self, credential: FakeCredential) -> None:
        self.credential = credential
        self.assertions: list[str] = []

    async def get_obo_credential(self, user_assertion: str) -> FakeCredential:
        self.assertions.append(user_assertion)
        return self.credential


class FakeExchanger:
    """GraphTokenExchanger の代わり。"""

    def __init__(self) -> None:
        self.received: list[str | None] = []

    async def exchange(self, entra_token: str | None) -> str:
        self.received.append(entra_token)
        if not entra_token:
            raise PermissionError("no token")
        return "graph-token"


async def test_exchange_requests_graph_scopes_with_user_token() -> None:
    credential = FakeCredential()
    provider = FakeProvider(credential)
    exchanger = GraphTokenExchanger(provider, ["User.Read", "Mail.Send"])  # type: ignore[arg-type]
    assert await exchanger.exchange("entra-token") == "graph-token"
    assert provider.assertions == ["entra-token"]
    assert credential.scopes == ("https://graph.microsoft.com/User.Read", "https://graph.microsoft.com/Mail.Send")


@pytest.mark.parametrize("token", [None, ""])
async def test_exchange_without_user_token_fails_and_does_not_call_obo(token: str | None) -> None:
    provider = FakeProvider(FakeCredential())
    exchanger = GraphTokenExchanger(provider, ["User.Read"])  # type: ignore[arg-type]
    with pytest.raises(PermissionError):
        await exchanger.exchange(token)
    assert provider.assertions == []


async def test_exchange_failure_logs_code_without_token(caplog: pytest.LogCaptureFixture) -> None:
    error = RuntimeError("AADSTS65001: consent required for entra-token")
    exchanger = GraphTokenExchanger(FakeProvider(FakeCredential(error)), ["User.Read"])  # type: ignore[arg-type]
    with pytest.raises(RuntimeError):
        await exchanger.exchange("entra-token")
    assert "AADSTS65001" in caplog.text
    assert "entra-token" not in caplog.text


def _with_user(monkeypatch: pytest.MonkeyPatch, token: str | None) -> None:
    value = AccessToken(token=token, client_id="c", scopes=[]) if token else None
    monkeypatch.setattr(relay_module, "get_access_token", lambda: value)


async def test_factory_sets_exchanged_token_in_header_and_disables_forwarding(monkeypatch: pytest.MonkeyPatch) -> None:
    _with_user(monkeypatch, "entra-token")
    recorded: dict[str, Any] = {}

    def transport_factory(url: str, headers: dict[str, str]) -> ClientTransport:
        recorded["url"] = url
        recorded["headers"] = headers
        return StreamableHttpTransport(url, headers=headers)

    exchanger = FakeExchanger()
    factory = RelayClientFactory("http://ms365-full:3000/mcp", exchanger, transport_factory)  # type: ignore[arg-type]
    client = await factory()

    assert isinstance(client, ProxyClient)
    assert exchanger.received == ["entra-token"]
    assert recorded == {"url": "http://ms365-full:3000/mcp", "headers": {"Authorization": "Bearer graph-token"}}
    assert client._transport_options.forward_incoming_headers is False


async def test_factory_default_transport_uses_headers_not_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    _with_user(monkeypatch, "entra-token")
    factory = RelayClientFactory("http://ms365-full:3000/mcp", FakeExchanger())  # type: ignore[arg-type]
    client = await factory()
    transport = client.transport
    assert isinstance(transport, StreamableHttpTransport)
    assert transport.url == "http://ms365-full:3000/mcp"
    assert transport.headers == {"Authorization": "Bearer graph-token"}
    assert transport.auth is None


async def test_factory_without_user_token_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    _with_user(monkeypatch, None)
    called: list[str] = []

    def transport_factory(url: str, headers: dict[str, str]) -> ClientTransport:
        called.append(url)
        return StreamableHttpTransport(url, headers=headers)

    exchanger = FakeExchanger()
    factory = RelayClientFactory("http://ms365-full:3000/mcp", exchanger, transport_factory)  # type: ignore[arg-type]
    with pytest.raises(PermissionError):
        await factory()
    assert called == []
