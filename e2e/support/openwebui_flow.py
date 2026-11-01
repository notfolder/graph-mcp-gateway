"""Open WebUI を HTTP の要求だけで動かす部品（ブラウザの自動操作なし）。

認可は Open WebUI の Cookie を持ち回す連携ライブラリのクライアントで始め、本システムと Entra ID の模擬の転送は
別の HTTP クライアントで 1 つずつ追い、戻り先を同じ Open WebUI のクライアントで呼ぶ。
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any
from urllib.parse import urljoin

import httpx2
from openwebui_api import OpenWebUIClient

from .mcp_client import base_host, ca_bundle, follow_authorization

CONNECTION_KEY = "mcp:m365"
TOOL_ID = "server:mcp:m365"


def open_webui_url() -> str:
    """Open WebUI の公開 URL。"""
    return f"https://{base_host()}:8443"


def new_client() -> OpenWebUIClient:
    """Open WebUI のクライアントを作る。"""
    return OpenWebUIClient(open_webui_url(), verify=ca_bundle())


async def mcp_authenticated(client: OpenWebUIClient) -> bool | None:
    """ツールの一覧から、M365 の接続先の認可の状態を返す（接続先が無ければ None）。"""
    for tool in await client.list_tools():
        if tool.get("id") == TOOL_ID:
            return bool(tool.get("authenticated"))
    return None


async def authorize_mcp(client: OpenWebUIClient, user: str) -> None:
    """ログイン済みの Open WebUI の利用者で、探して使う受け口の認可を最後まで進める。"""
    start = await client.start_mcp_authorization(CONNECTION_KEY)
    assert start.status_code in (302, 303, 307), start.status_code
    url = urljoin(open_webui_url(), start.headers["location"])
    callback_prefix = f"{open_webui_url()}/oauth/clients/{CONNECTION_KEY}/callback"

    def follow() -> str:
        with httpx2.Client(verify=ca_bundle(), timeout=60, follow_redirects=False) as http:
            return follow_authorization(http, url, user, callback_prefix)

    callback = await asyncio.to_thread(follow)
    finish = await client.finish_mcp_authorization(callback)
    assert finish.status_code in (200, 302, 303, 307), finish.status_code


async def send_and_wait(client: OpenWebUIClient, model: str, content: str, timeout: float = 120.0) -> dict[str, Any]:
    """チャットを作って発言を送り、アシスタントの応答が記録に入るまで待って、チャットの記録を返す。

    画面と同じく、先にモデルの一覧を取る（Open WebUI のサーバーのモデルの一覧が新しくなる）。
    """
    await client.list_models()
    user_id = str(uuid.uuid4())
    assistant_id = str(uuid.uuid4())
    now = int(time.time())
    user_message = {
        "id": user_id,
        "role": "user",
        "content": content,
        "parentId": None,
        "childrenIds": [assistant_id],
        "timestamp": now,
        "models": [model],
    }
    assistant_message = {
        "id": assistant_id,
        "role": "assistant",
        "content": "",
        "parentId": user_id,
        "childrenIds": [],
        "model": model,
        "modelName": model,
        "timestamp": now,
    }
    chat = await client.create_chat(
        {
            "title": "E2E",
            "models": [model],
            "messages": [user_message, assistant_message],
            "history": {"messages": {user_id: user_message, assistant_id: assistant_message}, "currentId": assistant_id},
            "params": {},
            "timestamp": now * 1000,
        }
    )
    chat_id = chat["id"]
    await client.chat_completions(
        {
            "model": model,
            "messages": [{"role": "user", "content": content}],
            "chat_id": chat_id,
            "id": assistant_id,
            "session_id": f"e2e-{uuid.uuid4()}",
            "tool_ids": [TOOL_ID],
            "stream": True,
            "params": {"function_calling": "native"},
            "features": {},
            "background_tasks": {"title_generation": False, "tags_generation": False, "follow_up_generation": False},
        }
    )
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        record = await client.get_chat(chat_id)
        message = record["chat"]["history"]["messages"].get(assistant_id, {})
        if message.get("done") and message.get("content"):
            return record
        await asyncio.sleep(2)
    raise AssertionError("アシスタントの応答が記録に入りませんでした")
