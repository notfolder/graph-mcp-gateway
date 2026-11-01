# CLAUDE.md（graph-mcp-gateway）

## 決まり

- **isdd で進める。** 正本は `docs/requirements.md` と `docs/detail_design.md`。工程は要件定義 → 外部連携の調査 → 詳細設計 → 実装。
- **MCP のツールは自作しない。** 既製の ms-365-mcp-server を内部ネットワークに置き、FastMCP は OAuth プロキシと中継だけを受け持つ（経緯は要件定義書 1 章）。
- **要件 ID・設計 ID とコードの対応は `docs/trace_map.md` に記録し、コード（コメントを含む）に ID を書かない。**
- **このリポジトリは公開。** 秘密情報・氏名・メールアドレス・社名をコミットしない。`.env` は `.gitignore` 済みで、見本は `.env.sample`。
- **`.history/` も公開する。** commit の前に、`session.md` の個人情報・社名・NDA の内容・秘密情報を伏せ字にする。
- **外部連携の模擬は `external/` が正本。** Entra ID と言語モデルは自作の模擬、Graph は Dev Proxy。E2E は mock モードの全件通過が必須で、real モードは手動。
- **OBO に使う azure-identity の非同期版は aiohttp が要る**（`fastmcp[azure]` に含まれない）。

## 場所

- 最新の引き継ぎ: `.history/2026-11-01-1039-ms365中継への方針変更と設計/summary.md`
- 残作業: `.history/BACKLOG.md`
