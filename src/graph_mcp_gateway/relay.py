"""Graph 用のトークンの交換と、ms-365-mcp-server への中継のクライアントの作成。"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Sequence

from fastmcp.client.transports import ClientTransport, StreamableHttpTransport
from fastmcp.server.auth.providers.azure import AzureProvider
from fastmcp.server.dependencies import get_access_token
from fastmcp.server.providers.proxy import ProxyClient

GRAPH_RESOURCE = "https://graph.microsoft.com"

TransportFactory = Callable[[str, dict[str, str]], ClientTransport]

_logger = logging.getLogger(__name__)
_AADSTS = re.compile(r"AADSTS\d+")


def _default_transport_factory(url: str, headers: dict[str, str]) -> ClientTransport:
    """ms-365-mcp-server への Streamable HTTP のトランスポートを作る。"""
    return StreamableHttpTransport(url, headers=headers)


class GraphTokenExchanger:
    """利用者の Entra のトークンを、OBO で Graph 用のトークンに替える。

    Args:
        provider: OAuth プロキシ（OBO の資格情報を作るのに使う）。
        graph_scopes: 要求する Graph の権限の一覧（`User.Read` などの短い名前）。
    """

    def __init__(self, provider: AzureProvider, graph_scopes: Sequence[str]) -> None:
        self._provider = provider
        self._scopes = [f"{GRAPH_RESOURCE}/{scope}" for scope in graph_scopes]

    async def exchange(self, entra_token: str | None) -> str:
        """利用者の Entra のトークンを Graph 用のトークンに替える。

        資格情報とトークンのキャッシュは azure-identity と FastMCP のメモリの上だけにある。

        Args:
            entra_token: 利用者の Entra のアクセストークン。

        Returns:
            Graph 用のアクセストークン。

        Raises:
            PermissionError: 利用者のトークンが無い場合（サーバー自身の権限で呼ぶ経路を作らない）。
            RuntimeError: OBO が失敗した場合。詳細（Entra のエラーの文言）は含めず、種類とエラーコードだけをログに出す。
        """
        if not entra_token:
            raise PermissionError("利用者のトークンがありません")
        credential = await self._provider.get_obo_credential(user_assertion=entra_token)
        try:
            token = await credential.get_token(*self._scopes)
        except Exception as exc:
            codes = sorted(set(_AADSTS.findall(str(exc))))
            _logger.warning("OBO に失敗しました: %s %s", type(exc).__name__, " ".join(codes) or "-")
            raise RuntimeError("Graph 用のトークンを取得できませんでした") from None
        return token.token


class RelayClientFactory:
    """要求ごとに、Graph 用のトークンを付けた ms-365-mcp-server への中継のクライアントを作る。

    `ProxyProvider` に、呼び出せるオブジェクトとして渡す。

    Args:
        upstream_url: 中継先の ms-365-mcp-server の URL。
        exchanger: Graph 用のトークンの交換。
        transport_factory: URL とヘッダーからトランスポートを作る関数（テストで差し替える）。
    """

    def __init__(
        self,
        upstream_url: str,
        exchanger: GraphTokenExchanger,
        transport_factory: TransportFactory | None = None,
    ) -> None:
        self._upstream_url = upstream_url
        self._exchanger = exchanger
        self._transport_factory = transport_factory or _default_transport_factory

    async def __call__(self) -> ProxyClient:
        """中継のクライアントを作る。

        現在の要求の利用者の Entra のトークンを Graph 用のトークンに替え、`Authorization` ヘッダーに設定した
        トランスポートを、受信したヘッダーを転送しない設定の `ProxyClient` で包んで返す。

        Returns:
            中継のクライアント。

        Raises:
            PermissionError: 利用者のトークンが無い場合。
        """
        access_token = get_access_token()
        graph_token = await self._exchanger.exchange(access_token.token if access_token else None)
        transport = self._transport_factory(self._upstream_url, {"Authorization": f"Bearer {graph_token}"})
        return ProxyClient(transport, forward_incoming_headers=False)
