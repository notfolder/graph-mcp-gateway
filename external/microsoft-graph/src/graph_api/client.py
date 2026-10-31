"""Microsoft Graph v1.0 の薄い非同期クライアント。

各メソッドは Graph の 1 つのエンドポイントに 1 対 1 で対応し、応答の JSON をそのまま返す。
ページングの打ち切り、項目の絞り込み、エラーの文言など、業務の判断はここでは行わない。
ここで行うのは、HTTP の送受信、429・503 での再試行、Graph のエラー応答の例外への変換だけ。
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping
from typing import Any
from urllib.parse import quote

import httpx2

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
RETRY_STATUS = frozenset({429, 503})

JSON = dict[str, Any]
Params = Mapping[str, str | int]


class GraphError(Exception):
    """Graph がエラーを返したことを表す。

    Attributes:
        status: HTTP の状態コード。
        code: Graph の `error.code`（無い場合は空文字）。
        retry_after: 応答の `Retry-After`（秒）。無い場合は None。
    """

    def __init__(self, status: int, code: str, retry_after: float | None = None) -> None:
        super().__init__(f"Graph error {status} {code}".strip())
        self.status = status
        self.code = code
        self.retry_after = retry_after


def _seg(value: str) -> str:
    """パスの 1 区間として値を URL エンコードする（`/` もエンコードする）。"""
    return quote(value, safe="")


def _drive(drive_id: str | None) -> str:
    """ドライブのパスを返す。省略時は本人の OneDrive。"""
    return "/me/drive" if drive_id is None else f"/drives/{_seg(drive_id)}"


def _odata_quote(value: str) -> str:
    """OData の文字列リテラルとして値を引用する（`'` は `''` にする）。"""
    return "'" + value.replace("'", "''") + "'"


class GraphClient:
    """Microsoft Graph v1.0 の非同期クライアント。

    Args:
        access_token: Graph あてのアクセストークン（OBO で得たもの）。
        base_url: Graph のベース URL。
        transport: テスト用に差し替える HTTP トランスポート。None なら既定（環境変数のプロキシと OS の証明書ストアを使う）。
        max_retries: 429・503 のときの再試行の回数。
        sleep: 待つための関数（テストで差し替える）。
        timeout: 1 要求のタイムアウト（秒）。
    """

    def __init__(
        self,
        access_token: str,
        *,
        base_url: str = GRAPH_BASE_URL,
        transport: httpx2.AsyncBaseTransport | None = None,
        max_retries: int = 3,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        timeout: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._max_retries = max_retries
        self._sleep = sleep
        self._http = httpx2.AsyncClient(
            headers={"Authorization": f"Bearer {access_token}"},
            transport=transport,
            timeout=timeout,
        )

    async def __aenter__(self) -> GraphClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """HTTP クライアントを閉じる。"""
        await self._http.aclose()

    # ---- 送受信 -------------------------------------------------------------

    async def request(
        self,
        method: str,
        path_or_url: str,
        *,
        params: Params | None = None,
        json_body: JSON | None = None,
        content: bytes | None = None,
        headers: Mapping[str, str] | None = None,
        follow_redirects: bool = False,
    ) -> httpx2.Response:
        """Graph に要求を送り、成功の応答を返す。

        `path_or_url` が `/` で始まればベース URL につなぐ。完全な URL（`@odata.nextLink`）はそのまま使う。
        429・503 は `Retry-After`（無ければ 1, 2, 4 … 秒）だけ待って再試行する。
        2xx 以外は GraphError を送出する。
        """
        url = self.base_url + path_or_url if path_or_url.startswith("/") else path_or_url
        attempt = 0
        while True:
            response = await self._http.request(
                method,
                url,
                params=params,
                json=json_body,
                content=content,
                headers=headers,
                follow_redirects=follow_redirects,
            )
            if response.is_success:
                return response
            if response.status_code in RETRY_STATUS and attempt < self._max_retries:
                await self._sleep(_retry_after(response) or float(2**attempt))
                attempt += 1
                continue
            raise _to_error(response)

    async def _json(self, method: str, path: str, **kwargs: Any) -> JSON:
        response = await self.request(method, path, **kwargs)
        if response.status_code == 204 or not response.content:
            return {}
        return response.json()

    async def get_page(self, next_link: str) -> JSON:
        """`@odata.nextLink` の URL をそのまま取得する。"""
        return await self._json("GET", next_link)

    # ---- プロフィール -------------------------------------------------------

    async def get_me(self, params: Params | None = None) -> JSON:
        """GET /me"""
        return await self._json("GET", "/me", params=params)

    # ---- メール -------------------------------------------------------------

    async def list_mail_folders(self, params: Params | None = None) -> JSON:
        """GET /me/mailFolders"""
        return await self._json("GET", "/me/mailFolders", params=params)

    async def list_child_mail_folders(self, folder_id: str, params: Params | None = None) -> JSON:
        """GET /me/mailFolders/{id}/childFolders"""
        return await self._json("GET", f"/me/mailFolders/{_seg(folder_id)}/childFolders", params=params)

    async def list_messages(self, params: Params | None = None) -> JSON:
        """GET /me/messages"""
        return await self._json("GET", "/me/messages", params=params)

    async def list_folder_messages(self, folder_id: str, params: Params | None = None) -> JSON:
        """GET /me/mailFolders/{id}/messages"""
        return await self._json("GET", f"/me/mailFolders/{_seg(folder_id)}/messages", params=params)

    async def get_message(self, message_id: str, headers: Mapping[str, str] | None = None) -> JSON:
        """GET /me/messages/{id}"""
        return await self._json("GET", f"/me/messages/{_seg(message_id)}", headers=headers)

    async def list_attachments(self, message_id: str, params: Params | None = None) -> JSON:
        """GET /me/messages/{id}/attachments"""
        return await self._json("GET", f"/me/messages/{_seg(message_id)}/attachments", params=params)

    async def create_message(self, body: JSON) -> JSON:
        """POST /me/messages（下書きの作成）"""
        return await self._json("POST", "/me/messages", json_body=body)

    async def update_message(self, message_id: str, body: JSON) -> JSON:
        """PATCH /me/messages/{id}"""
        return await self._json("PATCH", f"/me/messages/{_seg(message_id)}", json_body=body)

    async def send_mail(self, body: JSON) -> None:
        """POST /me/sendMail（202、本文なし）"""
        await self.request("POST", "/me/sendMail", json_body=body)

    async def send_message(self, message_id: str) -> None:
        """POST /me/messages/{id}/send（202、本文なし。`Content-Length: 0` を送る）"""
        await self.request("POST", f"/me/messages/{_seg(message_id)}/send", content=b"")

    async def reply_message(self, message_id: str, body: JSON) -> None:
        """POST /me/messages/{id}/reply"""
        await self.request("POST", f"/me/messages/{_seg(message_id)}/reply", json_body=body)

    async def reply_all_message(self, message_id: str, body: JSON) -> None:
        """POST /me/messages/{id}/replyAll"""
        await self.request("POST", f"/me/messages/{_seg(message_id)}/replyAll", json_body=body)

    async def forward_message(self, message_id: str, body: JSON) -> None:
        """POST /me/messages/{id}/forward"""
        await self.request("POST", f"/me/messages/{_seg(message_id)}/forward", json_body=body)

    async def move_message(self, message_id: str, destination_id: str) -> JSON:
        """POST /me/messages/{id}/move（移動先のメールを返す。ID は変わる）"""
        return await self._json(
            "POST", f"/me/messages/{_seg(message_id)}/move", json_body={"destinationId": destination_id}
        )

    async def delete_message(self, message_id: str) -> None:
        """DELETE /me/messages/{id}"""
        await self.request("DELETE", f"/me/messages/{_seg(message_id)}")

    # ---- 予定表 -------------------------------------------------------------

    async def list_calendar_view(self, params: Params, headers: Mapping[str, str] | None = None) -> JSON:
        """GET /me/calendarView（startDateTime と endDateTime が必須）"""
        return await self._json("GET", "/me/calendarView", params=params, headers=headers)

    async def get_event(self, event_id: str, headers: Mapping[str, str] | None = None) -> JSON:
        """GET /me/events/{id}"""
        return await self._json("GET", f"/me/events/{_seg(event_id)}", headers=headers)

    async def create_event(self, body: JSON, headers: Mapping[str, str] | None = None) -> JSON:
        """POST /me/events"""
        return await self._json("POST", "/me/events", json_body=body, headers=headers)

    async def update_event(self, event_id: str, body: JSON, headers: Mapping[str, str] | None = None) -> JSON:
        """PATCH /me/events/{id}"""
        return await self._json("PATCH", f"/me/events/{_seg(event_id)}", json_body=body, headers=headers)

    async def delete_event(self, event_id: str) -> None:
        """DELETE /me/events/{id}"""
        await self.request("DELETE", f"/me/events/{_seg(event_id)}")

    async def respond_event(self, event_id: str, action: str, body: JSON) -> None:
        """POST /me/events/{id}/{accept|tentativelyAccept|decline}（202、本文なし）"""
        if action not in ("accept", "tentativelyAccept", "decline"):
            raise ValueError(f"unknown action: {action}")
        await self.request("POST", f"/me/events/{_seg(event_id)}/{action}", json_body=body)

    # ---- ファイル -----------------------------------------------------------

    async def list_children(self, drive_id: str | None, item_id: str | None, params: Params | None = None) -> JSON:
        """GET {drive}/root/children または {drive}/items/{id}/children"""
        base = _drive(drive_id)
        path = f"{base}/root/children" if item_id is None else f"{base}/items/{_seg(item_id)}/children"
        return await self._json("GET", path, params=params)

    async def search_drive(self, drive_id: str | None, query: str, params: Params | None = None) -> JSON:
        """GET {drive}/root/search(q='...')"""
        path = f"{_drive(drive_id)}/root/search(q={quote(_odata_quote(query), safe='')})"
        return await self._json("GET", path, params=params)

    async def get_item(self, drive_id: str | None, item_id: str, params: Params | None = None) -> JSON:
        """GET {drive}/items/{id}"""
        return await self._json("GET", f"{_drive(drive_id)}/items/{_seg(item_id)}", params=params)

    async def get_item_content(self, drive_id: str | None, item_id: str) -> httpx2.Response:
        """GET {drive}/items/{id}/content。302 の転送をたどり、転送先の応答を返す。

        httpx2 は別のオリジンへの転送では Authorization ヘッダーを外すので、転送先にトークンは送られない。
        """
        return await self.request("GET", f"{_drive(drive_id)}/items/{_seg(item_id)}/content", follow_redirects=True)

    async def put_content(
        self, drive_id: str | None, parent_id: str, name: str, data: bytes, conflict_behavior: str = "replace"
    ) -> JSON:
        """PUT {drive}/items/{parent-id}:/{name}:/content（簡易アップロード、250 MB まで）"""
        path = (
            f"{_drive(drive_id)}/items/{_seg(parent_id)}:/{_seg(name)}:/content"
            f"?@microsoft.graph.conflictBehavior={_seg(conflict_behavior)}"
        )
        return await self._json(
            "PUT",
            path,
            content=data,
            headers={"Content-Type": "application/octet-stream"},
        )

    async def create_folder(
        self, drive_id: str | None, parent_id: str, name: str, conflict_behavior: str = "fail"
    ) -> JSON:
        """POST {drive}/items/{parent-id}/children（フォルダーの作成）"""
        body = {"name": name, "folder": {}, "@microsoft.graph.conflictBehavior": conflict_behavior}
        return await self._json("POST", f"{_drive(drive_id)}/items/{_seg(parent_id)}/children", json_body=body)

    async def update_item(self, drive_id: str | None, item_id: str, body: JSON) -> JSON:
        """PATCH {drive}/items/{id}（名前の変更・移動）"""
        return await self._json("PATCH", f"{_drive(drive_id)}/items/{_seg(item_id)}", json_body=body)

    async def delete_item(self, drive_id: str | None, item_id: str) -> None:
        """DELETE {drive}/items/{id}"""
        await self.request("DELETE", f"{_drive(drive_id)}/items/{_seg(item_id)}")

    # ---- SharePoint ---------------------------------------------------------

    async def search_sites(self, query: str, params: Params | None = None) -> JSON:
        """GET /sites?search={query}"""
        return await self._json("GET", "/sites", params={"search": query, **(params or {})})

    async def list_site_drives(self, site_id: str, params: Params | None = None) -> JSON:
        """GET /sites/{id}/drives"""
        return await self._json("GET", f"/sites/{_seg(site_id)}/drives", params=params)

    # ---- Teams --------------------------------------------------------------

    async def list_chats(self, params: Params | None = None) -> JSON:
        """GET /me/chats"""
        return await self._json("GET", "/me/chats", params=params)

    async def list_chat_messages(self, chat_id: str, params: Params | None = None) -> JSON:
        """GET /chats/{id}/messages"""
        return await self._json("GET", f"/chats/{_seg(chat_id)}/messages", params=params)

    async def post_chat_message(self, chat_id: str, body: JSON) -> JSON:
        """POST /chats/{id}/messages"""
        return await self._json("POST", f"/chats/{_seg(chat_id)}/messages", json_body=body)

    async def list_joined_teams(self) -> JSON:
        """GET /me/joinedTeams（OData の引数は使えない）"""
        return await self._json("GET", "/me/joinedTeams")

    async def list_channels(self, team_id: str, params: Params | None = None) -> JSON:
        """GET /teams/{id}/channels"""
        return await self._json("GET", f"/teams/{_seg(team_id)}/channels", params=params)

    async def list_channel_messages(self, team_id: str, channel_id: str, params: Params | None = None) -> JSON:
        """GET /teams/{id}/channels/{id}/messages"""
        path = f"/teams/{_seg(team_id)}/channels/{_seg(channel_id)}/messages"
        return await self._json("GET", path, params=params)

    async def list_message_replies(
        self, team_id: str, channel_id: str, message_id: str, params: Params | None = None
    ) -> JSON:
        """GET /teams/{id}/channels/{id}/messages/{id}/replies"""
        path = f"/teams/{_seg(team_id)}/channels/{_seg(channel_id)}/messages/{_seg(message_id)}/replies"
        return await self._json("GET", path, params=params)

    async def post_channel_message(self, team_id: str, channel_id: str, body: JSON) -> JSON:
        """POST /teams/{id}/channels/{id}/messages"""
        path = f"/teams/{_seg(team_id)}/channels/{_seg(channel_id)}/messages"
        return await self._json("POST", path, json_body=body)

    async def post_message_reply(self, team_id: str, channel_id: str, message_id: str, body: JSON) -> JSON:
        """POST /teams/{id}/channels/{id}/messages/{id}/replies"""
        path = f"/teams/{_seg(team_id)}/channels/{_seg(channel_id)}/messages/{_seg(message_id)}/replies"
        return await self._json("POST", path, json_body=body)


def _retry_after(response: httpx2.Response) -> float | None:
    value = response.headers.get("Retry-After")
    if value is None:
        return None
    try:
        return max(float(value), 0.0)
    except ValueError:
        return None


def _to_error(response: httpx2.Response) -> GraphError:
    code = ""
    try:
        payload = response.json()
        if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
            code = str(payload["error"].get("code", ""))
    except (json.JSONDecodeError, ValueError):
        pass
    return GraphError(response.status_code, code, _retry_after(response))
