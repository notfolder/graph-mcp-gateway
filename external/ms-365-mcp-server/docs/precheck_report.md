# 事前確認レポート：ms-365-mcp-server

- 確認日：2026-11-01
- 目的：MCP のツールを自作せず、ms-365-mcp-server を HTTP モードで内部ネットワークに置き、FastMCP（OAuth プロキシと中継）の後ろで使えるかを、要件定義の前に確かめる。
- 背景：ms-365-mcp-server をそのまま使うと、OAuth の後の戻り URL を AI ツールごとに Entra ID に登録する必要がある。また、AI ツールに Entra のトークンが渡る。これを避けるため、前に FastMCP の薄いラッパーを置く。

## 1. 連携先の概要

| 項目 | 内容 |
|---|---|
| 名前 | ms-365-mcp-server（ディレクトリ名 `ms-365-mcp-server`） |
| 提供元 | Softeria（GitHub `Softeria/ms-365-mcp-server`） |
| 版 | 0.178.0（確認時点の最新。コミット `6f862af`、2026-10-30）。リリースの間隔は短く、版の番号は頻繁に上がる |
| 言語・実行環境 | Node.js（TypeScript）。公式イメージ `ghcr.io/softeria/ms-365-mcp-server:<版>`（`node:24-alpine` が元、root でない利用者で動く） |
| ライセンス | MIT |
| 役割 | Microsoft Graph を呼ぶ MCP のツールを提供する。本システムでは、FastMCP から MCP（Streamable HTTP）で呼ばれ、渡された Graph 用のトークンで Graph を呼ぶ |
| 本システムでの置き方 | `--http` で起動し、compose の内部ネットワークにだけ置く（ホストには公開しない）。ms-365-mcp-server 自身の OAuth の受け口は使わない |

## 2. 接続できるかの判定

**接続できる。** 使い捨てのコンテナで公式イメージを起動して確かめた（8 章）。

- 接続先は自分で起動するコンテナなので、外部への手続きは要らない。
- 接続経路の制約：FastMCP のコンテナから compose の内部ネットワークで届けばよい。ms-365-mcp-server からは `graph.microsoft.com` へ出る必要がある。
- 認可の手続き：ms-365-mcp-server のための Entra ID のアプリ登録は要らない。Graph 用のトークンは FastMCP が OBO で得て渡すため。

## 3. 認証方式

| 項目 | 内容 |
|---|---|
| FastMCP から ms-365-mcp-server へ | `Authorization: Bearer <Graph 用のトークン>`。ms-365-mcp-server は、トークンの期限だけを確かめ（期限切れは 401）、署名は確かめずに、そのトークンで Graph を呼ぶ（`src/lib/microsoft-auth.ts`）。署名・宛先は Graph が確かめる |
| トークンが無い要求 | 401 で拒否する（実測） |
| 利用者ごとの分離 | 要求ごとにトークンを持ち回す（`src/request-context.ts`、`src/graph-client.ts`）。MCP のセッションを持たない動作 |
| トークンの更新・失効 | ms-365-mcp-server はトークンを保管も更新もしない。更新は FastMCP（OBO のキャッシュ）が行う |
| 接続元の制約 | ms-365-mcp-server は、期限内のトークンなら誰の要求でも受け付ける。そのため、FastMCP 以外から届かないよう、内部ネットワークだけに置くことが前提 |
| 必要な環境変数名 | 7 章 |

## 4. 主な制限

