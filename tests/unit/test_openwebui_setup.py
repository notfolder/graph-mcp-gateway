"""Open WebUI の初期設定（configure_open_webui・add_open_webui_users・main）の単体テスト。"""

from __future__ import annotations

from pathlib import Path

import pytest
from fake_openwebui import ADMIN_EMAIL, ADMIN_PASSWORD, FakeOpenWebUI
from openwebui_api import OpenWebUIClient, OpenWebUIError

from graph_mcp_gateway import openwebui_setup
from graph_mcp_gateway.openwebui_setup import add_open_webui_users, configure_open_webui

MCP_URL = "https://gw.test/discovery/mcp"


async def _configure(fake: FakeOpenWebUI, **overrides: object) -> None:
    async with OpenWebUIClient("https://owui.test", transport=fake.transport()) as client:
        options: dict[str, object] = {
            "admin_email": ADMIN_EMAIL,
            "admin_password": ADMIN_PASSWORD,
            "base_model_id": "mock-model",
            "mcp_url": MCP_URL,
            "health_interval": 0.0,
        }
        options.update(overrides)
        await configure_open_webui(client, **options)  # type: ignore[arg-type]


async def test_registers_and_saves_connection_when_missing() -> None:
    fake = FakeOpenWebUI()
    await _configure(fake)
    assert fake.register_calls == 1
    [conn] = fake.tool_servers
    assert conn["type"] == "mcp"
    assert conn["url"] == MCP_URL
    assert conn["path"] == ""
    assert conn["auth_type"] == "oauth_2.1"
    assert conn["config"] == {
        "enable": True,
        "access_grants": [{"principal_type": "user", "principal_id": "*", "permission": "read"}],
    }
    assert conn["info"]["id"] == "m365"
    assert conn["info"]["oauth_client_info"] == "encrypted-m365-1"


async def test_does_nothing_when_connection_exists() -> None:
    fake = FakeOpenWebUI(tool_servers=[{"type": "mcp", "url": MCP_URL, "info": {"id": "m365"}}])
    await _configure(fake)
    assert fake.register_calls == 0
    assert not any(r.method == "POST" and r.url.path == "/api/v1/configs/tool_servers" for r in fake.requests)


async def test_appends_to_existing_connections() -> None:
    other = {"type": "openapi", "url": "https://other.test", "info": {"id": "other"}}
    fake = FakeOpenWebUI(tool_servers=[other])
    await _configure(fake)
    assert [c["info"]["id"] for c in fake.tool_servers] == ["other", "m365"]
    assert fake.tool_servers[0] == other


async def test_creates_models_shared_with_everyone_only_when_missing() -> None:
    fake = FakeOpenWebUI()
    await _configure(fake)
    everyone = [{"principal_type": "user", "principal_id": "*", "permission": "read"}]
    preset = [m for m in fake.models if m["id"] == "poc-assistant"]
    assert len(preset) == 1
    assert preset[0]["base_model_id"] == "mock-model"
    assert preset[0]["access_grants"] == everyone
    base = [m for m in fake.models if m["id"] == "mock-model" and "access_grants" in m]
    assert len(base) == 1
    assert base[0]["base_model_id"] is None
    assert base[0]["access_grants"] == everyone
    assert sum(r.url.path == "/api/v1/models/create" for r in fake.requests) == 2

    await _configure(fake)
    assert sum(r.url.path == "/api/v1/models/create" for r in fake.requests) == 2


async def test_preset_model_does_not_get_builtin_tools() -> None:
    fake = FakeOpenWebUI()
    await _configure(fake)
    preset = next(m for m in fake.models if m["id"] == "poc-assistant")
    assert preset["meta"]["capabilities"] == {"builtin_tools": False}
    base = next(m for m in fake.models if m["id"] == "mock-model" and "access_grants" in m)
    assert base["meta"]["capabilities"] == {"builtin_tools": False}


async def test_default_model_is_preset_keeping_other_model_settings() -> None:
    fake = FakeOpenWebUI()
    await _configure(fake)
    assert fake.models_config["DEFAULT_MODELS"] == "poc-assistant"
    assert fake.models_config["MODEL_ORDER_LIST"] == ["mock-model"]
    posts = sum(r.method == "POST" and r.url.path == "/api/v1/configs/models" for r in fake.requests)
    assert posts == 1

    await _configure(fake)
    assert sum(r.method == "POST" and r.url.path == "/api/v1/configs/models" for r in fake.requests) == 1


async def test_existing_preset_with_builtin_tools_is_corrected_keeping_other_settings() -> None:
    existing = {
        "id": "poc-assistant",
        "base_model_id": "mock-model",
        "name": "PoC アシスタント",
        "meta": {"description": "既存", "capabilities": {"vision": True}},
        "params": {"temperature": 0.2},
        "access_grants": [],
    }
    fake = FakeOpenWebUI(models=[{"id": "mock-model"}, existing])
    await _configure(fake)
    preset = next(m for m in fake.models if m["id"] == "poc-assistant")
    assert preset["meta"]["capabilities"] == {"vision": True, "builtin_tools": False}
    assert preset["meta"]["description"] == "既存"
    assert preset["params"] == {"temperature": 0.2}
    assert sum(r.url.path == "/api/v1/models/model/update" for r in fake.requests) == 1

    await _configure(fake)
    assert sum(r.url.path == "/api/v1/models/model/update" for r in fake.requests) == 1


