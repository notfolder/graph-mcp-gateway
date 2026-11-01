# CLAUDE.md（graph-mcp-gateway）

## 決まり

- **isdd で進める。** 正本は `docs/requirements.md` と `docs/detail_design.md`。工程は要件定義 → 外部連携の調査 → 詳細設計 → 実装。
- **MCP のツールは自作しない。** 既製の ms-365-mcp-server を内部ネットワークに置き、FastMCP は OAuth プロキシと中継だけを受け持つ（経緯は要件定義書 1 章）。
- **要件 ID・設計 ID とコードの対応は `docs/trace_map.md` に記録し、コード（コメントを含む）に ID を書かない。**
- **このリポジトリは公開。** 秘密情報・氏名・メールアドレス・社名をコミットしない。`.env` は `.gitignore` 済みで、見本は `.env.sample`。
- **`.history/` も公開する。** commit の前に、`session.md` の個人情報・社名・NDA の内容・秘密情報を伏せ字にする。
- **外部連携の模擬は `external/` が正本。** Entra ID と言語モデルは自作の模擬、Graph は Dev Proxy。E2E は mock モードの全件通過が必須で、real モードは手動。
- **OBO に使う azure-identity の非同期版は aiohttp が要る**（`fastmcp[azure]` に含まれない）。
- **`src/` と `external/open-webui/src/` は Python 3.9 でも構文解析できる書き方にする。** `scripts/isdd/check.sh` がシステムの python3 で動くため（`def f[T]()` などを使わない）。
- **E2E は `bash e2e/run.sh mock`（約 27 分、`--skip-capacity` で約 12 分）。人の操作での確認は `bash e2e/run.sh real-offsite`**（`gateway.localhost`・`entra.localhost:9443`、手順は `e2e/real-checklist.md`）。

## 場所

- 最新の引き継ぎ: `.history/2026-11-01-1436-ms365中継の実装と社外確認/summary.md`
- 残作業: `.history/BACKLOG.md`

<!-- isdd-setup:begin -->
## isdd トレーサビリティ規則（isdd-setup が管理する。手で編集しない）

- 仕様とコードの対応は `docs/trace_map.md`（対応表）で管理する。コードに要件 ID や設計 ID を書かない。
- クラス・公開関数・ソースファイルを追加、改名、削除したら、同じ作業の中で `docs/trace_map.md` の行を更新する。
- コードを変更した作業の終わりに `bash scripts/isdd/check.sh` を実行する。エラーが出たら直してから作業を終える。警告は報告に含める。
- 設計要素を増やす必要があれば、コードを書く前に `docs/detail_design.md` を更新する。設計 ID の採番は設計スキルの責務で、実装中に ID を作らない。
<!-- isdd-setup:end -->
