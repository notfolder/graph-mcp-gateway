"""社外の確認（bash e2e/run.sh real-offsite）の下準備。

Open WebUI を初期設定し、確認用の参加者のアカウントを作って、探して使う受け口の認可まで済ませる
（Entra ID の模擬はブラウザから届かないので、認可は HTTP の要求で進める）。
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from graph_mcp_gateway.openwebui_setup import add_open_webui_users, configure_open_webui  # noqa: E402
from support.openwebui_flow import CONNECTION_KEY, authorize_mcp, mcp_authenticated, new_client  # noqa: E402

PARTICIPANT_EMAIL = "offsite@example.test"
PARTICIPANT_PASSWORD = "offsite-check-password"


async def main() -> int:
    """初期設定・参加者の作成・認可を行い、ログインの情報を表示する。"""
    admin_email = os.environ["WEBUI_ADMIN_EMAIL"]
    admin_password = os.environ["WEBUI_ADMIN_PASSWORD"]
    async with new_client() as admin:
        await configure_open_webui(
            admin,
            admin_email=admin_email,
            admin_password=admin_password,
            base_model_id=os.environ["OPENWEBUI_LLM_MODEL"],
            mcp_url="https://gateway/discovery/mcp",
        )
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = Path(tmp) / "participants.csv"
        csv_path.write_text(f"name,email,password\n社外の確認,{PARTICIPANT_EMAIL},{PARTICIPANT_PASSWORD}\n", encoding="utf-8")
        async with new_client() as admin:
            await add_open_webui_users(admin, admin_email=admin_email, admin_password=admin_password, csv_path=csv_path)
    async with new_client() as participant:
        await participant.signin(PARTICIPANT_EMAIL, PARTICIPANT_PASSWORD)
        if not await mcp_authenticated(participant):
            await authorize_mcp(participant, "alice")
        assert await mcp_authenticated(participant), CONNECTION_KEY
    print("Open WebUI: https://localhost:8443（証明書は e2e/.work/certs/ca.crt が発行。信頼させるか警告を承知で進める）")
    print(f"参加者: {PARTICIPANT_EMAIL} / {PARTICIPANT_PASSWORD}（模擬の Entra ID の alice として認可済み）")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
