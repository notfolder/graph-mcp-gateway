# 言語モデルの E2E 関連の設定

| ファイル | 役割 |
|---|---|
| `mock.env` | mock モード。Open WebUI を言語モデルの模擬（`../mock/mock_llm.py`）につなぐ |
| `real.env` | real モード。値はプロジェクト直下の `.env` から読む（社外は Claude の API、社内は社内の接続先） |

- モードは、テスト実行コマンドに渡す環境ファイルと、docker compose のプロファイルで切り替える。compose の定義は詳細設計で作る。
- 実装時・CI の必須ゴールは mock モードの全件通過。real モード（社外・社内の 2 通り）は手動実行だけを必須にする。
- プロジェクトの `e2e/` からは、`external/language-model/mock/` をシンボリックリンクで参照し、リンクも Git で管理する。
