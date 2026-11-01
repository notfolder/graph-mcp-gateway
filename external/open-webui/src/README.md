# Open WebUI の連携ライブラリ

`openwebui_api/` に、Open WebUI（v0.12.5）の API の薄い非同期クライアントを置く。初期設定の手順と E2E から使う。

| 公開インターフェース | 役割 |
|---|---|
| `OpenWebUIClient` | Open WebUI の各エンドポイントに 1 対 1 で対応するメソッドを持つ。1 つのインスタンスが 1 人のログインの状態（トークンと Cookie）を持つ |
| `OpenWebUIError` | Open WebUI がエラーを返したときの例外（状態コード、`detail`） |

- 業務の判断（初期設定の順番、認可の画面を進める処理）は入れない。それらは初期設定のスクリプトと E2E 側で行う（詳細設計）。
- 依存は `httpx2` だけ。メソッドの一覧は `../docs/research.md` 3 章。
