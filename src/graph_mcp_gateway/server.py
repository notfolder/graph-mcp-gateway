"""中継のサーバー（FastMCP）を組み立てる。"""

from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.server.providers.proxy import ProxyProvider

from .auth import build_auth_provider
from .config import Settings
from .relay import GraphTokenExchanger, RelayClientFactory, TransportFactory

SERVER_NAME = "graph-mcp-gateway"
TOOL_LIST_CACHE_SECONDS = 3600


def create_server(settings: Settings, transport_factory: TransportFactory | None = None) -> FastMCP:
    """設定から中継のサーバーを組み立てる。

    認証は OAuth プロキシ（AzureProvider）、エラーの詳細は伏せ、ツールの引数の定義は展開せず、
    サーバーの部品の失敗の扱いは「raise」にする（一覧が取れないときにツールが 0 個の一覧を返さない）。
    中継の部品（ProxyProvider、一覧のキャッシュ 3600 秒）を 1 つ載せる。
    受け口の違い（全部か探すか）は、設定の中継先と公開 URL だけで決まる。

    Args:
        settings: 中継の設定。
        transport_factory: 中継先へのトランスポートを作る関数（テストで差し替える）。None なら Streamable HTTP。

    Returns:
        組み立てた FastMCP のサーバー。
    """
    auth = build_auth_provider(settings)
    exchanger = GraphTokenExchanger(auth, settings.graph_scopes)
    factory = RelayClientFactory(settings.upstream_mcp_url, exchanger, transport_factory)
    server = FastMCP(
        SERVER_NAME,
        auth=auth,
        mask_error_details=True,
        dereference_schemas=False,
        providers=[ProxyProvider(factory, cache_ttl=TOOL_LIST_CACHE_SECONDS)],
    )
    server.provider_error_strategy = "raise"
    return server
