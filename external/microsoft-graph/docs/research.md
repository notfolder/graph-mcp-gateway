# 調査レポート：Microsoft Graph

- 確認日：2026-10-31
- 入力：`docs/requirements.md`（3-0 のツール一覧、3-2 の業務ルール、4-2 のデータ項目）
- 事前確認：`external/microsoft-graph/docs/precheck_report.md`
- 調べ方：Graph v1.0 の API リファレンスを、元の公開リポジトリ（`microsoftgraph/microsoft-graph-docs-contrib`、2026-10-31 時点の main）で読んだ。FastMCP 4.1.4、httpx2・httpcore2 2.16.0、azure-identity 1.27.0 は配布物を展開してソースで確かめた。実接続はテナントが無いため行っていない。

> **2026-11-01 の方針変更による注意**：本システムは MCP のツールを自作せず、Graph を呼ぶのは既製の ms-365-mcp-server になった。本書のうち、自作のツールの一覧・業務ルール・データ項目との突き合わせ、httpx2 の連携ライブラリ（`graph_api/`。使わなくなったので 2026-11-01 に消した）の選定は、今の要件には当てはまらない。Graph の API の仕様と制限（認証、スロットリング、ページング、エラー）の記述は引き続き有効。ms-365-mcp-server が送る要求と、作り直した模擬は `external/ms-365-mcp-server/docs/research.md` と `../mock/README.md` を見る。


## 1. システム概要

| 項目 | 内容 |
|---|---|
| システム名 | Microsoft Graph（ディレクトリ名 `microsoft-graph`） |
| 役割 | Microsoft 365 のデータ（メール、予定表、OneDrive・SharePoint、Teams）を読み書きする |
| API の種類 | REST（JSON）。v1.0 だけを使う |
| ベース URL | `https://graph.microsoft.com/v1.0` |
| 公式ドキュメント | https://learn.microsoft.com/graph/api/overview?view=graph-rest-1.0 |

## 2. 認証・接続情報

| 項目 | 内容 |
|---|---|
| 認証方式 | OAuth 2.0 のベアラートークン（`Authorization: Bearer`）。トークンは Entra ID の OBO で、利用者のトークンから交換して得る（`external/entra-id/docs/research.md`） |
| 権限 | 委任アクセスだけ。39 ツールすべてが、依頼資料 P-5 の権限で足りる。管理者の同意が必須なのは `ChannelMessage.Read.All` だけ |
| 必要な環境変数 | 無い（トークンは実行時に得る） |
| TLS | httpx2 は Linux では OS の証明書ストア（OpenSSL の既定の場所）を信頼し、`SSL_CERT_FILE` か `SSL_CERT_DIR` があればそれで置き換える（httpcore2 の `_ssl.py`）。プロキシは `HTTPS_PROXY`・`NO_PROXY` を読む |

## 3. オペレーション一覧

「最大件数」は 1 回の要求で返る件数の上限（`$top` の上限）。「—」は一覧ではない操作。

**プロフィール・メール**

| オペレーション名 | エンドポイント | メソッド | 主要パラメータ | レスポンス概要 |
|---|---|---|---|---|
| プロフィールの取得 | `/me` | GET | `$select` | 200 と user |
| フォルダーの一覧（いちばん上） | `/me/mailFolders` | GET | `$top`、`$select` | 200 と mailFolder の一覧（いちばん上の階層だけ） |
| フォルダーの一覧（下の階層） | `/me/mailFolders/{id}/childFolders` | GET | `$top`、`$select` | 200 と mailFolder の一覧 |
| メールの一覧 | `/me/messages`、`/me/mailFolders/{id}/messages` | GET | `$top`（1〜1000、既定 10）、`$select`、`$filter` か `$search` | 200 と message の一覧。続きは `@odata.nextLink`（`$skip` 方式） |
| メールの取得 | `/me/messages/{id}` | GET | `Prefer: outlook.body-content-type` | 200 と message |
| 添付ファイルの一覧 | `/me/messages/{id}/attachments` | GET | `$select=id,name,contentType,size` | 200 と attachment の一覧。`$select` が無いと中身（contentBytes）まで返る |
| 下書きの作成 | `/me/messages` | POST | toRecipients・ccRecipients・bccRecipients、subject、body（contentType、content） | 201 と message |
| 下書きの更新 | `/me/messages/{id}` | PATCH | 変える項目だけ | 200 と message。宛先・件名・本文は下書きのときだけ変えられる |
| メールの送信 | `/me/sendMail` | POST | message、saveToSentItems | 202（本文なし） |
| 下書きの送信 | `/me/messages/{id}/send` | POST | 本文なし（`Content-Length: 0` が必須） | 202（本文なし） |
| 返信・全員に返信 | `/me/messages/{id}/reply`、`/replyAll` | POST | comment | 202（本文なし）。comment と message.body の両方を付けると 400 |
| 転送 | `/me/messages/{id}/forward` | POST | comment、toRecipients | 202（本文なし） |
| メールの移動 | `/me/messages/{id}/move` | POST | destinationId | 201 と移動先の message（**ID が変わる**） |
| 既読・フラグの変更 | `/me/messages/{id}` | PATCH | isRead、flag.flagStatus（notFlagged / flagged / complete） | 200 と message |
| メールの削除 | `/me/messages/{id}` | DELETE | — | 204 |

