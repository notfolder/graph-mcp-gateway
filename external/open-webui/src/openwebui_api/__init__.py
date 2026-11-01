"""Open WebUI の API の連携ライブラリ（薄いラッパー）。

公開インターフェース:
    OpenWebUIClient: Open WebUI の各エンドポイントに 1 対 1 で対応するメソッドを持つ非同期クライアント。
    OpenWebUIError: Open WebUI がエラーを返したときの例外（状態コード、detail）。
"""

from .client import OpenWebUIClient, OpenWebUIError

__all__ = ["OpenWebUIClient", "OpenWebUIError"]