async def test_refreshes_model_list_after_setup() -> None:
    fake = FakeOpenWebUI()
    await _configure(fake)
    paths = [r.url.path for r in fake.requests]
    assert "/api/models" in paths[paths.index("/api/v1/models/create"):]


async def test_waits_for_health() -> None:
    fake = FakeOpenWebUI(health_failures=2)
    await _configure(fake)
    assert sum(r.url.path == "/health" for r in fake.requests) == 3


async def test_gives_up_waiting_for_health() -> None:
    fake = FakeOpenWebUI(health_failures=1000)
    with pytest.raises(OpenWebUIError):
        await _configure(fake, health_timeout=0.0)


async def test_rejects_non_https_mcp_url() -> None:
    with pytest.raises(ValueError):
        await _configure(FakeOpenWebUI(), mcp_url="http://gw.test/discovery/mcp")


def _write_csv(tmp_path: Path, rows: list[str]) -> Path:
    path = tmp_path / "participants.csv"
    path.write_text("name,email,password\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return path


async def test_add_users_creates_users_and_skips_existing(tmp_path: Path) -> None:
    fake = FakeOpenWebUI()
    fake.users["bob@example.test"] = {"name": "Bob", "password": "x", "role": "user"}
    path = _write_csv(tmp_path, ["Alice,alice@example.test,alice-initial-pass", "Bob,bob@example.test,bob-initial-pass"])
    lines: list[str] = []
    async with OpenWebUIClient("https://owui.test", transport=fake.transport()) as client:
        await add_open_webui_users(
            client, admin_email=ADMIN_EMAIL, admin_password=ADMIN_PASSWORD, csv_path=path, out=lines.append
        )
    assert fake.users["alice@example.test"]["role"] == "user"
    assert fake.users["bob@example.test"]["password"] == "x"
    assert any("alice@example.test" in line and "作成" in line for line in lines)
    assert any("bob@example.test" in line and "飛ばし" in line for line in lines)
    assert not any("initial-pass" in line for line in lines)


async def test_add_users_rejects_csv_without_columns(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("name,mail\nAlice,alice@example.test\n", encoding="utf-8")
    async with OpenWebUIClient("https://owui.test", transport=FakeOpenWebUI().transport()) as client:
        with pytest.raises(ValueError):
            await add_open_webui_users(client, admin_email=ADMIN_EMAIL, admin_password=ADMIN_PASSWORD, csv_path=path)


def _env() -> dict[str, str]:
    return {
        "OPENWEBUI_URL": "https://owui.test",
        "WEBUI_ADMIN_EMAIL": ADMIN_EMAIL,
        "WEBUI_ADMIN_PASSWORD": ADMIN_PASSWORD,
        "OPENWEBUI_CA_BUNDLE_PATH": "/certs/ca-bundle.pem",
        "OPENWEBUI_LLM_MODEL": "mock-model",
        "OPENWEBUI_MCP_URL": MCP_URL,
    }


@pytest.fixture
def fake_client(monkeypatch: pytest.MonkeyPatch) -> FakeOpenWebUI:
    """main が作るクライアントを、模擬につながるものに差し替える。"""
    fake = FakeOpenWebUI()

    def make_client(base_url: str, **_: object) -> OpenWebUIClient:
        return OpenWebUIClient(base_url, transport=fake.transport())

    monkeypatch.setattr(openwebui_setup, "OpenWebUIClient", make_client)
    return fake


def test_main_configure(fake_client: FakeOpenWebUI) -> None:
    openwebui_setup.main(["configure"], _env())
    assert fake_client.tool_servers[0]["info"]["id"] == "m365"


def test_main_add_users(fake_client: FakeOpenWebUI, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = _write_csv(tmp_path, ["Carol,carol@example.test,carol-initial-pass"])
    openwebui_setup.main(["add-users", str(path)], _env())
    out = capsys.readouterr().out
    assert "carol@example.test" in out
    assert "carol-initial-pass" not in out


def test_main_exits_1_with_status_and_detail(fake_client: FakeOpenWebUI, capsys: pytest.CaptureFixture[str]) -> None:
    env = _env()
    env["WEBUI_ADMIN_PASSWORD"] = "wrong-password"
    with pytest.raises(SystemExit) as info:
        openwebui_setup.main(["configure"], env)
    assert info.value.code == 1
    err = capsys.readouterr().err
    assert "400" in err
    assert "incorrect" in err
    assert "wrong-password" not in err


@pytest.mark.parametrize("argv", [[], ["unknown"], ["add-users"]])
def test_main_exits_1_on_bad_arguments(fake_client: FakeOpenWebUI, argv: list[str]) -> None:
    with pytest.raises(SystemExit) as info:
        openwebui_setup.main(argv, _env())
    assert info.value.code == 1


def test_main_exits_1_on_missing_env(fake_client: FakeOpenWebUI, capsys: pytest.CaptureFixture[str]) -> None:
    env = _env()
    del env["OPENWEBUI_MCP_URL"]
    with pytest.raises(SystemExit) as info:
        openwebui_setup.main(["configure"], env)
    assert info.value.code == 1
    assert "OPENWEBUI_MCP_URL" in capsys.readouterr().err
