"""全部の手順の後に、保存したログとテスト用クライアントの記録を調べる（e2e/run.sh の手順 9）。

- Entra ID（模擬）が発行した JWT と、宛先が Graph の JWT が、AI ツールの側（記録）と本システムのログに無い
- 送ったメールの本文・検索の語・利用者名が、本システムのログに無い
- Dev Proxy の記録で、Graph の再試行の回数と、件数の上限が送られたことを確かめる
"""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path

import pytest
from support.mcp_client import work_dir

from test_representative_tools import MAIL_BODY_MARKER, SEARCH_MARKER

pytestmark = [pytest.mark.final, pytest.mark.mock_only]

SYSTEM_SERVICES = ("gateway", "relay-full", "relay-discovery", "ms365-full", "ms365-discovery", "open-webui")
JWT = re.compile(r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*")
GRAPH_AUDIENCES = {"00000003-0000-0000-c000-000000000000", "https://graph.microsoft.com"}
PERSONAL = [MAIL_BODY_MARKER, SEARCH_MARKER, "Alice Mock", "alice@contoso.test", "Bob Mock", "bob@contoso.test"]


def _logs() -> Path:
    return work_dir() / "logs"


def _system_log_text() -> str:
    parts = []
    for path in sorted(_logs().glob("*-compose.log")):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            service = line.split("|", 1)[0].strip().rsplit("-", 1)[0]
            if service in SYSTEM_SERVICES:
                parts.append(line)
    for path in sorted(_logs().glob("*-ms365-*/**/*")):
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts)


def _records_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted((work_dir() / "records").glob("*.json*")))


def _claims(token: str) -> dict:
    payload = token.split(".")[1]
    try:
        return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except ValueError:
        return {}


def _leaked(text: str) -> list[dict]:
    found = []
    for token in set(JWT.findall(text)):
        claims = _claims(token)
        issuer = str(claims.get("iss", ""))
        audience = claims.get("aud")
        audiences = set(audience) if isinstance(audience, list) else {audience}
        if "mock-entra" in issuer or "login.microsoftonline.com" in issuer or audiences & GRAPH_AUDIENCES:
            found.append({"iss": issuer, "aud": audience})
    return found


def test_logs_were_saved() -> None:
    assert list(_logs().glob("phase4-compose.log"))
    assert list((work_dir() / "records").glob("*.json"))


def test_no_entra_or_graph_token_on_ai_tool_side() -> None:
    assert _leaked(_records_text()) == []


def test_no_entra_or_graph_token_in_system_logs() -> None:
    assert _leaked(_system_log_text()) == []


@pytest.mark.parametrize("value", PERSONAL)
def test_no_personal_data_in_system_logs(value: str) -> None:
    assert value not in _system_log_text()


def _devproxy_lines(phase: str) -> list[str]:
    path = _logs() / f"{phase}-compose.log"
    return [line for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.startswith("devproxy-")]


def _count(lines: list[str], fragment: str) -> int:
    return sum(fragment in line for line in lines)


def test_graph_retry_counts_in_devproxy_record() -> None:
    lines = _devproxy_lines("phase4")
    get = "GET https://graph.microsoft.com/v1.0/me/messages/"
    assert _count(lines, get + "mock-503") == 8
    assert _count(lines, get + "mock-429-always") == 8
    assert _count(lines, get + "mock-429-then-ok") == 2
    assert _count(lines, "MockResponsePlugin: 503 https://graph.microsoft.com/v1.0/me/sendMail") == 2


def test_top_limit_was_sent() -> None:
    phase4 = _devproxy_lines("phase4")
    assert any(re.search(r"/me/messages\?.*\$top=50(&|$)", line) for line in phase4)
    assert not any("$top=100" in line for line in phase4)
    phase5 = _devproxy_lines("phase5")
    assert any(re.search(r"/me/messages\?.*\$top=5(&|$)", line) for line in phase5)
