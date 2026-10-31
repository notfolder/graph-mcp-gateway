# バックログ（graph-mcp-gateway）

## isdd の開発工程
概要: .history/2026-11-01-0010-要件isdd化と外部連携調査/summary.md

- [ ] 詳細設計（isdd-design）で `docs/detail_design.md` を設計 ID 付きで作り直し、tasks.md を作る（追加 2026-11-01、重要 高）
- [ ] Dev Proxy を実機で起動し、`external/microsoft-graph/mock/mocks.json` の 302 の転送と nth の 429 が期待どおり返るか確かめる（追加 2026-11-01、重要 高）

## PoC 用テナントでの確認
概要: .history/2026-11-01-0010-要件isdd化と外部連携調査/summary.md

- [ ] PoC 用テナントの値を受け取ったら、real モードで `external/*/docs/research.md` の「未確認の項目」を確かめる（追加 2026-11-01、重要 高）

## 関連資料
概要: .history/2026-11-01-0010-要件isdd化と外部連携調査/summary.md

- [ ] `docs/related_materials.md` のプロキシ仕様の誤り（10 章の `forward_pkce` は AzureProvider では設定できない、5.3 の「additional_authorize_scopes に無いと交換に失敗」）を直すか決める（追加 2026-11-01、重要 低）
