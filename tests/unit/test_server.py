"""サーバーの組み立て（create_server）と起動（main）の単体テスト。"""

from __future__ import annotations

from typing import Any

import pytest
from conftest import make_env
from fastmcp import FastMCP
from fastmcp.server.auth.providers.azure import AzureProvider
from fastmcp.server.providers.proxy import ProxyProvider

from graph_mcp_gateway import __main__ as main_module
from graph_mcp_gateway.config import Settings
from graph_mcp_gateway.server import create_server


def _proxy_providers(server: FastMCP) -> list[ProxyProvider]:
    return [p for p in server.providers if isinstance(p, ProxyProvider)]


def test_create_server_settings() -> None:
    server = create_server(Settings.from_env(make_env()))
    assert server.name == "graph-mcp-gateway"
    assert isinstance(server.auth, AzureProvider)
    assert server.provider_error_strategy == "raise"
    assert server._mask_error_details is True
    assert not any(type(m).__name__ == "DereferenceRefsMiddleware" for m in server.middleware)
    proxies = _proxy_providers(server)
    assert len(proxies) == 1
    assert proxies[0]._cache_ttl == 3600


@pytest.fixture
def run_calls(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """FastMCP.run の呼び出しを記録し、実際には待ち受けない。"""
    calls: list[dict[str, Any]] = []

    def fake_run(self: FastMCP, transport: str | None = None, show_banner: bool | None = None, **kwargs: Any) -> None:
        assert show_banner is False
        calls.append({"transport": transport, **kwargs})

    monkeypatch.setattr(FastMCP, "run", fake_run)
    return calls


def _set_env(monkeypatch: pytest.MonkeyPatch, env: dict[str, str]) -> None:
    for name in list(make_env()) + ["APP_STATELESS_HTTP"]:
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)


def test_main_runs_streamable_http_with_json(monkeypatch: pytest.MonkeyPatch, run_calls: list[dict[str, Any]]) -> None:
    _set_env(monkeypatch, make_env())
    main_module.main()
    assert run_calls == [{"transport": "http", "host": "0.0.0.0", "port": 8000, "path": "/mcp", "json_response": True}]


def test_main_passes_stateless_only_when_set(monkeypatch: pytest.MonkeyPatch, run_calls: list[dict[str, Any]]) -> None:
    _set_env(monkeypatch, make_env(APP_STATELESS_HTTP="true", APP_JWT_SIGNING_KEY="k"))
    main_module.main()
    assert run_calls[0]["stateless_http"] is True


def test_main_warns_when_stateless_without_shared_storage(
    monkeypatch: pytest.MonkeyPatch, run_calls: list[dict[str, Any]], caplog: pytest.LogCaptureFixture
) -> None:
    _set_env(monkeypatch, make_env(APP_STATELESS_HTTP="true"))
    main_module.main()
    assert "APP_STATELESS_HTTP" in caplog.text


def test_main_exits_1_on_settings_error(
    monkeypatch: pytest.MonkeyPatch, run_calls: list[dict[str, Any]], capsys: pytest.CaptureFixture[str]
) -> None:
    env = make_env(APP_TENANT_ID="common")
    _set_env(monkeypatch, env)
    with pytest.raises(SystemExit) as info:
        main_module.main()
    assert info.value.code == 1
    err = capsys.readouterr().err
    assert "APP_TENANT_ID" in err
    assert env["APP_CLIENT_SECRET"] not in err
    assert run_calls == []
