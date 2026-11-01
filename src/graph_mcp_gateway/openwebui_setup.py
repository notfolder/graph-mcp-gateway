"""PoC 専用の Open WebUI の初期設定と、参加者のアカウントの作成（`python -m graph_mcp_gateway.openwebui_setup`）。"""

from __future__ import annotations

import asyncio
import csv
import os
import sys
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import httpx2
from openwebui_api import OpenWebUIClient, OpenWebUIError

CONNECTION_ID = "m365"
CONNECTION_NAME = "Microsoft 365"
MODEL_ID = "poc-assistant"
MODEL_NAME = "PoC アシスタント"
EVERYONE_READ = [{"principal_type": "user", "principal_id": "*", "permission": "read"}]
HEALTH_TIMEOUT_SECONDS = 180.0
HEALTH_INTERVAL_SECONDS = 3.0

Printer = Callable[[str], None]


async def _wait_for_health(client: OpenWebUIClient, timeout: float, interval: float) -> None:
    """`/health` が 200 になるまで待つ。"""
    deadline = time.monotonic() + timeout
    while True:
        try:
            await client.health()
            return
        except (OpenWebUIError, httpx2.HTTPError):
            if time.monotonic() >= deadline:
                raise
        await asyncio.sleep(interval)


async def _ensure_model(client: OpenWebUIClient, model: dict[str, Any]) -> None:
    """モデルの設定が無ければ作る（あれば何もしない）。"""
    try:
        await client.get_model(model["id"])
    except OpenWebUIError as exc:
        if exc.status != 404:
            raise
        await client.create_model(model)


async def configure_open_webui(
    client: OpenWebUIClient,
    *,
    admin_email: str,
    admin_password: str,
    base_model_id: str,
    mcp_url: str,
    health_timeout: float = HEALTH_TIMEOUT_SECONDS,
    health_interval: float = HEALTH_INTERVAL_SECONDS,
) -> None:
    """Open WebUI を PoC 用に設定する。何度実行しても同じ状態になる。

    `/health` が 200 になるまで待ち、管理者でログインする。言語モデルを基にしたモデルの設定（ID `poc-assistant`）が
    無ければ作って利用者全員に read で公開する。Open WebUI は設定の無い元のモデルを管理者だけに見せ、公開したモデルの
    元としても使わせないので、元のモデルの設定も無ければ作って利用者全員に read で公開する。最後にモデルの一覧を取り、
    Open WebUI のサーバーのモデルの一覧を新しくする。ツールサーバーの接続先 `m365` が無ければ、探して使う受け口に DCR で
    登録し、既存の接続先の一覧に足して保存し、利用者全員に公開する。

    Args:
        client: Open WebUI のクライアント（未ログインでよい）。
        admin_email: 管理者のメールアドレス。
        admin_password: 管理者のパスワード。
        base_model_id: 公開するモデルの元のモデル名。
        mcp_url: 探して使う受け口の URL（https）。
        health_timeout: `/health` を待つ最大の秒数。
        health_interval: `/health` を確かめる間隔の秒数。

    Raises:
        ValueError: 受け口の URL が https でない場合。
        OpenWebUIError: Open WebUI がエラーを返した場合。
    """
    if not mcp_url.startswith("https://"):
        raise ValueError("OPENWEBUI_MCP_URL は https:// で始まる必要があります")

    await _wait_for_health(client, health_timeout, health_interval)
    await client.signin(admin_email, admin_password)

    await _ensure_model(
        client,
        {
            "id": base_model_id,
            "base_model_id": None,
            "name": base_model_id,
            "meta": {"description": "PoC の言語モデル", "capabilities": {}},
            "params": {},
            "access_grants": EVERYONE_READ,
        },
    )
    await _ensure_model(
        client,
        {
            "id": MODEL_ID,
            "base_model_id": base_model_id,
            "name": MODEL_NAME,
            "meta": {"description": "Microsoft 365 のツールを探して使う PoC 用のモデル", "capabilities": {}},
            "params": {},
            "access_grants": EVERYONE_READ,
        },
    )
    await client.list_models()

    connections: list[dict[str, Any]] = list((await client.get_tool_servers()).get("TOOL_SERVER_CONNECTIONS", []))
    if any((conn.get("info") or {}).get("id") == CONNECTION_ID for conn in connections):
        return

    registered = await client.register_oauth_client(mcp_url, CONNECTION_ID)
    connections.append(
        {
            "type": "mcp",
            "url": mcp_url,
            "path": "",
            "auth_type": "oauth_2.1",
            "key": "",
            "config": {"enable": True, "access_grants": EVERYONE_READ},
            "info": {
                "id": CONNECTION_ID,
                "name": CONNECTION_NAME,
                "description": "社内共有 M365 MCP サーバー（探して使う受け口）",
                "oauth_client_info": registered.get("oauth_client_info"),
            },
        }
    )
    await client.set_tool_servers(connections)


