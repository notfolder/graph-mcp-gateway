# Open WebUI の E2E 関連の設定

| ファイル | 役割 |
|---|---|
| `mock.env` | mock モード。言語モデル・Entra ID・Graph は模擬。手順は `../docs/research.md` 6 章のとおり自動で行う |
| `real.env` | real モード（社外：模擬の Entra ID・Graph と Claude の API、社内：PoC 用テナントと社内の言語モデルの接続先）。手で確かめる |

- Open WebUI そのものは模擬しない。どちらのモードでも公式イメージを使う。
- `WEBUI_URL` は `https://` にする（本システムの OAuth プロキシが、`http://` の戻り先を拒否するため）。
- 証明書は `AIOHTTP_CLIENT_SSL_CERT_FILE` と `SSL_CERT_FILE` の 2 系統に渡す。
- `WEBUI_SECRET_KEY` は固定する（変えると、保管した OAuth の情報とトークンが読めなくなる）。
- モードは、テスト実行コマンドに渡す環境ファイルと、docker compose のプロファイルで切り替える。compose の定義は詳細設計で作る。
- 実装時・CI の必須ゴールは mock モードの全件通過。real モードは手動実行だけを必須にする。
