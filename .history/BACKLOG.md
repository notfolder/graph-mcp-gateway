# バックログ（graph-mcp-gateway）

## isdd の開発工程
概要: .history/2026-11-01-1039-ms365中継への方針変更と設計/summary.md

- [ ] 実装：isdd-setup で対応表チェックを入れ、isdd-traceable-coding で `.history/20261101-relay-ms365-mcp-server/tasks.md` の順に実装する（追加 2026-11-01、重要 高）
- [ ] Entra ID の戻り先の 2 件目（`https://<公開のホスト名>/discovery/auth/callback`）の追加を別部署に依頼する（依頼資料は直し済み）（追加 2026-11-01、重要 高）
- [ ] 社内の言語モデルの接続先の事前確認：接続情報を受け取ってから、`external/language-model/docs/precheck_report.md` と同じ 3 つの要求で確かめる（追加 2026-11-01、重要 高）

## PoC 用テナントでの確認
概要: .history/2026-11-01-1039-ms365中継への方針変更と設計/summary.md

- [ ] PoC 用テナントの値を受け取ったら、real モードで `external/*/docs/research.md` の「確かめられなかったこと」を確かめる（追加 2026-11-01、重要 高）

## 関連資料
概要: .history/2026-11-01-0010-要件isdd化と外部連携調査/summary.md

- [ ] `docs/related_materials.md` のプロキシ仕様の誤り（10 章の `forward_pkce` は AzureProvider では設定できない、5.3 の「additional_authorize_scopes に無いと交換に失敗」）を直すか決める（追加 2026-11-01、重要 低）