async def add_open_webui_users(
    client: OpenWebUIClient,
    *,
    admin_email: str,
    admin_password: str,
    csv_path: Path,
    out: Printer = print,
) -> None:
    """参加者の CSV（名前・メールアドレス・初期のパスワード、ヘッダー行あり）から、役割 `user` のアカウントを作る。

    同じメールアドレスが既にあれば飛ばして、その旨を表示する。パスワードは表示しない。

    Args:
        client: Open WebUI のクライアント（未ログインでよい）。
        admin_email: 管理者のメールアドレス。
        admin_password: 管理者のパスワード。
        csv_path: 参加者の CSV のパス（列名 `name`・`email`・`password`）。
        out: 結果の表示先。

    Raises:
        ValueError: CSV の列が足りない場合。
        OpenWebUIError: 既存のメールアドレス以外の理由で Open WebUI がエラーを返した場合。
    """
    with csv_path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    if rows and not {"name", "email", "password"} <= set(rows[0]):
        raise ValueError("CSV には name・email・password の列が必要です")

    await client.signin(admin_email, admin_password)
    for row in rows:
        email = row["email"].strip()
        try:
            await client.add_user(row["name"].strip(), email, row["password"], role="user")
        except OpenWebUIError as exc:
            if exc.status == 400 and "already" in exc.detail.lower():
                out(f"既にあるため飛ばしました: {email}")
                continue
            raise
        out(f"作成しました: {email}")


def _required_env(env: Mapping[str, str], names: list[str]) -> dict[str, str]:
    values = {name: (env.get(name) or "").strip() for name in names}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise ValueError("設定に誤りがあります: " + ", ".join(missing))
    return values


async def _run(argv: list[str], env: Mapping[str, str]) -> None:
    if not argv or argv[0] not in ("configure", "add-users") or (argv[0] == "add-users" and len(argv) != 2):
        raise ValueError("使い方: openwebui_setup configure | add-users <CSV のパス>")
    common = ["OPENWEBUI_URL", "WEBUI_ADMIN_EMAIL", "WEBUI_ADMIN_PASSWORD", "OPENWEBUI_CA_BUNDLE_PATH"]
    if argv[0] == "configure":
        values = _required_env(env, [*common, "OPENWEBUI_LLM_MODEL", "OPENWEBUI_MCP_URL"])
    else:
        values = _required_env(env, common)
    async with OpenWebUIClient(values["OPENWEBUI_URL"], verify=values["OPENWEBUI_CA_BUNDLE_PATH"]) as client:
        if argv[0] == "configure":
            await configure_open_webui(
                client,
                admin_email=values["WEBUI_ADMIN_EMAIL"],
                admin_password=values["WEBUI_ADMIN_PASSWORD"],
                base_model_id=values["OPENWEBUI_LLM_MODEL"],
                mcp_url=values["OPENWEBUI_MCP_URL"],
            )
            print("Open WebUI の初期設定が終わりました")
        else:
            await add_open_webui_users(
                client,
                admin_email=values["WEBUI_ADMIN_EMAIL"],
                admin_password=values["WEBUI_ADMIN_PASSWORD"],
                csv_path=Path(argv[1]),
            )


def main(argv: list[str] | None = None, env: Mapping[str, str] | None = None) -> None:
    """引数の `configure` か `add-users <CSV のパス>` で初期設定か参加者の作成を行う。

    設定は環境変数から読む。失敗は理由（状態コードと `detail`）を標準エラーに出し、終了コード 1 で終わる。

    Args:
        argv: コマンドの引数。None ならコマンドラインの引数。
        env: 環境変数の対応表。None なら OS の環境変数。
    """
    try:
        asyncio.run(_run(sys.argv[1:] if argv is None else argv, os.environ if env is None else env))
    except OpenWebUIError as exc:
        print(f"Open WebUI がエラーを返しました: {exc.status} {exc.detail}", file=sys.stderr)
        sys.exit(1)
    except (ValueError, OSError, httpx2.HTTPError) as exc:
        print(f"失敗しました: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
