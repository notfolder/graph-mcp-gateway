# ms-365-mcp-server の E2E 関連の設定

| ファイル | 役割 |
|---|---|
| `mock.env` | mock モード。Graph への要求を Graph の模擬（Dev Proxy、`external/microsoft-graph/mock/`）に通す |
| `real.env` | real モード。本物の Graph に直接つなぐ |

- ms-365-mcp-server そのものは模擬しない。どちらのモードでも公式イメージを使う。
- 両方のモードで共通に渡す設定（組織用のモード、12 権限、外す 2 ツール、回数の制限と回路遮断器を外す、ログの水準など）は `../.env.example` の一覧のとおり。値は詳細設計で compose に書く。
- モードは、テスト実行コマンドに渡す環境ファイルと、docker compose のプロファイルで切り替える。
- 実装時・CI の必須ゴールは mock モードの全件通過。real モードは手動実行だけを必須にする。
