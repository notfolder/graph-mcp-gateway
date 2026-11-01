# 調査レポート：ms-365-mcp-server（と FastMCP からの中継）

- 調査日：2026-11-01
- 入力：変更要件定義書 `.history/20261101-relay-ms365-mcp-server/change_requirements.md`（同日に `docs/requirements.md` へ反映済み）
- 事前確認：`precheck_report.md`
- 調べ方：ソース（ms-365-mcp-server 0.178.0、コミット `6f862af`。FastMCP 4.1.4）を読み、使い捨てのコンテナで実測した。本物の Graph・Entra ID には接続していない。行番号は各ソースのもの

## 1. システム概要

| 項目 | 内容 |
|---|---|
| 名前と役割 | ms-365-mcp-server（Softeria、Node.js、MIT）。Microsoft Graph を呼ぶ MCP のツールを提供する。本システムでは、FastMCP の OAuth プロキシと中継の後ろで、要求ごとに渡される利用者の Graph 用のトークンで Graph を呼ぶ |
| 版 | 0.178.0（公式イメージ `ghcr.io/softeria/ms-365-mcp-server:0.178.0`、Node v24、root でない利用者で動く） |
| API の種類 | MCP（Streamable HTTP、`POST /mcp`）。セッションを持たない |
| 公式ドキュメント | https://github.com/Softeria/ms-365-mcp-server （README、確認日 2026-11-01） |

本システムでの置き方は 2 つ（受け口ごと）。

| 受け口 | 起動の引数 | ツールの一覧 |
|---|---|---|
| 全部を出す方 | `--http 3000 --org-mode` | 173 ツール（12 権限で 175 から 2 つ外す）、約 0.95 MB |
| 探して使う方 | `--http 3000 --org-mode --discovery` | 3 ツール＋直接出すツール。探せる範囲は全部を出す方と同じ |

## 2. 認証・接続情報

| 項目 | 内容 |
|---|---|
| 中継からの認証 | `Authorization: Bearer <利用者の Graph 用のトークン>`。ms-365-mcp-server はトークンの期限だけを確かめ（期限切れは 401。`exp` が無いトークンと JWT でないトークンは通す）、署名は確かめずにそのトークンで Graph を呼ぶ（`src/lib/microsoft-auth.ts:43-149`） |
| トークンが無い要求 | `initialize`・`tools/list` を含めて 401（実測）。`MS365_MCP_ALLOW_UNAUTHENTICATED_DISCOVERY=true` にすると、発見系の要求（`initialize`、`notifications/initialized`、`tools/list`、`prompts/list`、`resources/list`、`ping`）だけトークン無しで通す。`tools/call` は通さない（`src/cli.ts:145-147, 477-482`、issue #513） |
| 要求の作法 | `POST /mcp` には `Accept: application/json, text/event-stream` が要る（片方だと 406）。`GET /mcp` は 405。`Mcp-Session-Id` は発行しない |
| 自身の OAuth の受け口 | `--http` で何も設定しなくても有効になり、全体を止める設定は無い。止められるのは動的な登録（`MS365_MCP_DISABLE_DCR=true`）だけ。`MS365_MCP_CLIENT_ID` を渡さないと、Softeria の公開アプリと `common` テナントへのサインインの経路になる。`/revoke`・`/token` は Microsoft のログイン先へ外向きの接続を始めうる（`src/server.ts:547-737, 915, 1059-1064`、`src/cli.ts:444-457`、issue #387） |
| ヘルスチェック | 専用の受け口は無い。`GET /` が 200。イメージには busybox の `wget` がある（`wget -q -O- http://127.0.0.1:3000/`）。curl は無い |
| 環境変数 | 7 章 |

### 中継の作り（FastMCP 4.1.4 から呼ぶ側）

