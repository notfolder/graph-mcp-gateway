# バックログ（graph-mcp-gateway）

## isdd の開発工程
概要: .history/2026-11-01-1039-ms365中継への方針変更と設計/summary.md

- [x] (2026-11-01) 実装：isdd-setup で対応表チェックを入れ、isdd-traceable-coding で tasks.md の順に実装した（mock モードの E2E 全件通過、未コミット）
- [x] (2026-11-01) 実装後の逆引き整合チェック：proposals の 11 件を正本に反映し（要件 RQ-NF-GRAPH-RETRY-BY-MS365 の文言を含む）、proposals.md を消した
- [x] (2026-11-01) 実装をブランチ `impl/relay-ms365` にコミットした
- [x] (2026-11-01) real-offsite（Claude の API での Open WebUI の確認）：Claude がツールを探す→引数を調べる→実行するで M365 のツールを呼べた。途中で、Open WebUI の自前のツールを選ぶ取り違えを見つけ、両方のモデルで自前のツールを外し既定のモデルを PoC アシスタントにして直した。言語モデルは今日の日付を知らないので、日付をはっきり書くよう手順書で案内する（ユーザーの判断）
- [x] (2026-11-01) 社外の確認を人の操作で行った：Open WebUI（ブラウザで認可、Claude がツールを探して呼んだ）と Claude Code（`/mcp` で認可、プロフィールを取得）で、接続の確認画面と Entra ID の模擬のサインイン画面を通して使えた（`gateway.localhost`・`entra.localhost:9443` の構成）
- [ ] 社内の確認で、本物の Entra ID のサインイン画面を通したときの Open WebUI の表示に合わせて、`docs/connect/open-webui.md` の画面の操作の書き方を直す（追加 2026-11-01、重要 中）
- [ ] PR #1（https://github.com/notfolder/graph-mcp-gateway/pull/1）を確認して main に取り込む（追加 2026-11-01、重要 高）
- [ ] Entra ID の戻り先の 2 件目（`https://<公開のホスト名>/discovery/auth/callback`）の追加を別部署に依頼する（依頼資料は直し済み）（追加 2026-11-01、重要 高）
- [ ] 社内の言語モデルの接続先の事前確認：接続情報を受け取ってから、`external/language-model/docs/precheck_report.md` と同じ 3 つの要求で確かめる（追加 2026-11-01、重要 高）

## PoC 用テナントでの確認
概要: .history/2026-11-01-1039-ms365中継への方針変更と設計/summary.md

- [ ] PoC 用テナントの値を受け取ったら、real モードで `external/*/docs/research.md` の「確かめられなかったこと」を確かめる（追加 2026-11-01、重要 高）

## 関連資料
概要: .history/2026-11-01-0010-要件isdd化と外部連携調査/summary.md

- [ ] `docs/related_materials.md` のプロキシ仕様の誤り（10 章の `forward_pkce` は AzureProvider では設定できない、5.3 の「additional_authorize_scopes に無いと交換に失敗」）を直すか決める（追加 2026-11-01、重要 低）
