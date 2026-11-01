"""台数を増やした構成で、4 つの中継と 4 つの ms-365-mcp-server のすべてに要求が届いた（ホストから記録を調べる）。"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.multi, pytest.mark.mock_only]

MIN_RX_BYTES = 2000


def _work() -> Path:
    return Path(os.environ.get("E2E_WORK_DIR", "e2e/.work"))


@pytest.mark.parametrize("container", ["relay-full-1", "relay-full-2", "relay-discovery-1", "relay-discovery-2"])
def test_every_relay_received_mcp_requests(container: str) -> None:
    log = (_work() / "logs" / "phase7-compose.log").read_text(encoding="utf-8", errors="replace")
    lines = [line for line in log.splitlines() if line.startswith(container + " ") and '"POST /mcp' in line]
    assert lines, f"{container} に MCP の要求が届いていません"


def _rx(path: Path) -> dict[str, int]:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        index, _, value = line.partition(" ")
        if re.fullmatch(r"\d+", value.strip()):
            values[index] = int(value)
    return values


@pytest.mark.parametrize("service", ["full", "discovery"])
def test_every_ms365_replica_received_requests(service: str) -> None:
    before = _rx(_work() / "state" / f"rx-before-{service}.txt")
    after = _rx(_work() / "state" / f"rx-after-{service}.txt")
    assert len(after) == 2, after
    for index, value in after.items():
        assert value - before.get(index, 0) >= MIN_RX_BYTES, f"ms365-{service} の {index} 台目に要求が届いていません"