| 項目 | 結論 | 根拠 |
|---|---|---|
| 要求ごとのクライアント | `ProxyProvider(client_factory, cache_ttl=...)` に非同期の関数を渡せる。関数の中で `get_access_token().token`（OAuth プロキシの下では利用者の Entra の上流トークン）を取り、OBO で Graph 用のトークンに替え、`ProxyClient(StreamableHttpTransport(url, headers={"Authorization": ...}), forward_incoming_headers=False)` を返す | `fastmcp/server/providers/proxy.py:80, 346-351, 887-916`、`oauth_proxy/proxy.py:2169-2360` |
| AI ツールのトークンの扱い | transport に設定した `Authorization` が、転送されるヘッダーより優先され、置き換わる（実測で、AI ツールのトークンは中継先に届かなかった）。ただし `ProxyClient` は既定で他の受信ヘッダーを転送するので、`forward_incoming_headers=False` にする。トークンは `auth=` ではなく `headers` で渡す | `fastmcp/client/dependencies.py:6-34`、`server/dependencies.py:600-662` |
| 中継先への要求の回数 | 呼び出しのたびに `initialize` → `notifications/initialized` → 本体の 3 要求。ツールの一覧はプロセスの中で全員共通にキャッシュするが、AI ツールから `tools/list` が来るたびに中継先から取り直す。`tools/call` はキャッシュから名前を引き、切れていれば一覧を取り直す。MCP の新しい版（2026-07-28）で通信する AI ツールが引数付きで呼ぶと、MCP SDK の検査のために一覧の取り直しが 1 回増える | `proxy.py:836-953`、MCP SDK `_streamable_http_modern.py:285-371` |
| 一覧の大きさ | FastMCP の既定（`dereference_schemas=True`）では、全部を出す方の一覧が 947 KB から 1,353 KB に膨らみ、受け取りの上限が 1 MiB の MCP クライアント（Python の MCP SDK の SSE）で失敗した。`dereference_schemas=False` か `json_response=True` で通る | 実測、`server.py:340, 520` |
| エラーの伝わり方 | ms-365-mcp-server の `isError: true` はそのまま届く。`FastMCP`＋`ProxyProvider` では、一覧の取得時の中継先の停止や OBO の失敗が「ツール 0 個」に化ける（要件で「エラーとして返す」と決めた）。`FastMCPProxy` を使うと、OBO の例外の文言が `mask_error_details` に関係なく届く | `proxy.py:457-465`、`server.py:1552-1564`、実測 |
| OBO | `AzureProvider.get_obo_credential(user_assertion=...)` → `get_token(*scopes)`。キャッシュはプロセスのメモリの中（利用者のトークンごとの LRU 128 件と MSAL のキャッシュ）で、台ごと。要求の権限は 12 権限を並べるか `.default`（Microsoft の文書では OBO に `.default` が必要とある）。どちらでも、トークンには同意済みの権限が全部入る | `fastmcp/server/auth/providers/azure.py:216-228, 656-722, 859-940`、https://learn.microsoft.com/en-us/entra/identity-platform/scopes-oidc |
| OAuth プロキシを 2 つにする構成 | (a) プロセスを 2 つにし、`base_url` を `https://<host>/full` と `https://<host>/discovery` にして、nginx でパスを剥がす。保護リソースのメタデータ（`/.well-known/oauth-protected-resource/full/mcp`）はドメインの直下に出るので剥がさずに転送し、認可サーバーのメタデータ（パスを挿入した形）は書き換えて転送する。(b) 1 つのプロセスに 2 つの FastMCP を `Mount` し、`get_well_known_routes` と `combine_lifespans` で載せる。どちらも実測で成り立った（ASGI で確認。実際の nginx では未確認） | `auth.py:489-509, 1138-1205`、`oauth_proxy/proxy.py:774-797, 895`、https://gofastmcp.com/deployment/http |
| 台数を増やす構成 | `jwt_signing_key` を明示し、`client_storage` を `FernetEncryptionWrapper(RedisStore)` にし、`stateless_http=True`。保管のコレクション名は固定なので、2 つの OAuth プロキシが同じ Redis を使うと名前空間を共有する（`/full` で登録したクライアント ID で `/discovery` の認可が通った）。`PrefixCollectionsWrapper` か Redis の DB 番号で分ける | `oauth_proxy/proxy.py:565-702`、key_value 0.4.6、実測 |
| Open WebUI の戻り先 | FastMCP は、`application_type` が未指定の登録を native として扱い、`http://` の戻り先はループバックだけを許す。Open WebUI の URL は `https://` が必須（実測：`http://open-webui:8080/...` は 400） | `auth/redirect_validation.py:369-424`、`proxy.py:985-1030` |

## 3. オペレーション一覧

ms-365-mcp-server の外向きの API は MCP の 3 つの要求だけ。ツールの中身は Graph の要求に 1 対 1 で対応する（`src/endpoints.json`）。