**予定表**

| オペレーション名 | エンドポイント | メソッド | 主要パラメータ | レスポンス概要 |
|---|---|---|---|---|
| 期間の予定の一覧 | `/me/calendarView` | GET | startDateTime・endDateTime（必須）、`$top`、`$select`、`Prefer: outlook.timezone` | 200 と event の一覧。続きは `@odata.nextLink`（`$skip` 方式） |
| 予定の取得 | `/me/events/{id}` | GET | `Prefer: outlook.timezone` | 200 と event |
| 予定の作成 | `/me/events` | POST | subject、start・end（dateTime と timeZone）、location、attendees、body | 201 と event。参加者がいれば招待が送られる |
| 予定の変更 | `/me/events/{id}` | PATCH | 変える項目だけ | 200 と event |
| 予定の削除 | `/me/events/{id}` | DELETE | — | 204。主催者が消すと参加者に取り消しが送られる |
| 招待への返答 | `/me/events/{id}/accept`、`/tentativelyAccept`、`/decline` | POST | comment、sendResponse（既定 true） | 202（本文なし） |

**ファイル・SharePoint**

| オペレーション名 | エンドポイント | メソッド | 主要パラメータ | レスポンス概要 |
|---|---|---|---|---|
| フォルダーの中身の一覧 | `/me/drive/root/children`、`/me/drive/items/{id}/children`、`/drives/{d}/root/children`、`/drives/{d}/items/{id}/children` | GET | `$top`（既定 200）、`$select` | 200 と driveItem の一覧 |
| ファイルの検索 | `/me/drive/root/search(q='…')`、`/drives/{d}/root/search(q='…')` | GET | q、`$top`、`$select` | 200 と driveItem の一覧 |
| ファイルの情報 | `/me/drive/items/{id}`、`/drives/{d}/items/{id}` | GET | `$select` | 200 と driveItem |
| ファイルの内容 | `…/items/{id}/content` | GET | — | **302 と、事前に認証済みのダウンロード URL（別のドメイン）**。転送先には Authorization を付けない |
| アップロード | `…/items/{parent-id}:/{name}:/content` | PUT | 本文はバイナリ。`@microsoft.graph.conflictBehavior` は URL に付ける（PUT の既定は replace） | 201 と driveItem。上限 250 MB |
| フォルダーの作成 | `…/items/{parent-id}/children` | POST | name、folder、`@microsoft.graph.conflictBehavior`（fail を明示する） | 201 と driveItem。同じ名前があれば 409 |
| 名前の変更・移動 | `…/items/{id}` | PATCH | name、parentReference.id | 200 と driveItem。ドライブをまたいだ移動はできない |
| 削除 | `…/items/{id}` | DELETE | — | 204（ごみ箱に移る） |
| サイトの検索 | `/sites?search={q}` | GET | search | 200 と site の一覧。`$top` に対応するかは未確認 |
| サイトのドライブの一覧 | `/sites/{id}/drives` | GET | `$top`、`$select` | 200 と drive の一覧 |

**Teams**

| オペレーション名 | エンドポイント | メソッド | 主要パラメータ | レスポンス概要 |
|---|---|---|---|---|
| チャットの一覧 | `/me/chats` | GET | `$top`（最大 50） | 200 と chat の一覧 |
| チャットのメッセージ | `/chats/{id}/messages` | GET | `$top`（最大 50） | 200 と chatMessage の一覧 |
| チャットへの投稿 | `/chats/{id}/messages` | POST | body（contentType、content） | 201 と chatMessage |
| 参加しているチーム | `/me/joinedTeams` | GET | **OData の引数は一切使えない** | 200 と team の一覧 |
| チャネルの一覧 | `/teams/{id}/channels` | GET | `$filter`、`$select` だけ（`$top` は書かれていない） | 200 と channel の一覧 |
| チャネルのメッセージ | `/teams/{t}/channels/{c}/messages` | GET | `$top`（既定 20、最大 50） | 200 と chatMessage の一覧（返信は含まない） |
| 返信の一覧 | `…/messages/{id}/replies` | GET | `$top`（最大 50） | 200 と chatMessage の一覧 |
| チャネルへの投稿 | `/teams/{t}/channels/{c}/messages` | POST | body | 201 と chatMessage |
| 返信 | `…/messages/{id}/replies` | POST | body | 201 と chatMessage |

