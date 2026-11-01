# ms-365-mcp-server を中継する共有 MCP サーバーの実装と社外の確認
更新: 2026-11-01 14:36 JST
セッション: 47317742-afc1-4922-bad1-a6866c247107
ログ: ./session.md

## 概要
tasks.md の順に実装して mock モードの E2E を全件通し、実装後の逆引き整合で正本を直し、社外の確認（Claude の API・人の操作）まで済ませて PR #1 を作った。

## やったこと

- **対応表チェックの導入（isdd-setup）**：`scripts/isdd/`、`AGENTS.md`、`CLAUDE.md` の規則、`.claude/settings.json`（応答の終わりに `check.sh`）。版は v2.0.0。
- **実装（isdd-traceable-coding、tasks.md の 1〜13 と固定タスク）**：
  - 中継のアプリ `src/graph_mcp_gateway/`（設定、認証と保管先、OBO で得た Graph 用のトークンを付けた中継、サーバーの組み立て、起動、Open WebUI の初期設定）。
  - `Dockerfile`、`compose.yaml`、`deploy/nginx/default.conf.template`、`.env.sample`。
  - 単体・結合テスト 116 本、E2E（`e2e/`：実行スクリプト、compose の追加ファイル 6 つ、補助の部品、処理量の測定、ホスト側の確認）。
  - 手順書：`README.md`、`docs/connect/`、`docs/operations/`、`e2e/real-checklist.md`。対応表 `docs/trace_map.md`。
- **E2E の mock モード**：処理量の測定を含む通しが 12:28 に全件通過。初期設定を直した後の通し（処理量の測定は除く）が 14:01 に全件通過。処理量（CPU 1 個）は中継 毎秒 27〜30 回、ms-365-mcp-server 毎秒 80 回以上で 429 なし（`.history/20261101-relay-ms365-mcp-server/capacity-report-mock.md`）。
- **実装で見つけた主な問題と直し方**：
  - Open WebUI v0.12.5 は未公開の元のモデルを一般の利用者に使わせない → 元のモデルも公開する。
  - ツールの一覧の取得で OBO が失敗すると Entra のエラーの文言が AI ツールに出ていた → 詳細を伏せた例外にする。
  - FastMCP が起動時に PyPI へ版を確かめに行く → `show_banner=False`。
  - Open WebUI の自前のツール（カレンダー・現在時刻）を Claude が選び、M365 のツールを呼ばなかった → 元のモデルと PoC アシスタントの両方で自前のツールを外し、新しいチャットの既定のモデルを PoC アシスタントにする。
  - そのほか、証明書の束の改行、bash の変数名と全角の括弧、compose のプロファイル、Open WebUI のログインの回数の制限（3 分で 15 回）。
- **実装後の逆引き整合（isdd-post-implementation-review）**：`docs/proposals.md` の 11 件を設計書・外部連携の調査・運用手順書に反映し、要件 `RQ-NF-GRAPH-RETRY-BY-MS365` の文言（503 は `Retry-After` を待たない）を直して、proposals.md を消した。未マッピングは無し。
- **社外の確認（`bash e2e/run.sh real-offsite`）**：Claude の API につないだ Open WebUI で、Claude がツールを探す → 引数を調べる → 実行するの順に M365 のツールを呼べた。公開のホスト名を `gateway.localhost`、Entra ID の模擬を `entra.localhost:9443` にして、人がブラウザ（Open WebUI）と Claude Code で、接続の確認画面と Entra ID の模擬のサインイン画面を通して使えることを確かめた。
- **コミットと PR**：ブランチ `impl/relay-ms365` に 3 コミット（`c83d8bf`・`5e8f7fd`・`ad3dd74`）、PR #1 https://github.com/notfolder/graph-mcp-gateway/pull/1 。main には未取り込み。
- **意図的に残したもの**：プロジェクト直下の `.env`（Claude の API の本物の鍵。`.gitignore` 済み）。`e2e/.work/`（E2E の作業場所。`.gitignore` 済み）。

## 決定事項

- 実装で分かった差は、設計書との差の一覧（proposals）を作ってから正本に反映し、コミットする（ユーザー回答 1A）。
- 要件の再試行の文言は、ms-365-mcp-server の実際の動きに合わせて直す（503 は `Retry-After` を待たない。製品を改造しない方針のため）。
- Open WebUI では、元のモデルと PoC アシスタントの両方で自前のツールを外し、既定のモデルを PoC アシスタントにする（取り違えを確実に防ぐため。ユーザー回答 B）。
- 言語モデルに今日の日付は渡さず、利用者に日付をはっきり書いてもらうよう手順書で案内する（ユーザー回答 B）。
- 取り込みはブランチを push して PR にする（ユーザー回答 B）。
- isdd の対応表チェッカーの不具合（末尾が `-ID` の設計 ID を見出しと見なす、`check.sh` がシステムの python3 で動く）は、このリポジトリの外の作業としてユーザーに報告した（バックログには書かない）。

## 次にやること

- PR #1 を確認して main に取り込む。
- Entra ID の戻り先の 2 件目の追加を別部署に依頼する。
- PoC 用テナントの値と社内の言語モデルの接続先を受け取ったら、real モード（`bash e2e/run.sh real` と `e2e/real-checklist.md` の社内の手順）を行う。

## バックログ

- [x] (2026-11-01) 実装（isdd-setup → isdd-traceable-coding、tasks.md の順）
- [x] (2026-11-01) 実装後の逆引き整合チェック（proposals の 11 件を正本に反映）
- [x] (2026-11-01) 社外の確認（Claude の API、人の操作での Open WebUI と Claude Code）
- [ ] PR #1 を確認して main に取り込む（追加 2026-11-01、重要 高）
- [ ] 社内の確認で、本物の Entra ID の画面に合わせて `docs/connect/open-webui.md` の画面の操作の書き方を直す（追加 2026-11-01、重要 低）
- [ ] Entra ID の戻り先の 2 件目の追加を別部署に依頼する（追加 2026-11-01、重要 高）
- [ ] 社内の言語モデルの接続先の事前確認（追加 2026-11-01、重要 高）
- [ ] PoC 用テナントでの real モードの確認（追加 2026-11-01、重要 高）
- [ ] 関連資料のプロキシ仕様の誤りを直すか決める（追加 2026-11-01、重要 低）
