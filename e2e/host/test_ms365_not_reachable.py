"""ms-365-mcp-server に外から届かない（ホストから試す）。"""

from __future__ import annotations

import os
import socket

import httpx2
import pytest

pytestmark = pytest.mark.mock_only


def _ca() -> str:
    return os.environ.get("E2E_CA_BUNDLE", "e2e/.work/certs/e2e-bundle.pem")


@pytest.mark.parametrize("port", [3000])
def test_ms365_port_is_not_published(port: int) -> None:
    with pytest.raises(OSError):
        socket.create_connection(("127.0.0.1", port), timeout=3).close()


@pytest.mark.parametrize(
    "path",
    ["/register", "/authorize", "/token", "/mcp", "/revoke", "/.well-known/oauth-authorization-server", "/full/../register"],
)
def test_oauth_paths_outside_relay_are_not_reachable(path: str) -> None:
    with httpx2.Client(verify=_ca(), timeout=10) as http:
        response = http.request("POST" if path in ("/token", "/mcp", "/register") else "GET", f"https://localhost{path}")
    assert response.status_code == 404
