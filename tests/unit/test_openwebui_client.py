"""Open WebUI の連携ライブラリ（OpenWebUIClient・OpenWebUIError）の単体テスト。"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

import httpx2
import pytest
from openwebui_api import OpenWebUIClient, OpenWebUIError


class Recorder:
    """送られた要求を記録し、決まった応答を返す。"""

    def __init__(self, response: httpx2.Response | None = None) -> None:
        self.requests: list[httpx2.Request] = []
        self.response = response

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        if self.response is not None:
            return self.response
        if request.url.path == "/api/v1/auths/signin":
            return httpx2.Response(200, json={"token": "login-token"})
        return httpx2.Response(200, json={"ok": True})


def _client(recorder: Recorder) -> OpenWebUIClient:
    return OpenWebUIClient("https://owui.test/", transport=httpx2.MockTransport(recorder))


Call = Callable[[OpenWebUIClient], Awaitable[Any]]

CASES: list[tuple[str, Call, str, str, dict[str, str] | None, Any]] = [
    ("health", lambda c: c.health(), "GET", "/health", None, None),
    ("signup", lambda c: c.signup("n", "e@x.test", "p"), "POST", "/api/v1/auths/signup", None,
     {"name": "n", "email": "e@x.test", "password": "p"}),
    ("add_user", lambda c: c.add_user("n", "e@x.test", "p"), "POST", "/api/v1/auths/add", None,
     {"name": "n", "email": "e@x.test", "password": "p", "role": "user"}),
    ("register", lambda c: c.register_oauth_client("https://gw.test/discovery/mcp", "m365"), "POST",
     "/api/v1/configs/oauth/clients/register", {"type": "mcp"},
     {"url": "https://gw.test/discovery/mcp", "client_id": "m365"}),
    ("register_scope", lambda c: c.register_oauth_client("https://u", "m365", oauth_scope="s"), "POST",
     "/api/v1/configs/oauth/clients/register", {"type": "mcp"}, {"url": "https://u", "client_id": "m365", "oauth_scope": "s"}),
    ("get_tool_servers", lambda c: c.get_tool_servers(), "GET", "/api/v1/configs/tool_servers", None, None),
    ("set_tool_servers", lambda c: c.set_tool_servers([{"url": "u"}]), "POST", "/api/v1/configs/tool_servers", None,
     {"TOOL_SERVER_CONNECTIONS": [{"url": "u"}]}),
    ("list_tools", lambda c: c.list_tools(), "GET", "/api/v1/tools/", None, None),
    ("start_auth", lambda c: c.start_mcp_authorization("mcp:m365"), "GET", "/oauth/clients/mcp:m365/authorize", None, None),
    ("finish_auth", lambda c: c.finish_mcp_authorization("/oauth/clients/mcp:m365/callback?code=a&state=b"), "GET",
     "/oauth/clients/mcp:m365/callback", {"code": "a", "state": "b"}, None),
    ("delete_session", lambda c: c.delete_oauth_session("mcp:m365"), "DELETE", "/api/v1/auths/oauth/sessions/mcp:m365",
     None, None),
    ("list_models", lambda c: c.list_models(), "GET", "/api/models", None, None),
    ("get_model", lambda c: c.get_model("poc-assistant"), "GET", "/api/v1/models/model", {"id": "poc-assistant"}, None),
    ("create_model", lambda c: c.create_model({"id": "m"}), "POST", "/api/v1/models/create", None, {"id": "m"}),
    ("create_chat", lambda c: c.create_chat({"title": "t"}), "POST", "/api/v1/chats/new", None, {"chat": {"title": "t"}}),
    ("get_chat", lambda c: c.get_chat("a b"), "GET", "/api/v1/chats/a%20b", None, None),
    ("delete_chat", lambda c: c.delete_chat("c1"), "DELETE", "/api/v1/chats/c1", None, None),
    ("chat_completions", lambda c: c.chat_completions({"model": "m"}), "POST", "/api/chat/completions", None,
     {"model": "m"}),
]


@pytest.mark.parametrize(("name", "call", "method", "path", "params", "body"), CASES, ids=[c[0] for c in CASES])
async def test_method_sends_expected_request(
    name: str, call: Call, method: str, path: str, params: dict[str, str] | None, body: Any
) -> None:
    recorder = Recorder()
    async with _client(recorder) as client:
        await call(client)
    [request] = recorder.requests
    assert request.method == method
    assert request.url.raw_path.decode().split("?")[0] == path
    assert dict(request.url.params) == (params or {})
    if body is None:
        assert not request.content
    else:
        assert json.loads(request.content) == body


async def test_signin_keeps_token_and_sends_it_afterwards() -> None:
    recorder = Recorder()
    async with _client(recorder) as client:
        await client.signin("admin@x.test", "pw")
        assert client.token == "login-token"
        await client.list_models()
    signin, models = recorder.requests
    assert json.loads(signin.content) == {"email": "admin@x.test", "password": "pw"}
    assert "authorization" not in signin.headers
    assert models.headers["authorization"] == "Bearer login-token"


async def test_error_status_becomes_exception_with_detail() -> None:
    recorder = Recorder(httpx2.Response(403, json={"detail": "Access prohibited"}))
    async with _client(recorder) as client:
        with pytest.raises(OpenWebUIError) as info:
            await client.signup("n", "e@x.test", "p")
    assert info.value.status == 403
    assert info.value.detail == "Access prohibited"


async def test_error_without_json_uses_text() -> None:
    recorder = Recorder(httpx2.Response(500, text="Internal Server Error"))
    async with _client(recorder) as client:
        with pytest.raises(OpenWebUIError) as info:
            await client.health()
    assert info.value.status == 500
    assert "Internal Server Error" in info.value.detail


async def test_redirect_is_returned_not_followed() -> None:
    recorder = Recorder(httpx2.Response(302, headers={"location": "https://gw.test/discovery/authorize?x=1"}))
    async with _client(recorder) as client:
        response = await client.start_mcp_authorization("mcp:m365")
    assert response.status_code == 302
    assert response.headers["location"].startswith("https://gw.test/discovery/authorize")
    assert len(recorder.requests) == 1
