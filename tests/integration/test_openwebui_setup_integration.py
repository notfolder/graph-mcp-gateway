"""Open WebUI の初期設定の結合テスト（模擬のトランスポートの Open WebUI に対して実行する）。"""

from __future__ import annotations

import copy

from fake_openwebui import ADMIN_EMAIL, ADMIN_PASSWORD, FakeOpenWebUI
from openwebui_api import OpenWebUIClient

from graph_mcp_gateway.openwebui_setup import configure_open_webui


async def _configure(fake: FakeOpenWebUI) -> None:
    async with OpenWebUIClient("https://owui.test", transport=fake.transport()) as client:
        await configure_open_webui(
            client,
            admin_email=ADMIN_EMAIL,
            admin_password=ADMIN_PASSWORD,
            base_model_id="mock-model",
            mcp_url="https://gw.test/discovery/mcp",
            health_interval=0.0,
        )


async def test_configure_twice_gives_same_state() -> None:
    fake = FakeOpenWebUI()
    await _configure(fake)
    first = (copy.deepcopy(fake.models), copy.deepcopy(fake.tool_servers))
    await _configure(fake)
    assert (fake.models, fake.tool_servers) == first
    assert fake.register_calls == 1
