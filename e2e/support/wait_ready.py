"""E2E の実行役のコンテナから、全サービスの起動を待つ（Open WebUI は最大 3 分）。

両方の受け口の保護リソースのメタデータ・認可サーバーのメタデータと、Open WebUI の `/health` が 200 になるまで待つ。
"""

from __future__ import annotations

import os
import sys
import time

import httpx2

HOST = os.environ.get("E2E_BASE_HOST", "gateway")
CA = os.environ.get("E2E_CA_BUNDLE", "/certs/e2e-bundle.pem")
URLS = [
    f"https://{HOST}/.well-known/oauth-protected-resource/full/mcp",
    f"https://{HOST}/.well-known/oauth-protected-resource/discovery/mcp",
    f"https://{HOST}/.well-known/oauth-authorization-server/full",
    f"https://{HOST}/.well-known/oauth-authorization-server/discovery",
    f"https://{HOST}:8443/health",
]
TIMEOUT_SECONDS = 300


def main() -> int:
    """全部の URL が 200 になるまで待つ。間に合わなければ 1 を返す。"""
    deadline = time.monotonic() + TIMEOUT_SECONDS
    pending = list(URLS)
    with httpx2.Client(verify=CA, timeout=5) as client:
        while pending and time.monotonic() < deadline:
            for url in list(pending):
                try:
                    if client.get(url).status_code == 200:
                        pending.remove(url)
                        print(f"起動を確認しました: {url}", flush=True)
                except httpx2.HTTPError:
                    pass
            if pending:
                time.sleep(3)
    if pending:
        print("起動を確認できませんでした: " + ", ".join(pending), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
