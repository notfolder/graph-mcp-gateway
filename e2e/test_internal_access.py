"""社内ネットワーク（mock は compose の内部ネットワーク）から、両方の受け口のメタデータと Open WebUI に届く。"""

from __future__ import annotations

import httpx2
import pytest
from support.mcp_client import base_host, ca_bundle


@pytest.mark.parametrize(
    "path",
    [
        "/.well-known/oauth-protected-resource/full/mcp",
        "/.well-known/oauth-protected-resource/discovery/mcp",
        "/.well-known/oauth-authorization-server/full",
        "/.well-known/oauth-authorization-server/discovery",
    ],
)
def test_metadata_is_reachable(path: str) -> None:
    with httpx2.Client(verify=ca_bundle(), timeout=30) as http:
        response = http.get(f"https://{base_host()}{path}")
    assert response.status_code == 200
    body = response.json()
    endpoint = "full" if "/full" in path else "discovery"
    if "protected-resource" in path:
        assert body["resource"] == f"https://{base_host()}/{endpoint}/mcp"
    else:
        assert body["issuer"] == f"https://{base_host()}/{endpoint}"


def test_open_webui_health_is_reachable() -> None:
    with httpx2.Client(verify=ca_bundle(), timeout=30) as http:
        assert http.get(f"https://{base_host()}:8443/health").status_code == 200