| 項目 | 内容 | 要件定義での扱い |
|---|---|---|
| ツールの数と一覧の大きさ | 組織用のモード（`--org-mode`）では 367 ツールで、ツールの一覧が約 2.2 MB。依頼資料 P-5 の 12 の権限で絞っても（`--allowed-scopes`）175 ツール・約 0.99 MB 残る（実測）。AI ツールの入力に収まらない | 出すツールを決める要件が要る。手段は、ツール名での絞り込み（`--enabled-tools`・`--enabled-tools-file`・`--preset`）か、必要なときに読み込む方式（`--discovery`：3 ツール、約 2.7 KB。実験的な機能） |
| 権限での絞り込みの書き方 | `--allowed-scopes` は空白区切り。カンマ区切りだと 1 つの権限として扱われ、ほぼ全部のツールが消える（実測） | 設計で書き方を固定する |
| レート制限 | HTTP モードでは IP ごとに `/mcp` が毎分 120 回（実測。応答ヘッダー `RateLimit-Policy: 120;w=60`）。FastMCP の後ろに置くと、全利用者の要求が FastMCP の 1 つの IP から来るので、全員で毎分 120 回になる | 制限を外す（`MS365_MCP_RATE_LIMIT_DISABLED`）か、FastMCP の後ろであることを設定する必要がある |
| 応答の大きさ | Graph の応答をほぼそのまま返す。`$top` の上限（`MS365_MCP_MAX_TOP`）、全ページの取得の上限（`MS365_MCP_MAX_PAGES`・`MS365_MCP_MAX_ITEMS`）、メール本文のテキスト化（既定）を設定できる | 応答の大きさの扱いを要件で決める |
| 任意の Graph の要求 | 絞り込みの後も `graph-batch`（任意の Graph の要求をまとめて送る）が残る。利用者本人の委任の権限の範囲で動く | 出すかどうかを要件で決める |
| エラーの形 | Graph のエラーは状態コード・`error.code` と、Graph の `error.message`・要求 ID を含む文字列で返す（実測）。トークンは含まない | 前の要件の「エラーの種類」は外す方針なので、そのまま返してよいかを要件で決める |
| タイムアウト・利用時間帯・契約 | 公開資料に制限の記述は無い | — |
| 法務・ライセンス | MIT。自社サーバーでの利用と改変に制約は無い | — |
| 版の固定 | 版の番号が頻繁に上がるので、イメージを版のタグで固定する | 要件の「版を固定する」に含める |

## 5. 後続の isdd-external-research で調べる範囲

1. FastMCP の中継（`create_proxy` と、要求ごとにクライアントを作る関数）で、自分で付けた `Authorization` が FastMCP のヘッダーの転送で上書きされないか。
2. ツールの一覧の取得（`tools/list`）にも利用者のトークンが要る。FastMCP がツールの一覧を問い合わせるときのトークンの渡し方と、一覧のキャッシュ。
3. 出すツールの絞り方（ツール名の一覧か、必要なときに読み込む方式か）ごとに、AI ツール（Claude Code・Codex・OpenCode）で使えるか。
4. E2E の mock モード：
   - ms-365-mcp-server（Node.js）が `HTTPS_PROXY` で Dev Proxy を通るか（Node 24 は `NODE_USE_ENV_PROXY=1` が要る）。
   - Dev Proxy のルート証明書を `NODE_EXTRA_CA_CERTS` で信頼させられるか。
   - 既存の Graph の模擬の応答（`external/microsoft-graph/mock/mocks.json`）が、ms-365-mcp-server の組み立てる要求（パス・クエリ）に合うか。
5. ms-365-mcp-server の OAuth の受け口（`/authorize`・`/token`・`/register`）が内部ネットワークに残ることの扱い（無効にできるか）。
6. 応答の大きさを抑える設定（`MS365_MCP_MAX_TOP` など）の既定値と効き方。
7. ファイルの添付・ダウンロード系の機能（添付の URL を作る機能、ローカルファイルの読み書き）は既定で無効であること。

## 6. 要件定義に進んでよいかの判定

**条件付きで進んでよい。**

接続・認証・利用者ごとの分離は、要件の方針どおりに成り立つ。条件は、変更要件の定義で次を決めること。

- 出すツールの範囲と絞り方（ツールの一覧が大きすぎるため必須）
- レート制限の扱い
- 応答の大きさとエラーの返し方を、ms-365-mcp-server のままにするか

## 7. 必要な環境変数名の一覧

値は書かない。ms-365-mcp-server のコンテナに渡す。