| オペレーション名 | エンドポイント | メソッド | 主要パラメータ | レスポンス概要 |
|---|---|---|---|---|
| 初期化 | `/mcp`（`initialize`） | POST | プロトコルの版、クライアントの情報 | サーバーの情報。要求ごとに MCP サーバーを作り直す |
| ツールの一覧 | `/mcp`（`tools/list`） | POST | なし | ツールの名前・説明・引数のスキーマ |
| ツールの呼び出し | `/mcp`（`tools/call`） | POST | ツール名、引数 | `content[0].text` に Graph の応答の JSON（字下げ付き）、`_meta.http_status` など。失敗は `isError: true` と `{"error": "Microsoft Graph API error: <状態> <理由> - <Graph の本文>"}` |
| ツールを探す（探して使う方） | `tools/call`（`search-tools`） | POST | `query`、`category`、`limit`（既定 10、最大 50） | `{found, total, tools:[{name, method, path, description}], tip}` |
| 引数を調べる（探して使う方） | `tools/call`（`get-tool-schema`） | POST | `tool_name` | 引数の一覧（場所、必須、スキーマ） |
| 実行する（探して使う方） | `tools/call`（`execute-tool`） | POST | `tool_name`、`parameters`（本文は `body` の下） | 直接呼んだときと同じ形 |

領域ごとの代表のツールと、送る Graph の要求（実測）：

| 領域 | 読み取り | 書き込み |
|---|---|---|
| プロフィール | `get-current-user`：GET `/v1.0/me` | — |
| メール | `list-mail-messages`：GET `/me/messages?$top=` | `send-mail`：POST `/me/sendMail`（202） |
| 予定表 | `get-calendar-view`：GET `/me/calendarView?startDateTime=&endDateTime=` | `create-calendar-event`：POST `/me/events` |
| OneDrive | `list-drives`：GET `/me/drives` → `list-folder-files`：GET `/drives/{d}/items/{i}/children` | `upload-file-content`：PUT `/drives/{d}/items/{i}/content` |
| SharePoint | `search-sharepoint-sites`：GET `/sites?$search=` → `list-sharepoint-site-list-items`：GET `/sites/{s}/lists/{l}/items?$expand=fields` | `create-sharepoint-list-item`：POST `/sites/{s}/lists/{l}/items` |
| Teams | `list-chats`：GET `/me/chats` | `send-chat-message`：POST `/chats/{id}/messages` |
| Excel | `get-excel-range`：GET `/drives/{d}/items/{i}/workbook/worksheets/{ws}/range(address='A1:B2')` | `update-excel-range`：PATCH 同じパス |

パスの引数は符号化して送る（`%2C`、`%3A`、`%40`。`src/graph-tools.ts:2838-2866`）。Excel のツールはブックのセッションに対応していない。

## 4. 連携先のデータ構造

非 DB 系（ms-365-mcp-server はデータを持たず、Graph を呼ぶだけ）。エンティティの一覧と CRUD テーブルは、要件定義書 4-2・4-3 のとおり（外部データの 19 エンティティ。ツールの領域と対応する）。任意の Graph の要求を送る `graph-batch` は、どのエンティティの操作にもなりうる。

## 5. 制限事項

