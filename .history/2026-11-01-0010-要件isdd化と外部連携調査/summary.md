# 要件定義書の isdd 化と外部連携（Entra ID・Graph）の調査
更新: 2026-11-01 00:10 JST
セッション: e11a6139-daf3-4567-9758-1d76e7b265ea
ログ: ./session.md

## 概要
仕様書・設計書のレビューの後、要件定義書を isdd 形式で作り直し、Entra ID と Graph の外部連携の調査・模擬・連携ライブラリまで作った（詳細設計は次のセッション）。

## やったこと

- **仕様書・設計書のレビュー**
  - FastMCP 4.1.4 のソースと Graph・Entra の公式資料で突き合わせた。
  - 指摘（ページングの取りこぼし、302 の転送、アップロードの入力、複数台のセッション、v2 トークンなど）を、旧要件仕様書と旧設計書に反映した。
- **GitHub への公開**
  - 文書から「社内限り」・氏名・メールアドレスを消し、履歴を書き換えてから `notfolder/graph-mcp-gateway`（public）に push した。
  - 書き換え前のブランチは削除した。
- **isdd 化**
  - AI-004 を「対応表 `docs/trace_map.md` で管理し、コードに ID を書かない」に変えた。
  - `docs/design.md` を `docs/detail_design.md` に改名した（中身は旧設計のままで、isdd 形式ではない）。
- **外部連携の事前確認**
  - `external/entra-id/docs/precheck_report.md` と `external/microsoft-graph/docs/precheck_report.md` を書いた。
  - テナントが無いので、実接続は未実施とした。判定は「条件付きで進んでよい」。
- **要件定義書を isdd 形式で作り直した**（`docs/requirements.md`）
  - RQ-* は 88 件。業務課題は 1 つ（`RQ-BK-SHARED-M365-MCP-POC`）。
  - 旧 ID は「旧 ID」列に残した。
  - `rq_integrity_checker.py` は問題 0 件で合格。
- **外部連携の調査（isdd-external-research）**
  - サブエージェント 3 本で調べ、主な点はソースで確かめ直した。
  - 成果物：
    - `external/*/docs/research.md` と `alignment_report.md`（判定はどちらも「設計に進める」）
    - `external/microsoft-graph/src/graph_api/`（httpx2 の薄いラッパー。41 のエンドポイント）
    - `external/entra-id/mock/`（自作の模擬 Entra ID と、利用者 4 人）
    - `external/microsoft-graph/mock/`（Dev Proxy の設定と、模擬の応答 65 件）
    - `external/*/e2e/`（mock / real の環境ファイル、`make-certs.sh`）
    - `.env.example`
  - 手元で確かめたこと：
    - Graph のラッパーは、通信なしの試験に通った。
    - 模擬 Entra ID は、FastMCP の検証、更新、azure-identity の非同期版の OBO、AADSTS50105、AADSTS65001 を確かめた。
- **ホーム側の書き換え**：`.history/` は公開する、という決まりに戻した。
  - `~/.claude/skills/session-handover/SKILL.md`
  - `~/CLAUDE.md` 75 行目
  - `~/docs` の過去の記録 3 ファイル
  - **`~/.claude` のコミットと push はまだ**（ホームのセッションで行う決まり）。
- **意図的に残したもの**：
  - `docs/detail_design.md` は旧設計のまま。次の詳細設計で作り直す。
  - Dev Proxy の実機での起動は未確認（調査のときに docker の実行が自動許可で止められた）。

## 決定事項

- **`.history/` は公開する。** ユーザーの判断。commit の前に、氏名・メールアドレス・社名・NDA の内容・秘密情報を伏せ字にする。
- **`.gitignore` は `.env` だけ。**
- **isdd の正規の順で進める。** 要件定義 → 外部連携の調査 → 詳細設計。
- **要件定義の主な回答**：
  - 業務の問題は「手でコピーしている」。KPI は未測定。業務課題は 1 つ。
  - 配備はコンテナ。本番も docker compose で 1 台。
  - チームの技術とライセンスの制約は特に無い（無料の OSS のみ）。
  - 社内ネットワーク（VPN を含む）からだけ使う。
  - 応答時間・可用性・監査ログ・監視・バックアップの要求は無い。
  - HTTPS は必須。証明書は社内の認証局が発行する。
- **上限と既定値**：
  - ツール注釈は付けない。
  - ファイルの内容を返す上限は 100 KB（設定で変更可）。アップロードの上限は 1 MB（設定で変更可）。
  - 再試行は 3 回で、429・503 だけ。
  - 件数の上限の最大値は 100（設定で変更可）。
- **ツールの決め方**：
  - ツール名は「対象_操作」。
  - 一覧は主な項目だけを返す。
  - メールフォルダーは、親フォルダーを指定して下の階層も取れるようにする。
  - 同じ名前のフォルダーの作成はエラーにする。
- **外部連携の選定**：
  - Graph の連携ライブラリは、httpx2 の上の自作の薄いラッパー。
  - 模擬 Entra ID は Python で自作。
  - Graph の模擬は Dev Proxy。
  - E2E は、日常を mock モード、最終確認を PoC 用テナント（real モード）で行う。

## 次にやること

1. 詳細設計（isdd-design）。技術選定の比較表を出して承認をもらい、`docs/detail_design.md` を設計 ID 付きで作り直し、tasks.md を作る。
2. Dev Proxy を実機で起動し、模擬の応答（302 の転送、nth を使った 429 の後の成功）を確かめる。
3. PoC 用テナントの値を受け取ったら、real モードで `external/*/docs/research.md` の「未確認の項目」を確かめる。

## バックログ

- [ ] 詳細設計（isdd-design）で `docs/detail_design.md` を設計 ID 付きで作り直し、tasks.md を作る（追加 2026-11-01、重要 高）
- [ ] Dev Proxy を実機で起動し、`external/microsoft-graph/mock/mocks.json` の 302 の転送と nth の 429 が期待どおり返るか確かめる（追加 2026-11-01、重要 高）
- [ ] PoC 用テナントの値を受け取ったら、real モードで `external/*/docs/research.md` の「未確認の項目」を確かめる（追加 2026-11-01、重要 高）
- [ ] `docs/related_materials.md` のプロキシ仕様の誤り（10 章の `forward_pkce` は AzureProvider では設定できない、5.3 の「additional_authorize_scopes に無いと交換に失敗」）を直すか決める（追加 2026-11-01、重要 低）