**一覧で返す項目と、Graph の項目の対応**（要件 3-0「一覧で返す項目」）

| ツール | Graph の項目（`$select` に使えるものは使い、使えない一覧は受け取った後に項目を絞る） |
|---|---|
| メールフォルダーの一覧 | id、displayName、parentFolderId、childFolderCount、unreadItemCount、totalItemCount |
| メールの一覧 | id、subject、from、receivedDateTime、isRead、flag、hasAttachments、bodyPreview |
| 予定の一覧 | id、subject、start、end、isAllDay、location、organizer、responseStatus、isCancelled、bodyPreview |
| ファイルの一覧・検索 | id、name、folder、file、size、lastModifiedDateTime、webUrl、parentReference |
| サイトの検索 | id、displayName、name、webUrl、description |
| サイトのドライブ | id、name、driveType、webUrl |
| チャットの一覧 | id、topic、chatType、lastUpdatedDateTime、webUrl |
| 参加しているチーム | id、displayName、description（`$select` は使えない） |
| チャネルの一覧 | id、displayName、description、membershipType |
| Teams のメッセージの一覧 | id、replyToId、createdDateTime、lastModifiedDateTime、from、body、messageType |

出典（各ページ `https://learn.microsoft.com/graph/api/<名前>?view=graph-rest-1.0`）：user-get、user-list-mailfolders、mailfolder-list-childfolders、user-list-messages、mailfolder-list-messages、message-get、message-list-attachments、user-post-messages、message-update、user-sendmail、message-send、message-reply、message-replyall、message-forward、message-move、message-delete、user-list-calendarview、event-get、user-post-events、event-update、event-delete、event-accept、event-tentativelyaccept、event-decline、driveitem-list-children、driveitem-search、driveitem-get、driveitem-get-content、driveitem-put-content、driveitem-post-children、driveitem-update、driveitem-move、driveitem-delete、site-search、drive-list、chat-list、chat-list-messages、chat-post-messages、user-list-joinedteams、channel-list、channel-list-messages、chatmessage-list-replies、channel-post-messages、chatmessage-post-replies

## 4. 連携先のデータ構造

Graph はデータベースではない（REST の API）。本システムが扱うエンティティと、Graph を通した操作の可否は次のとおり。

| エンティティ名 | Create | Read（一覧） | Read（詳細） | 検索 | Update | Delete | 備考 |
|---|---|---|---|---|---|---|---|
| 利用者のプロフィール（user） | × | × | ○ | × | × | × | — |
| メールフォルダー（mailFolder） | × | ○ | × | × | × | × | 一覧は階層ごと |
| メール（message、attachment） | ○ | ○ | ○ | ○ | ○ | ○ | 作成は下書き。送信・返信・転送・移動を含む。添付は一覧だけ |
| 予定（event） | ○ | ○ | ○ | × | ○ | ○ | 一覧は期間の指定が必須。更新に招待への返答を含む |
| ファイル・フォルダー（driveItem） | ○ | ○ | ○ | ○ | ○ | ○ | 作成はアップロードとフォルダーの作成 |
| SharePoint サイト（site、drive） | × | ○ | × | ○ | × | × | 一覧はサイトのドライブ |
| Teams のチャット（chat） | × | ○ | × | × | × | × | — |
| Teams のチームとチャネル（team、channel） | × | ○ | × | × | × | × | — |
| Teams のメッセージ（chatMessage） | ○ | ○ | × | × | × | × | 作成は投稿と返信 |

## 5. 制限事項

