"""テスト用の MCP クライアント（AI ツールの代わり）。

httpx2 で OAuth 2.1 の流れ（DCR か CIMD の登録、認可、接続の確認画面のフォームの送信、Entra ID の模擬での
サインイン、戻りの受け取り、トークンの取得と更新）を行い、FastMCP のクライアントでツールを呼ぶ。
受け取った応答とトークンは、トークンが外に出ないことの確認のために記録のディレクトリに残す。
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import httpx2
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

CALLBACK_URI = "http://127.0.0.1:33418/callback"
CIMD_CLIENT_ID = "https://ai-tool.example.com/e2e/client-metadata.json"
API_SCOPE = "mcp.access"


def work_dir() -> Path:
    """E2E の作業ディレクトリ（記録と状態の置き場所）。"""
    path = Path(os.environ.get("E2E_WORK_DIR", "/work"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def base_host() -> str:
    """試す本システムの公開のホスト名。"""
    return os.environ.get("E2E_BASE_HOST", "gateway")


def ca_bundle() -> str:
    """公開 URL の証明書を確かめる認証局の束。"""
    return os.environ.get("E2E_CA_BUNDLE", "/certs/e2e-bundle.pem")


class _FormParser(HTMLParser):
    """HTML の最初のフォームの action と入力の値を読む。"""

    def __init__(self) -> None:
        super().__init__()
        self.action: str | None = None
        self.fields: dict[str, str] = {}
        self._in_form = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {k: v or "" for k, v in attrs}
        if tag == "form" and self.action is None:
            self.action = values.get("action", "")
            self._in_form = True
        elif tag == "input" and self._in_form and values.get("name"):
            self.fields[values["name"]] = values.get("value", "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "form":
            self._in_form = False


class SignInRejected(Exception):
    """サインインが拒否された（Entra ID のエラー画面など）。"""

    def __init__(self, status: int, body: str) -> None:
        super().__init__(f"サインインが拒否されました: {status} {body[:200]}")
        self.status = status
        self.body = body


@dataclass
class Tokens:
    """MCP サーバーのトークンの組。"""

    access_token: str
    refresh_token: str | None
    expires_in: int | None
    obtained_at: float = field(default_factory=time.time)


@dataclass
class McpOAuthClient:
    """1 つの受け口に対する、1 人の利用者のテスト用の MCP クライアント。

    Args:
        endpoint: `full` か `discovery`。
        name: 記録のファイル名に使う名前。
        registration: `dcr` か `cimd`。
    """

    endpoint: str
    name: str
    registration: str = "dcr"
    client_id: str | None = None
    tokens: Tokens | None = None
    history: list[dict[str, Any]] = field(default_factory=list)

    @property
    def base(self) -> str:
        """受け口の公開 URL（`https://<ホスト>/full` など）。"""
        return f"https://{base_host()}/{self.endpoint}"

    @property
    def mcp_url(self) -> str:
        """MCP の受け口の URL。"""
        return f"{self.base}/mcp"

    def _http(self) -> httpx2.Client:
        return httpx2.Client(verify=ca_bundle(), timeout=30, follow_redirects=False)

    def _record(self, kind: str, data: Any) -> None:
        self.history.append({"kind": kind, "at": time.time(), "data": data})
        path = work_dir() / "records" / f"{self.name}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        stored = {
            "endpoint": self.endpoint,
            "registration": self.registration,
            "client_id": self.client_id,
            "tokens": self.tokens.__dict__ if self.tokens else None,
            "history": self.history,
        }
        path.write_text(json.dumps(stored, ensure_ascii=False, indent=1, default=str), encoding="utf-8")

    # ---- 登録 -------------------------------------------------------------------

    def register(self) -> str:
        """DCR で登録するか、CIMD のクライアント ID を使う。クライアント ID を返す。"""
        if self.registration == "cimd":
            self.client_id = CIMD_CLIENT_ID
            self._record("register", {"method": "cimd", "client_id": self.client_id})
            return self.client_id
        with self._http() as http:
            response = http.post(
                f"{self.base}/register",
                json={
                    "client_name": f"E2E Test MCP Client ({self.name})",
                    "redirect_uris": [CALLBACK_URI],
                    "token_endpoint_auth_method": "none",
                    "grant_types": ["authorization_code", "refresh_token"],
                    "response_types": ["code"],
                },
            )
        response.raise_for_status()
        self.client_id = response.json()["client_id"]
        self._record("register", {"method": "dcr", "status": response.status_code, "body": response.json()})
        return self.client_id

    # ---- 認可 -------------------------------------------------------------------

    def sign_in(self, user: str) -> Tokens:
        """認可コード＋PKCE の流れを進め、Entra ID の模擬で `user` としてサインインしてトークンを得る。

        Raises:
            SignInRejected: Entra ID（模擬）がサインインを拒否した場合。
        """
        if self.client_id is None:
            self.register()
        verifier = secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        state = secrets.token_urlsafe(16)
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": CALLBACK_URI,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
            "scope": API_SCOPE,
            "resource": self.mcp_url,
        }
        with self._http() as http:
            url = f"{self.base}/authorize?{urlencode(params)}"
            if os.environ.get("E2E_MODE", "mock") == "real":
                final = _browser_authorization(url)
            else:
                final = follow_authorization(http, url, user, CALLBACK_URI, self._record)
            query = parse_qs(urlparse(final).query)
            if query.get("state") != [state]:
                raise AssertionError("state が一致しません")
            if "code" not in query:
                raise SignInRejected(400, final)
            code = query["code"][0]
            response = http.post(
                f"{self.base}/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": CALLBACK_URI,
                    "code_verifier": verifier,
                    "client_id": self.client_id,
                    "resource": self.mcp_url,
                },
            )
        self._record("token", {"status": response.status_code, "body": _safe_json(response)})
        response.raise_for_status()
        body = response.json()
        self.tokens = Tokens(body["access_token"], body.get("refresh_token"), body.get("expires_in"))
        self._record("tokens", {"received": True})
        return self.tokens

    def refresh(self) -> Tokens:
        """リフレッシュトークンでトークンを更新する。"""
        assert self.tokens is not None and self.tokens.refresh_token
        with self._http() as http:
            response = http.post(
                f"{self.base}/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.tokens.refresh_token,
                    "client_id": self.client_id,
                    "resource": self.mcp_url,
                },
            )
        self._record("refresh", {"status": response.status_code, "body": _safe_json(response)})
        response.raise_for_status()
        body = response.json()
        self.tokens = Tokens(body["access_token"], body.get("refresh_token", self.tokens.refresh_token), body.get("expires_in"))
        self._record("tokens", {"refreshed": True})
        return self.tokens

    # ---- MCP --------------------------------------------------------------------

    def ensure_fresh(self, margin: float = 15.0) -> None:
        """期限まで `margin` 秒を切ったトークンを更新する。"""
        if self.tokens and self.tokens.expires_in and self.tokens.refresh_token:
            if time.time() > self.tokens.obtained_at + self.tokens.expires_in - margin:
                self.refresh()

    def client(self, token: str | None = None) -> Client:
        """ツールを呼ぶ FastMCP のクライアントを返す（`async with` で使う）。"""
        if token is None:
            self.ensure_fresh()
        bearer = token if token is not None else (self.tokens.access_token if self.tokens else "")
        headers = {"Authorization": f"Bearer {bearer}"} if bearer else {}
        transport = StreamableHttpTransport(self.mcp_url, headers=headers)
        return Client(transport, timeout=120)

    async def list_tools(self) -> list[Any]:
        """ツールの一覧を取る。"""
        async with self.client() as client:
            tools = await client.list_tools()
        self._record("tools/list", {"count": len(tools)})
        return tools

    async def call(self, tool: str, arguments: dict[str, Any] | None = None) -> Any:
        """ツールを呼び、結果（`CallToolResult`）を返す。失敗も例外にせず返す。"""
        async with self.client() as client:
            result = await client.call_tool(tool, arguments or {}, raise_on_error=False)
        self._record(
            "tools/call",
            {"tool": tool, "is_error": result.is_error, "content": [getattr(c, "text", "") for c in result.content]},
        )
        return result

    async def call_text(self, tool: str, arguments: dict[str, Any] | None = None) -> tuple[bool, str]:
        """ツールを呼び、（失敗か、最初の本文）を返す。"""
        result = await self.call(tool, arguments)
        text = result.content[0].text if result.content else ""
        return bool(result.is_error), text

    async def execute(self, tool: str, arguments: dict[str, Any] | None = None) -> tuple[bool, str]:
        """受け口に合わせてツールを呼ぶ。探して使う受け口では `execute-tool` で呼ぶ。"""
        if self.endpoint == "discovery":
            return await self.call_text("execute-tool", {"tool_name": tool, "parameters": arguments or {}})
        return await self.call_text(tool, arguments)

    def save_state(self, key: str) -> None:
        """トークンとクライアント ID を状態のファイルに保存する（再起動の確認で使う）。"""
        path = work_dir() / "state" / f"{key}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"endpoint": self.endpoint, "client_id": self.client_id, "tokens": self.tokens.__dict__ if self.tokens else None}),
            encoding="utf-8",
        )

    @classmethod
    def load_state(cls, key: str, name: str) -> McpOAuthClient:
        """`save_state` で保存した状態から作り直す。"""
        data = json.loads((work_dir() / "state" / f"{key}.json").read_text(encoding="utf-8"))
        client = cls(endpoint=data["endpoint"], name=name, client_id=data["client_id"])
        if data["tokens"]:
            client.tokens = Tokens(**data["tokens"])
        return client


def follow_authorization(
    http: httpx2.Client,
    url: str,
    user: str,
    stop_prefix: str,
    record: Any = None,
) -> str:
    """認可の転送を 1 つずつ追い、`stop_prefix` で始まる URL に着いたらその URL を返す。

    本システムの接続の確認画面では許可を送り、Entra ID の模擬の認可の URL には `login_hint` を足して
    画面なしでサインインする。

    Raises:
        SignInRejected: 転送でも確認画面でもない応答（Entra ID のエラー画面など）が返った場合。
    """
    for _ in range(20):
        if url.startswith(stop_prefix):
            return url
        parsed = urlparse(url)
        if parsed.path.endswith("/oauth2/v2.0/authorize") and "login_hint" not in parse_qs(parsed.query):
            url = f"{url}&{urlencode({'login_hint': user})}"
        response = http.get(url)
        if record:
            record("authorize-step", {"url": _strip_query(url), "status": response.status_code})
        if response.status_code in (301, 302, 303, 307, 308):
            url = urljoin(url, response.headers["location"])
            continue
        if response.status_code == 200 and "consentForm" in response.text:
            parser = _FormParser()
            parser.feed(response.text)
            form = dict(parser.fields)
            form["action"] = "approve"
            target = urljoin(url, parser.action or url)
            posted = http.post(target, data=form)
            if record:
                record("consent", {"status": posted.status_code})
            if posted.status_code not in (302, 303, 307):
                raise SignInRejected(posted.status_code, posted.text)
            url = urljoin(target, posted.headers["location"])
            continue
        raise SignInRejected(response.status_code, response.text)
    raise AssertionError("転送が多すぎます")


def _browser_authorization(url: str, timeout: float = 300.0) -> str:
    """real モード：手元のブラウザで認可の URL を開き、手元の戻り先（127.0.0.1）で戻りを受けて、その URL を返す。"""
    import threading
    import webbrowser
    from http.server import BaseHTTPRequestHandler, HTTPServer

    received: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            received["url"] = f"http://127.0.0.1:33418{self.path}"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("サインインを受け取りました。このタブは閉じてかまいません。".encode())

        def log_message(self, *_: Any) -> None:
            return

    server = HTTPServer(("127.0.0.1", 33418), Handler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    print(f"\nブラウザで次の URL を開いてサインインしてください:\n{url}\n", flush=True)
    webbrowser.open(url)
    thread.join(timeout)
    server.server_close()
    if "url" not in received:
        raise AssertionError("サインインの戻りを受け取れませんでした")
    return received["url"]


def _safe_json(response: httpx2.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text[:500]


def _strip_query(url: str) -> str:
    return url.split("?", 1)[0]
