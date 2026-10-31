# Microsoft Graph の E2E 関連の設定

| ファイル | 役割 |
|---|---|
| `mock.env` | mock モードの環境変数（Graph への要求を Dev Proxy に通す） |
| `real.env` | real モードの環境変数（本物の Graph。プロキシなし） |

- モードは、テスト実行コマンドに渡す環境ファイルと、docker compose のプロファイルで切り替える。compose の定義は詳細設計で作る。
- 実装時・CI の必須ゴールは mock モードの全件通過。real モードは手動実行だけを必須にする。
- プロジェクトの `e2e/` からは、`external/microsoft-graph/mock/` をシンボリックリンクで参照し、リンクも Git で管理する。