| 項目 | 内容 | 本システムでの扱い |
|---|---|---|
| 要求元ごとの回数の制限 | `/mcp` が IP ごとに毎分 120 回 | `MS365_MCP_RATE_LIMIT_DISABLED=true` で外す（要件） |
| 回路遮断器 | Graph の一時的なエラー（429・503・504・ネットワーク）が再試行の 1 回ごとに数えられ、5 回続くと 30 秒のあいだプロセスの中の全員の Graph の呼び出しを止める。プロセスで 1 つ（`src/lib/graph-resilience.ts:325-338`、実測） | `MS365_MCP_GRAPH_CIRCUIT_DISABLED=true` で無効にする（要件） |
| 再試行 | 429 はすべてのメソッド（`Retry-After` に従い最大 60 秒）、503・504・ネットワークは冪等なメソッドだけ。POST・PATCH の 503・504 は再試行しない。回数は既定 3 回（`MS365_MCP_GRAPH_MAX_RETRIES`）。1 回の要求の制限時間は既定 100 秒（`MS365_MCP_GRAPH_TIMEOUT_MS`） | 要件「Graph の一時的なエラーで再試行する」をこの動きで満たす。中継の側では再試行しない |
| ページネーション | ツールの引数 `fetchAllPages` で全ページをまとめて取る（既定で最大 100 ページ・1 万件）。`$top` の上限は既定で無い | 要件「ツールの応答の大きさの上限」で、`MS365_MCP_MAX_TOP`・`MS365_MCP_MAX_PAGES`・`MS365_MCP_MAX_ITEMS` の値を設計で決める |
| ファイルの中身 | `download-bytes` は既定で上限なし。`MS365_MCP_BLOB_OUTPUT=true` で `MS365_MCP_BLOB_MAX_BYTES`（既定 5 MiB）の上限が効く | 同上 |
| 認証なしの URL | `get-download-url` はファイルを認証なしで取れる短期の URL を返す。`get-upload-url` は HTTP モードでは必ずエラー | どちらも出さない（要件。`ENABLED_TOOLS` などの絞り込みの書き方は設計で決める） |
| ローカルファイル | `download-bytes-to-file`・`upload-attachment-from-file` は HTTP モードの既定で出ない。添付の URL（`/attachment`）も無効 | そのまま |
| エラーの文言 | 403 で本文に `scope`・`permission` を含むと「`--org-mode` で再起動」という案内が付く（`src/graph-client.ts:554-572`）。ネットワークのエラーは原因の無い `fetch failed` | そのまま返す（要件の既知の制限） |
| ログ | 運用のログはファイル（`${MS365_MCP_LOG_DIR:-~/.ms-365-mcp-server/logs}`）にだけ出て、ローテーションは無い。`info` ではツールの引数全体（メールの本文など）と Graph の URL 全体が残る。監査のログ（利用者名を含む）は標準エラー出力に常に出る。トークンは伏せ字にされる（`src/lib/log-redactor.ts`） | `LOG_LEVEL=warn`、`MS365_MCP_AUDIT_LOG=false`（要件「ログに個人のデータを書かない」）。ログの置き場所は設計で決める |
| 処理の費用 | 要求ごとに MCP サーバーを作り直す。中央値は、全部を出す方で `initialize` 13.7 ms・`tools/list` 63 ms・`tools/call` 10 ms、探して使う方で 9〜7 ms。全部を出す方の `tools/list` を繰り返すと、メモリが一時 537 MiB まで上がる | 台数の見積もりと、コンテナのメモリの上限の根拠にする。FastMCP 側で一覧を保持する価値がある |
| 書き込みの確認 | 書き込みのツールに `confirm` 引数がある（`MS365_MCP_REQUIRE_CONFIRM=true` のとき使う） | 使わない |
| 探して使う方の注釈 | `execute-tool` は 1 本で `destructiveHint: true`。AI ツールの「読み取りは確認なしで許す」設定が効かない | 要件はこれに頼らない |

## 6. モックの説明

- ms-365-mcp-server そのものは模擬しない。mock モードでも本物のコンテナを使い、その Graph への要求を Graph の模擬（Dev Proxy、`external/microsoft-graph/mock/`）に通す。中継と ms-365-mcp-server の組み合わせそのものを確かめるため。
- Dev Proxy に通す設定：`NODE_USE_ENV_PROXY=1` と `HTTPS_PROXY` の両方（`HTTPS_PROXY` だけでは Node の `fetch` は守らない）と、Dev Proxy のルート証明書を `NODE_EXTRA_CA_CERTS` で渡す（OS の証明書の置き場は Node に効かず、root でないので `update-ca-certificates` も実行できない）。実測で通った。
- 別の方法として `MS365_MCP_GRAPH_BASE_URL` で Graph の宛先を模擬の HTTP サーバーに向けられる。ただし Dev Proxy は普通のサーバーではないので使えず、異常の注入のために Dev Proxy を続けて使う。
- 回路遮断器を無効にしないと、異常系のテスト（503 など）の後のテストが 30 秒失敗する。

## 7. 必要な環境変数（本システムで使うもの）

