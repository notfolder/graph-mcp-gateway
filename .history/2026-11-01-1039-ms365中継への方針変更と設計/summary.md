# ms-365-mcp-server を中継する方針への変更（要件・外部連携の調査・詳細設計）
更新: 2026-11-01 10:40 JST
セッション: 6b558391-76f2-4e68-9e8a-b7ec89d92f47
ログ: ./session.md

## 概要
ツール自作の方針をやめ、既製の ms-365-mcp-server を FastMCP の OAuth プロキシで中継する方針に要件・外部調査・詳細設計を作り直した（実装の直前まで）。

## やったこと

- **詳細設計（最初の版）**：依頼「設計をして」で isdd-design を実行し、技術選定（Python 3.14、uv、nginx、Redis、pytest、Dev Proxy、Entra ID の模擬）の承認を得て、ツールを自作する前提の設計書と tasks.md を作った。
- **方針の誤りの発見**：ユーザーの「ms-365-mcp-server を使うようになっていますか？」から、プロジェクトの経緯（ms-365-mcp-server をそのまま使うと AI ツールごとに Entra ID の戻り先の登録が要るので、前に FastMCP の薄いラッパーを置くために立ち上げた）が文書に残っておらず、要件と設計が自作の方向に進んでいたことが分かった。stdio での呼び出しも検討し、HTTP で中継すると決めた。
- **外部連携の事前確認（4 つ）**：ms-365-mcp-server（公式イメージで実測。367 ツール・2.2 MB、P-5 の権限で 175 ツール・約 0.95 MB、`--discovery` で 3 ツール、レート制限 毎分 120 回）、Open WebUI v0.12.5（模擬の言語モデル経由でツールの実行まで実測）、言語モデル（Claude の API の OpenAI 互換の受け口で、応答とツールの呼び出しを実測。Max プランの鍵は使えないことを確認）。レポートは `external/*/docs/precheck_report.md`。
- **変更要件の定義**：`.history/20261101-relay-ms365-mcp-server/change_requirements.md`。決まった主な内容は「決定事項」のとおり。推奨より複雑な案を選んだ 8 か所は、ユーザーの理由をそのまま記録した。
- **外部連携の詳細調査**：サブエージェント 3 本を並列で使い、ms-365-mcp-server・FastMCP の中継・Open WebUI をソースと実測で調べた。Open WebUI → FastMCP の OAuth プロキシ → Entra ID の模擬で、OAuth 2.1 を最後まで通した（ブラウザの自動操作は不要）。調査で見つかった不整合（回路遮断器が全員で 1 つ、OAuth の受け口を止められない、ログに本文が残る、応答の大きさが無制限、認証なしの URL を返すツールなど）をユーザーの判断で要件に反映した。Graph の模擬（`external/microsoft-graph/mock/`）を ms-365-mcp-server 向けに作り直し、Dev Proxy 4.0.0 の実機で 26 ツール・異常系・上限を確認した。言語モデルの模擬（`external/language-model/mock/mock_llm.py`）と Open WebUI の連携ライブラリ（`external/open-webui/src/openwebui_api/`）を作った。
- **正本の書き直し**：実装も確定した設計も無いので、ユーザーの判断で変更設計を待たずに `docs/requirements.md` へ直接反映した（97 の ID）。依頼資料 `docs/related_materials.md` の「FastMCP で自作」の言い方と、Entra ID の戻り先 2 件を直した。
- **詳細設計の作り直し**：`docs/detail_design.md`（75 の設計 ID、整合チェック合格、図 8 つ描画可）と `.history/20261101-relay-ms365-mcp-server/tasks.md`（実装タスク 13、固定タスク）。
- **消したもの**：使わなくなった Graph の連携ライブラリ `external/microsoft-graph/src/graph_api/`（コミット `b43a62c` に残る）、旧版の tasks.md（`.history/20261101-詳細設計/`、未コミット）。
- **意図的に残したもの**：プロジェクト直下の `.env`（Claude の API の本物の鍵。`.gitignore` 済み）。見本は `.env.sample`。

## 決定事項

- MCP のツールは自作せず、ms-365-mcp-server（HTTP モード、内部ネットワークだけ）を FastMCP の OAuth プロキシと中継の後ろに置く。中継のたびに OBO で得た Graph 用のトークンを付ける（理由：AI ツールごとの Entra ID の戻り先の登録を避け、AI ツールに Entra のトークンを渡さないため）。
- 出すツールは依頼資料 P-5 の権限で使えるもの（認証なしの URL を返す `get-download-url` と使えない `get-upload-url` を除き 173 個）。
- MCP の受け口は 2 つ：全部を出す方（`/full`）と探して使う方（`/discovery`、直接出すツールは最初は空）。受け口ごとに OAuth プロキシのコンテナを分け、Entra ID の戻り先は 2 件（固定）。
- PoC 専用の Open WebUI を compose に入れる（探して使う受け口だけにつなぐ。ログインは Open WebUI のアカウントで管理者が作る）。mock モードの自動テストにも入れる。言語モデルは社内では社内の接続先、社外では Claude の API（Haiku 5.5）。
- 中継の部分は台数を増やせる（ms-365-mcp-server も）。1 台あたりの処理量を測り、1 万人の台数を見積もれるようにする（理由：本番の稟議に台数と費用の根拠が要る）。
- ms-365-mcp-server のレート制限と回路遮断器は外す。ログは警告以上だけ、監査のログは止める。応答の大きさの上限は ms-365-mcp-server の設定で決める。
- 連携の部品は推奨どおり採用（FastMCP の `ProxyProvider`、自作の Open WebUI のクライアント、自作の言語モデルの模擬）。処理量の測定は自作のスクリプト。

## 次にやること

- isdd-setup で対応表チェックを入れ、isdd-traceable-coding で `.history/20261101-relay-ms365-mcp-server/tasks.md` の順に実装する。
- Entra ID の戻り先の 2 件目（`https://<公開のホスト名>/discovery/auth/callback`）の追加を別部署に依頼する。
- 実装で確かめること：実際の nginx での認可サーバーのメタデータの書き換え、MCP の新しい版での一覧の取り直しの影響（処理量の測定で見る）、権限を並べた OBO が本物の Entra ID で通るか。

## バックログ

- [ ] 実装（isdd-setup → isdd-traceable-coding、tasks.md の順）（追加 2026-11-01、重要 高）
- [ ] Entra ID の戻り先の 2 件目の追加を別部署に依頼する（追加 2026-11-01、重要 高）
- [ ] 社内の言語モデルの接続先の事前確認（接続情報を受け取ってから）（追加 2026-11-01、重要 高）
- [ ] PoC 用テナントでの real モードの確認（追加 2026-11-01、重要 高）
- [ ] 関連資料のプロキシ仕様の誤りを直すか決める（追加 2026-11-01、重要 低）
- [x] (2026-11-01) 詳細設計（isdd-design）で設計書と tasks.md を作る（ms-365-mcp-server の中継の方針で作り直し）
- [x] (2026-11-01) Dev Proxy の実機での確認（ms-365-mcp-server 向けに模擬を作り直して確認）
- [x] (2026-11-01) 依頼資料の「FastMCP で自作」の言い方と戻り先 2 件の修正
