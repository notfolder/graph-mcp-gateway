"""Microsoft Graph v1.0 の連携ライブラリ（薄いラッパー）。

公開インターフェース:
    GraphClient: Graph の各エンドポイントに 1 対 1 で対応するメソッドを持つ非同期クライアント。
    GraphError: Graph がエラーを返したときの例外（状態コード、error.code、Retry-After）。
    GRAPH_BASE_URL: Graph v1.0 のベース URL。
"""

from .client import GRAPH_BASE_URL, GraphClient, GraphError

__all__ = ["GRAPH_BASE_URL", "GraphClient", "GraphError"]