| 項目 | 内容 | 出典 |
|---|---|---|
| スロットリング（共通） | 429 と `Retry-After`（秒）。その秒数を待ってから再試行する。無ければ指数バックオフ。すぐの再試行も回数に数えられる | throttling |
| Outlook（メール・予定表） | アプリとメールボックスの組ごとに、10,000 要求 / 10 分、**同時 4 要求まで**、アップロード 150 MB / 5 分 | throttling-limits |
| Teams | 要求の種類ごとに、アプリ全体・アプリとテナント・リソースごと・利用者ごとの上限がある。投稿とチャットの一覧は**利用者ごとに 1 要求 / 秒** | throttling-limits |
| OneDrive・SharePoint | 429 と 503 の両方に `Retry-After` が付く。利用者ごとに 3,000 要求 / 5 分。委任権限での検索は利用者ごとに 10 要求 / 秒 | SharePoint のスロットリングのページ |
| ページング | `@odata.nextLink` の URL を丸ごとそのまま使う（中身の分からない値として扱う）。Outlook は `$skip` 方式。1 ページが 0 件のこともある。ページングの一貫性（途中でデータが変わったときの扱い）は保証されていない | paging |
| `$top` の上限 | メール 1000、Teams のメッセージとチャット 50、ファイル一覧の既定 200。`/me/joinedTeams` は OData の引数を受け付けない。チャネルの一覧は `$top` が書かれていない。上限を超える `$top` は、無視・丸め・エラーのどれかになる | 各 API ページ、query-parameters |
| 検索 | メールの `$search` は式全体を `"…"` で囲む。結果は最大 1,000 件。`$search` と `$filter` を併用できないという公式の記述は無いが、対応していない組み合わせは黙って無視されることがある | search-query-parameter、known-issues |
| 予定の日時 | calendarView の開始・終了は、値に付いたオフセットで解釈し、オフセットが無ければ UTC として扱う。`Prefer: outlook.timezone` は応答の時刻表示にだけ効く。公式の例は Windows のタイムゾーン名だけで、IANA 名を使えるかは未確認 | user-list-calendarview、datetimetimezone |
| エラーの形 | `{"error":{"code","message","innerError":{…}}}`。判断に使うのは状態コードと `error.code` だけにし、`error.message` は利用者に見せない（多言語化されておらず、予告なく変わる） | errors |
| タイムアウト | 公式の推奨値は無い。大きな `$top` は 504 になることがある（`$select` を併用する） | user-list-messages |
| ファイルの内容 | 302 の転送先は SharePoint の別ドメインで、URL は数分で切れることがある。社内サーバーからそのドメインへ出られるかは未確認（事前確認のまま） | driveitem-get-content |

## 6. モックの説明

方式は **既存モックサーバーツール方式（方式C）**：Microsoft Dev Proxy（v4.0.0、2026-10-29、MIT、公式の Docker イメージ `ghcr.io/dotnet/dev-proxy`）を使う。Graph は状態を持つが、E2E で確かめたいのは「本システムが正しい要求を組み立て、応答とエラーを正しく扱うこと」で、Graph の状態の再現ではないため、固定の応答で足りる。エラーの注入（401・403・404・429・503）が要るので、方式C を選んだ。

- **役割**：Dev Proxy を HTTPS のプロキシとして置き、MCP サーバーから `graph.microsoft.com` と、ファイルのダウンロード先の模擬ドメインへの要求を横取りして、`mock/mocks.json` の応答を返す。
- **応答の種類**：
  - 正常系：ツールごとの代表的な応答
  - 一覧の続き：`@odata.nextLink` 付きの 2 ページ目
  - ファイルの内容：302 と、模擬のダウンロード先
  - エラー系：決まった ID で決まったエラーを返す（`mock/README.md` の表）
  - 429 の後に成功：同じ URL の 1 回目だけ 429 を返す（Dev Proxy の nth）
- **使い方**：
  1. Dev Proxy のコンテナに `mock/` を `/config` としてマウントして起動する。
  2. MCP サーバーのコンテナに `HTTPS_PROXY` で Dev Proxy を指させる。
  3. Dev Proxy のルート証明書を MCP サーバーのコンテナの OS の証明書ストアに入れる（`update-ca-certificates`）。
  4. 詳しい手順は `external/microsoft-graph/mock/README.md` に書く。
- **限界**：
  - Dev Proxy は状態を持たないので、作成した後に一覧へ現れるかは確かめられない。
  - 利用者ごとのデータの分離は、決まった ID への 403 で代わりに確かめるだけになる。
  - これらは real モード（PoC 用テナント）で確かめる。
  - Dev Proxy の nth の回数は、Dev Proxy を再起動しないと戻らない。

## 7. 既存ライブラリの選定結果

**候補と比較**（確認日 2026-10-31）

