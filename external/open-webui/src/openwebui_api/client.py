"""Open WebUI（v0.12.5）の API の薄い非同期クライアント。

各メソッドは Open WebUI の 1 つのエンドポイントに 1 対 1 で対応し、応答の JSON をそのまま返す。
初期設定の手順（どの順に何を登録するか）や、OAuth の認可の画面を進める処理はここでは行わない。
ここで行うのは、HTTP の送受信、ログインのトークンの付与、Cookie の持ち回し、エラー応答の例外への変換だけ。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

import httpx2

JSON = dict[str, Any]


class OpenWebUIError(Exception):
    """Open WebUI がエラーを返したことを表す。

    Attributes:
        status: HTTP の状態コード。
        detail: 応答の `detail`（無い場合は応答の本文の先頭）。
    """

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(f"Open WebUI error {status}: {detail}")
        self.status = status
        self.detail = detail


def _seg(value: str) -> str:
    """パスの 1 区間として値を URL エンコードする（`:` は Open WebUI の接続の ID に使うので残す）。"""
    return quote(value, safe=":")


class OpenWebUIClient:
    """Open WebUI の非同期クライアント。

    1 つのインスタンスは 1 人のログインの状態（トークンと Cookie）を持つ。
    OAuth の認可の開始から戻り先までは同じ Cookie（`owui-session`）が要るので、同じインスタンスを使う。

    Args:
        base_url: Open WebUI の公開 URL（`WEBUI_URL` と同じ origin にする）。
        transport: テスト用に差し替える HTTP トランスポート。
        verify: サーバー証明書の確認に使う CA のファイルのパス。None なら既定。
        timeout: 1 要求のタイムアウト（秒）。
    """

    def __init__(
        self,
        base_url: str,
        *,
        transport: httpx2.AsyncBaseTransport | None = None,
        verify: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        options: dict[str, Any] = {"transport": transport, "timeout": timeout}
        if verify is not None:
            options["verify"] = verify
        self._http = httpx2.AsyncClient(base_url=self.base_url, **options)
        self._token: str | None = None

    async def __aenter__(self) -> OpenWebUIClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """HTTP クライアントを閉じる。"""
        await self._http.aclose()

    @property
    def token(self) -> str | None:
        """ログインで得たトークン（未ログインなら None）。"""
        return self._token

    # ---- 送受信 -------------------------------------------------------------

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
        json_body: Any = None,
        follow_redirects: bool = False,
    ) -> httpx2.Response:
        """Open WebUI に要求を送り、応答を返す。

        ログイン済みならトークンを `Authorization: Bearer` で付ける。
        2xx と 3xx 以外は OpenWebUIError を送出する（3xx は認可の転送を呼び出し側で追うため返す）。
        """
        headers = {"Authorization": f"Bearer {self._token}"} if self._token else None
        response = await self._http.request(
            method,
            path,
            params=params,
            json=json_body,
            headers=headers,
            follow_redirects=follow_redirects,
        )
        if response.status_code >= 400:
            raise _to_error(response)
        return response

    async def _json(self, method: str, path: str, **kwargs: Any) -> Any:
        response = await self.request(method, path, **kwargs)
        if not response.content:
            return {}
        return response.json()

    # ---- 状態とログイン -----------------------------------------------------

    async def health(self) -> JSON:
        """`GET /health`：起動が終わっているかを返す。"""
        return await self._json("GET", "/health")

    async def signin(self, email: str, password: str) -> JSON:
        """`POST /api/v1/auths/signin`：ログインし、トークンをこのインスタンスに保持する。"""
        body = await self._json("POST", "/api/v1/auths/signin", json_body={"email": email, "password": password})
        self._token = body.get("token")
        return body

    async def signup(self, name: str, email: str, password: str) -> JSON:
        """`POST /api/v1/auths/signup`：利用者自身の登録（受け付けない設定なら 403）。"""
        return await self._json(
            "POST", "/api/v1/auths/signup", json_body={"name": name, "email": email, "password": password}
        )

    async def add_user(self, name: str, email: str, password: str, role: str = "user") -> JSON:
        """`POST /api/v1/auths/add`：管理者が利用者を作る。"""
        return await self._json(
            "POST",
            "/api/v1/auths/add",
            json_body={"name": name, "email": email, "password": password, "role": role},
        )

    # ---- ツールサーバー（MCP）の接続先 ---------------------------------------

    async def register_oauth_client(
        self, url: str, connection_id: str, oauth_scope: str | None = None, client_type: str = "mcp"
    ) -> JSON:
        """`POST /api/v1/configs/oauth/clients/register`：MCP の受け口に DCR で登録し、暗号化したクライアントの情報を返す。

        この時点では保存されない。返した `oauth_client_info` を接続先の設定に入れて `set_tool_servers` で保存する。
        """
        body: JSON = {"url": url, "client_id": connection_id}
        if oauth_scope is not None:
            body["oauth_scope"] = oauth_scope
        return await self._json(
            "POST", "/api/v1/configs/oauth/clients/register", params={"type": client_type}, json_body=body
        )

    async def get_tool_servers(self) -> JSON:
        """`GET /api/v1/configs/tool_servers`：ツールサーバーの接続先の一覧を返す。"""
        return await self._json("GET", "/api/v1/configs/tool_servers")

    async def set_tool_servers(self, connections: list[JSON]) -> JSON:
        """`POST /api/v1/configs/tool_servers`：ツールサーバーの接続先の一覧を、渡したもので置き換える。"""
        return await self._json(
            "POST", "/api/v1/configs/tool_servers", json_body={"TOOL_SERVER_CONNECTIONS": connections}
        )

    async def list_tools(self) -> list[JSON]:
        """`GET /api/v1/tools/`：使えるツールの一覧（MCP の接続先の認可の状態を含む）を返す。"""
        return await self._json("GET", "/api/v1/tools/")

    async def start_mcp_authorization(self, connection_key: str) -> httpx2.Response:
        """`GET /oauth/clients/{connection_key}/authorize`：MCP の受け口の認可を始め、転送の応答を返す（転送は追わない）。

        `connection_key` は `mcp:<接続の ID>` の形。
        """
        return await self.request("GET", f"/oauth/clients/{_seg(connection_key)}/authorize")

    async def finish_mcp_authorization(self, callback_url: str) -> httpx2.Response:
        """認可の戻り先（`/oauth/clients/{connection_key}/callback?...`）を呼び、応答を返す（転送は追わない）。"""
        return await self.request("GET", callback_url)

    async def delete_oauth_session(self, connection_key: str) -> JSON:
        """`DELETE /api/v1/auths/oauth/sessions/{connection_key}`：MCP の受け口との接続（保管したトークン）を消す。"""
        return await self._json("DELETE", f"/api/v1/auths/oauth/sessions/{_seg(connection_key)}")

    # ---- モデル --------------------------------------------------------------

    async def list_models(self) -> JSON:
        """`GET /api/models`：使えるモデルの一覧を返す。"""
        return await self._json("GET", "/api/models")

    async def get_model(self, model_id: str) -> JSON:
        """`GET /api/v1/models/model?id=...`：モデルの設定（公開の範囲を含む）を返す。設定が無ければ 404。"""
        return await self._json("GET", "/api/v1/models/model", params={"id": model_id})

    async def create_model(self, model: JSON) -> JSON:
        """`POST /api/v1/models/create`：モデルの設定（公開の範囲を含む）を作る。"""
        return await self._json("POST", "/api/v1/models/create", json_body=model)

    # ---- チャット ------------------------------------------------------------

    async def create_chat(self, chat: JSON) -> JSON:
        """`POST /api/v1/chats/new`：チャットの記録を作る。"""
        return await self._json("POST", "/api/v1/chats/new", json_body={"chat": chat})

    async def get_chat(self, chat_id: str) -> JSON:
        """`GET /api/v1/chats/{chat_id}`：チャットの記録を返す。"""
        return await self._json("GET", f"/api/v1/chats/{_seg(chat_id)}")

    async def delete_chat(self, chat_id: str) -> JSON:
        """`DELETE /api/v1/chats/{chat_id}`：チャットの記録を消す。"""
        return await self._json("DELETE", f"/api/v1/chats/{_seg(chat_id)}")

    async def chat_completions(self, payload: JSON) -> JSON:
        """`POST /api/chat/completions`：発言を送る。

        ツールを実行させるには、`chat_id`・`id`（アシスタントのメッセージ ID）・`session_id`・`tool_ids` を付ける。
        チャットの記録の無い要求では、Open WebUI はツールを実行しない。
        """
        return await self._json("POST", "/api/chat/completions", json_body=payload)


def _to_error(response: httpx2.Response) -> OpenWebUIError:
    """エラーの応答を例外に変換する。"""
    try:
        detail = str(response.json().get("detail", ""))
    except ValueError:
        detail = response.text[:200]
    return OpenWebUIError(response.status_code, detail)