| 名前 | 用途 |
|---|---|
| `MS365_MCP_ORG_MODE` | 組織用のモード（Teams・SharePoint のツールを含める） |
| `MS365_MCP_ALLOWED_SCOPES` | 出すツールを、依頼資料 P-5 の権限で使えるものに限る（空白区切り） |
| `ENABLED_TOOLS` または `ENABLED_TOOLS_FILE` | 出すツールを名前で絞る（絞り方を名前の一覧にした場合） |
| `MS365_MCP_RATE_LIMIT_DISABLED` または `MS365_MCP_TRUST_PROXY_HOPS` | レート制限の扱い |
| `MS365_MCP_MAX_TOP`、`MS365_MCP_MAX_PAGES`、`MS365_MCP_MAX_ITEMS` | 応答の大きさの上限（使う場合） |
| `HTTPS_PROXY`、`NO_PROXY`、`NODE_USE_ENV_PROXY`、`NODE_EXTRA_CA_CERTS` | E2E の mock モードで Dev Proxy を通す（調べる範囲 4） |

`MS365_MCP_CLIENT_ID`・`MS365_MCP_CLIENT_SECRET`・`MS365_MCP_TENANT_ID` は、ms-365-mcp-server 自身の OAuth と OBO を使わないので渡さない。秘密情報は無い。

## 8. 実接続テストの結果

- 実行日時：2026-11-01 00:50 ごろ（JST）
- 実行環境：手元の Docker（使い捨てのコンテナ、終了後に削除）。イメージ `ghcr.io/softeria/ms-365-mcp-server:0.178.0`

| 確かめたこと | 方法 | 結果 |
|---|---|---|
| 起動 | `--http 3000 --org-mode` で起動 | 起動した |
| トークンが無い要求の拒否 | `tools/list` を `Authorization` 無しで送る | 401 |
| トークンを付けた要求 | 期限内の偽の JWT（署名なし）を付けて `tools/list` | 200。367 ツール、一覧は 2,252,468 バイト |
| 渡したトークンで Graph を呼ぶか | 同じ偽の JWT で `get-current-user` を呼ぶ | Graph が 401 `InvalidAuthenticationToken` を返し、ツールのエラー（状態コード付き）として返った。渡したトークンがそのまま Graph に送られることを確かめた |
| 権限での絞り込み | `--allowed-scopes` に依頼資料 P-5 の 12 の権限を空白区切りで渡す | 175 ツール、一覧は 985,980 バイト。カンマ区切りでは 12 ツールまで減った |
| 必要なときに読み込む方式 | `--discovery` を足す | 3 ツール（`search-tools`、`get-tool-schema`、`execute-tool`）、一覧は 2,680 バイト |
| レート制限 | 応答ヘッダーを見る | `RateLimit-Policy: 120;w=60` |

実際の利用者のトークンでの確認（本物の Graph のデータの読み書き）は、PoC 用テナントの値を受け取ってから行う。

## 9. 取得できるスキーマ（エンティティ一覧）

ms-365-mcp-server はデータを持たない（Graph を呼ぶだけ）。本システムから見たスキーマは「ツールの一覧」になる。

- 組織用のモードで依頼資料 P-5 の権限で使えるツールの領域：メール（一覧・取得・下書き・送信・返信・転送・移動・削除・フォルダー・添付）、予定表（一覧・期間・取得・作成・変更・削除・返答・転送）、OneDrive（一覧・検索・取得・アップロード・フォルダー作成・移動と名前の変更・削除・共有・版）、Excel（範囲・表・グラフ）、SharePoint（サイトの検索・取得・ドライブ・リスト・リストの項目）、Teams（チャット・チーム・チャネル・メッセージ・返信・投稿・ピン留め・リアクション）、変更の通知（サブスクリプション）、その他（`graph-batch`、`download-bytes`、`read-mail-text` など）。
- 依頼資料 P-5 の権限で使えないために隠れるツール（192 個）の主な領域：共有メールボックス、連絡先、OneNote、Planner・To Do、オンライン会議、在席情報、グループ、メールボックスの設定。
