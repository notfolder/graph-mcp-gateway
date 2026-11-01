"""Open WebUI からの利用を自動で確かめる（mock モード、言語モデルの模擬）。"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path

import pytest
from openwebui_api import OpenWebUIError
from support.mcp_client import work_dir
from support.openwebui_flow import CONNECTION_KEY, authorize_mcp, mcp_authenticated, new_client, send_and_wait

from graph_mcp_gateway.openwebui_setup import CONNECTION_ID, MODEL_ID, add_open_webui_users, configure_open_webui

pytestmark = pytest.mark.mock_only

PARTICIPANT_EMAIL = "participant@example.test"
PARTICIPANT_PASSWORD = "participant-initial-password"


def _admin() -> tuple[str, str]:
    return os.environ["WEBUI_ADMIN_EMAIL"], os.environ["WEBUI_ADMIN_PASSWORD"]


async def _configure() -> None:
    email, password = _admin()
    async with new_client() as client:
        await configure_open_webui(
            client,
            admin_email=email,
            admin_password=password,
            base_model_id=os.environ["OPENWEBUI_LLM_MODEL"],
            mcp_url="https://gateway/discovery/mcp",
        )


async def _snapshot() -> tuple[list, list]:
    email, password = _admin()
    async with new_client() as client:
        await client.signin(email, password)
        servers = (await client.get_tool_servers())["TOOL_SERVER_CONNECTIONS"]
        models = [m for m in (await client.list_models())["data"] if m["id"] == MODEL_ID]
    for model in models:
        model.pop("updated_at", None)
    return copy.deepcopy(servers), [m["id"] for m in models]


def _llm_requests() -> list[dict]:
    path = work_dir() / "llm" / "llm-requests.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


async def test_open_webui_end_to_end(tmp_path: Path) -> None:
    await _configure()
    first = await _snapshot()
    await _configure()
    assert await _snapshot() == first
    servers, models = first
    async with new_client() as admin:
        await admin.signin(*_admin())
        assert (await admin.get_model(MODEL_ID))["meta"]["capabilities"].get("builtin_tools") is False
        base = os.environ["OPENWEBUI_LLM_MODEL"]
        assert (await admin.get_model(base))["meta"]["capabilities"].get("builtin_tools") is False
        assert (await admin.get_models_config())["DEFAULT_MODELS"] == MODEL_ID
    assert [s["info"]["id"] for s in servers] == [CONNECTION_ID]
    assert models == [MODEL_ID]

    csv_path = tmp_path / "participants.csv"
    csv_path.write_text(f"name,email,password\nPoC 参加者,{PARTICIPANT_EMAIL},{PARTICIPANT_PASSWORD}\n", encoding="utf-8")
    email, password = _admin()
    async with new_client() as admin:
        await add_open_webui_users(admin, admin_email=email, admin_password=password, csv_path=csv_path, out=print)

    async with new_client() as anonymous:
        with pytest.raises(OpenWebUIError) as info:
            await anonymous.signup("self signup", "self@example.test", "self-password-123")
        assert info.value.status == 403

    before = len(_llm_requests())
    async with new_client() as participant:
        await participant.signin(PARTICIPANT_EMAIL, PARTICIPANT_PASSWORD)
        if await mcp_authenticated(participant):
            await participant.delete_oauth_session(CONNECTION_KEY)
        assert await mcp_authenticated(participant) is False
        await authorize_mcp(participant, "alice")
        assert await mcp_authenticated(participant) is True

        searched = await send_and_wait(participant, MODEL_ID, 'CALL search-tools {"query": "calendar"}')
        executed = await send_and_wait(participant, MODEL_ID, 'CALL execute-tool {"tool_name": "get-current-user"}')

    for record in (searched, executed):
        text = json.dumps(record, ensure_ascii=False)
        assert "TOOL_RESULT:" in text
    requests = _llm_requests()[before:]
    assert requests and all(r["tool_count"] == 3 for r in requests), [r["tool_count"] for r in requests]
    tool_results = [text for r in requests for text in r.get("tool_results", [])]
    assert any("found" in text for text in tool_results)
    assert any("Alice Mock" in text for text in tool_results)
