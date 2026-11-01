"""中継を起動する（`python -m graph_mcp_gateway`）。"""

from __future__ import annotations

import logging
import sys
from typing import Any

from .config import Settings
from .server import create_server

HOST = "0.0.0.0"
PORT = 8000
MCP_PATH = "/mcp"

_logger = logging.getLogger("graph_mcp_gateway")


def main() -> None:
    """設定を読み、中継のサーバーを Streamable HTTP で起動する。

    設定に誤りがあれば、項目名だけを標準エラーに出して終了コード 1 で終わる。
    0.0.0.0 の 8000 番、パス `/mcp` で待ち受け、応答は JSON にする。
    MCP のセッションを持たない動作は、設定されたときだけ有効にする。
    起動時の案内の表示（外部への版の確認を伴う）は出さない。
    """
    try:
        settings = Settings.from_env()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    if settings.stateless_http and (settings.jwt_signing_key is None or settings.storage_redis_url is None):
        _logger.warning(
            "APP_STATELESS_HTTP=true ですが APP_JWT_SIGNING_KEY か APP_STORAGE_REDIS_URL がありません。"
            "台数を増やす構成では両方を設定してください"
        )

    server = create_server(settings)
    run_options: dict[str, Any] = {"host": HOST, "port": PORT, "path": MCP_PATH, "json_response": True}
    if settings.stateless_http is not None:
        run_options["stateless_http"] = settings.stateless_http
    server.run(transport="http", show_banner=False, **run_options)


if __name__ == "__main__":
    main()
