"""社外の確認（bash e2e/run.sh real-offsite）の下準備。

Open WebUI を初期設定し、確認用の参加者のアカウントを作る。探して使う受け口の認可は、人が手元のブラウザで
進める（Entra ID の模擬は entra.localhost:9443 で手元から届く）。
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from graph_mcp_gateway.openwebui_setup import add_open_webui_users, configure_open_webui  # noqa: E402
from support.mcp_client import base_host  # noqa: E402
from support.openwebui_flow import mcp_authenticated, new_client, open_webui_url  # noqa: E402

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
            mcp_url=f"https://{base_host()}/discovery/mcp",
        )
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = Path(tmp) / "participants.csv"
        csv_path.write_text(f"name,email,password\n社外の確認,{PARTICIPANT_EMAIL},{PARTICIPANT_PASSWORD}\n", encoding="utf-8")
        async with new_client() as admin:
            await add_open_webui_users(admin, admin_email=admin_email, admin_password=admin_password, csv_path=csv_path)
    async with new_client() as participant:
        await participant.signin(PARTICIPANT_EMAIL, PARTICIPANT_PASSWORD)
        assert await mcp_authenticated(participant) is False
    print(f"Open WebUI: {open_webui_url()}（証明書は e2e/.work/certs/ca.crt が発行。信頼させるか警告を承知で進める）")
    print(f"参加者: {PARTICIPANT_EMAIL} / {PARTICIPANT_PASSWORD}（M365 のツールの認可はまだ。ブラウザで進める）")
    print(f"MCP の受け口: https://{base_host()}/full/mcp と https://{base_host()}/discovery/mcp")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