| 観点 | httpx2 の上の自作の薄いラッパー | msgraph-sdk（Microsoft 公式） | O365（python-o365） | Office365-REST-Python-Client |
|---|---|---|---|---|
| 保守状況 | httpx2 2.16.0（2026-10-21）。リリースが頻繁 | 1.65.0（2026-10-22）。約 2 週間ごと | 2.1.10（2026-09-09） | 3.3.0（2026-10-18）。保守者は実質 1 人 |
| 利用規模 | httpx2 は月間約 2.3 億ダウンロード（FastMCP の依存） | stars 634、月間約 582 万ダウンロード | stars 1,928 | stars 1,729 |
| ライセンス | BSD-3-Clause | MIT | Apache-2.0 | MIT |
| 対象 API のカバレッジ | 要る 41 のエンドポイントだけを書く | v1.0 全体 | 部分的 | 主要分野 |
| 認証方式（取得済みトークンを渡せるか） | 渡せる（ヘッダーを付けるだけ） | 渡せる（`AccessTokenProvider` を自作する。公式の例は無く、issue #501 が未解決） | 難しい（MSAL のトークンキャッシュが前提。OBO 非対応） | 渡せる |
| 型定義 | httpx2 にある。応答のモデルは持たない | 生成コードで型付き | 無い | ある |
| テスタビリティ | `httpx2.MockTransport` で通信なしに試せる。OS の証明書ストアを読むので Dev Proxy をそのまま通せる | httpx 0.28 の `MockTransport` が使える。既定の CA は certifi で、Dev Proxy には `SSL_CERT_FILE` が要る | requests ベースで同期 | requests ベースで同期 |

**推奨理由**：httpx2 の上の自作の薄いラッパーにする。

- 使うエンドポイントは 41 と決まっていて、isdd の「1 対 1 の薄いラッパー」にそのまま合う。
- 依存が増えない。
- 通信なしのテストと Dev Proxy への接続が、追加の設定なしでできる。

**不採用理由**：

- msgraph-sdk：
  - インストール後の容量が約 190 MB。
  - httpx 0.28・aiohttp・opentelemetry が入り、HTTP の層が増える。
  - 取得済みのトークンを渡す方法が公式に無い。
- O365：同期で、OBO で得たトークンの差し込みが難しい。
- Office365-REST-Python-Client：同期で、保守者が 1 人。

**リスク評価**

| 区分 | 内容 |
|---|---|
| 運用 | httpx2 のリリースが頻繁なので、版を固定する（要件の版の固定と同じ） |
| 法務 | BSD-3-Clause で問題なし |
| 保守 | 再試行・ページング・エラーの変換を自分で保守する。Graph の仕様が変わったときは、ラッパーのメソッドを直す |

**ユーザーの最終決定**：httpx2 の上の自作の薄いラッパーにする（2026-10-31、回答 1A）。

## 8. E2E の 2 モード運用

- **mock モード**：
  - MCP サーバーは模擬 Entra ID（`external/entra-id/mock/`）でサインインする。
  - Graph への要求は、`HTTPS_PROXY` で Dev Proxy に通す。
  - 実装時・CI の必須ゴールは、mock モードでの全件通過。
- **real モード**：
  - MCP サーバーは PoC 用テナントの Entra ID と、本物の Graph に接続する。
  - `HTTPS_PROXY` は設定しない。
  - 手動実行だけを必須にする。
- **切り替え**：テスト実行コマンドに渡す環境ファイル（`external/microsoft-graph/e2e/mock.env` か `real.env`）と、docker compose のプロファイルで切り替える。設計で compose の定義を作るときに、このファイルを読む。
- **シンボリックリンク**：E2E 側（プロジェクトの `e2e/`）からは、`external/microsoft-graph/mock/` をシンボリックリンクで参照し、リンクも Git で管理する。
- **テスト環境のスクリプト**：bash を基本にする。証明書の作成などは `external/entra-id/e2e/` の bash スクリプトで行う。

## 未確認の項目（real モードで確かめる）

- `Prefer: outlook.timezone` に IANA 形式の名前（`Asia/Tokyo`）を使えるか
- `/sites?search=` が `$top` に対応するか、`/me/joinedTeams` が `@odata.nextLink` を返すか
- `$search` のときに `@odata.nextLink` が返るか
- メールの削除が「削除済みアイテム」に移るか
- アップロードで上書きしたときの状態コード（200 か 201 か）
- Dev Proxy で 302 を返し、転送先も模擬できるか（ソースでは可能と読めるが、実機では試していない）
- 社内サーバーから `graph.microsoft.com` と SharePoint のダウンロード先へ出られるか
