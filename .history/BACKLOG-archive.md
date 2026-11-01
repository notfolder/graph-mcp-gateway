# バックログの完了・見送り（graph-mcp-gateway）

## isdd の開発工程

- [x] (2026-11-01) 詳細設計（isdd-design）で `docs/detail_design.md` と tasks.md を作る（最初はツールを自作する前提で作り、方針変更で ms-365-mcp-server の中継の設計に作り直した）
- [x] (2026-11-01) Dev Proxy を実機で起動して Graph の模擬を確かめる（ms-365-mcp-server 向けに作り直し、26 ツール・異常系・上限を確認）
- [x] (2026-11-01) 方針変更の要件の定義・外部連携の調査・正本への反映（`.history/20261101-relay-ms365-mcp-server/change_requirements.md`）
- [x] (2026-11-01) 依頼資料の「FastMCP で自作」の言い方と、Entra ID の戻り先 2 件の修正
- [x] (2026-11-01) 言語モデル（Claude の API）の事前確認
- [x] (2026-11-01) 実装：isdd-setup で対応表チェックを入れ、isdd-traceable-coding で tasks.md の順に実装した（mock モードの E2E 全件通過）
- [x] (2026-11-01) 実装後の逆引き整合チェック：proposals の 11 件を正本に反映し（要件 RQ-NF-GRAPH-RETRY-BY-MS365 の文言を含む）、proposals.md を消した
- [x] (2026-11-01) 実装をブランチ `impl/relay-ms365` にコミットした
- [x] (2026-11-01) real-offsite（Claude の API での Open WebUI の確認）：Claude がツールを探す→引数を調べる→実行するで M365 のツールを呼べた。途中で、Open WebUI の自前のツールを選ぶ取り違えを見つけ、両方のモデルで自前のツールを外し既定のモデルを PoC アシスタントにして直した。言語モデルは今日の日付を知らないので、日付をはっきり書くよう手順書で案内する（ユーザーの判断）
- [x] (2026-11-01) 社外の確認を人の操作で行った：Open WebUI（ブラウザで認可、Claude がツールを探して呼んだ）と Claude Code（`/mcp` で認可、プロフィールを取得）で、接続の確認画面と Entra ID の模擬のサインイン画面を通して使えた（`gateway.localhost`・`entra.localhost:9443` の構成）