| 変数 | 用途 | 区分 |
|---|---|---|
| `MS365_MCP_ORG_MODE=true` | Teams・SharePoint のツールを含める | 必須 |
| `MS365_MCP_ALLOWED_SCOPES` | 依頼資料 P-5 の 12 権限（空白区切り）で出すツールを絞る | 必須 |
| `ENABLED_TOOLS` または `ENABLED_TOOLS_FILE` | 出さない 2 ツールを外す（正規表現） | 必須 |
| `MS365_MCP_RATE_LIMIT_DISABLED=true` | 回数の制限を外す | 必須 |
| `MS365_MCP_GRAPH_CIRCUIT_DISABLED=true` | 回路遮断器を無効にする | 必須 |
| `MS365_MCP_DISABLE_DCR=true` | 動的な登録の受け口を止める | 必須 |
| `LOG_LEVEL=warn`、`MS365_MCP_AUDIT_LOG=false`、`MS365_MCP_LOG_DIR` | ログに個人のデータを書かない。置き場所 | 必須 |
| `MS365_MCP_EAGER_TOOLS` | 直接出すツール（カンマ区切り、完全一致。探して使う方だけ） | 任意（最初は空） |
| `MS365_MCP_MAX_TOP`、`MS365_MCP_MAX_PAGES`、`MS365_MCP_MAX_ITEMS`、`MS365_MCP_BLOB_OUTPUT`、`MS365_MCP_BLOB_MAX_BYTES` | ツールの応答の大きさの上限 | 必須（値は設計で決める） |
| `MS365_MCP_GRAPH_MAX_RETRIES` | 再試行の回数 | 任意（既定 3） |
| `MS365_MCP_ALLOW_UNAUTHENTICATED_DISCOVERY` | 一覧の取得をトークン無しで行う場合 | 設計で決める |
| `NODE_USE_ENV_PROXY=1`、`HTTPS_PROXY`、`NODE_EXTRA_CA_CERTS` | mock モードで Dev Proxy に通す | mock モードだけ |

渡さないもの：`MS365_MCP_CLIENT_ID`・`MS365_MCP_CLIENT_SECRET`・`MS365_MCP_TENANT_ID`、`MS365_MCP_OBO`、`MS365_MCP_OAUTH_TOKEN`、ローカルファイルと添付の URL の設定。`--http` と `--discovery` は環境変数が無いので、compose の `command` で渡す。秘密情報は無い。

## 8. 既存ライブラリの選定結果（中継の作り方）

| 項目 | FastMCP の中継（`ProxyProvider`＋`ProxyClient`） | MCP の Python SDK で中継を自作 | 汎用の MCP のプロキシ（mcp-proxy など） |
|---|---|---|---|
| メンテナンス状況 | 活発（4.1.4、2026-10 時点の最新） | 活発（2.3.0） | プロジェクトによる |
| 利用実績 | 多い（FastMCP 本体） | 多い | 少〜中 |
| ライセンス | Apache 2.0 | MIT | 多くは MIT |
| 必要な機能（要求ごとに利用者の Graph 用のトークンを付ける、OAuth プロキシと同じプロセスで OBO を呼ぶ） | すべて満たす（実測） | 作れば満たすが、受け口・転送・一覧の扱いを自分で書く | stdio と HTTP の橋渡しが中心で、要求ごとの認証の差し替えに向かない |
| 認証方式 | `AzureProvider` と同じプロセスで使える | 自分で組む | 対応しない |
| 型定義 | あり | あり | プロジェクトによる |
| テスタビリティ | ASGI のまま試せる（実測） | 同じ | 外部プロセス |

- 推奨：FastMCP の中継。OAuth プロキシと同じ部品で、必要な機能が揃っているため。
- 不採用の理由：SDK での自作は、FastMCP が持つ中継を書き直すことになる。汎用のプロキシは利用者ごとの認証に向かない。
- リスク：運用（一覧の取り直しと 1 MiB の上限、`dereference_schemas` の設定を誤ると大きな一覧が取れない）、法務（なし）、保守（FastMCP の版が上がると中継の内部の動きが変わりうる。版を固定する）。
- ユーザーの最終決定：推奨どおり採用する（ユーザー回答、2026-11-01）。
- ms-365-mcp-server を呼ぶための独自の連携ライブラリは置かない（`../src/README.md`）。

## 9. E2E の 2 モード運用

- mock モード：`../e2e/mock.env`。Graph への要求を Dev Proxy に通す。実装時・CI の必須ゴールは mock モードの全件通過。
- real モード：`../e2e/real.env`。本物の Graph に直接つなぐ。手動実行だけを必須にする。
- 切り替え：テスト実行コマンドに渡す環境ファイルと、docker compose のプロファイル（詳細設計で定義）。

## 10. 確かめられなかったこと

- `upload-file-content` で、`root:/a.txt:` の形のパスを符号化して送ったものを、本物の Graph が受け付けるか（新しいファイルの作成の手順に関わる。real モードで確かめる）。
- Claude Code・Codex・OpenCode・Open WebUI が、MCP のどの版で通信するか（新しい版では、引数付きの呼び出しのたびに一覧の取り直しが増える）。
- 本物の OBO（模擬の Entra ID を含む）を、中継の関数から呼んだときの動き。
- 実際の nginx での、2 つの OAuth プロキシの振り分け。
- 全部を出す方の一覧の大きさが、事前確認（985,980 バイト）と今回（946,601 バイト）で約 4% 違う原因。
