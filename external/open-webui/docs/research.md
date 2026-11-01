# 調査レポート：Open WebUI（PoC 専用）

- 調査日：2026-11-01
- 入力：変更要件定義書 `.history/20261101-relay-ms365-mcp-server/change_requirements.md`（同日に `docs/requirements.md` へ反映済み）
- 事前確認：`precheck_report.md`
- 調べ方：ソース（v0.12.5、`backend/open_webui/` からの相対パスで書く）を読み、使い捨てのコンテナで実測した。OAuth 2.1 の流れは、Open WebUI → FastMCP 4.1.4 の OAuth プロキシ（TLS）→ Entra ID の模擬で最後まで通した（OBO と Graph は通していない）

## 1. システム概要

| 項目 | 内容 |
|---|---|
| 名前と役割 | Open WebUI v0.12.5。会話の画面と言語モデルへの接続を持つ Web アプリ。言語モデルが選んだツールを、MCP で本システムの探して使う受け口に呼ぶ |
| 本システムでの置き方 | PoC 専用のものを docker compose に入れる（公式イメージ `ghcr.io/open-webui/open-webui:v0.12.5`、約 5.8 GB） |
| API の種類 | REST（JSON）。画面と同じ API を、ログインのトークンで呼べる |
| 公式ドキュメント | https://docs.openwebui.com/features/extensibility/mcp/ 、https://docs.openwebui.com/reference/env-configuration 、https://docs.openwebui.com/license/ （確認日 2026-11-01） |

## 2. 認証・接続情報

| 項目 | 内容 |
|---|---|
| Open WebUI へのログイン | メールアドレスとパスワード。`POST /api/v1/auths/signin` でトークンを得て、`Authorization: Bearer` か Cookie の `token` で使う |
| 管理者の作成 | `WEBUI_ADMIN_EMAIL`・`WEBUI_ADMIN_PASSWORD` を渡すと、利用者が 0 人のときだけ起動時に管理者を作り、利用者自身の登録を止める（`main.py:400-403`） |
| 利用者自身の登録 | `ENABLE_SIGNUP=false` で止まる（`POST /api/v1/auths/signup` が 403、実測）。管理者は `POST /api/v1/auths/add` で利用者を作る。`DEFAULT_USER_ROLE` の既定は `pending` |
| MCP の受け口への認証（OAuth 2.1、DCR） | 管理者が `POST /api/v1/configs/oauth/clients/register?type=mcp` を呼ぶと、Open WebUI のサーバーがメタデータを探し（`initialize` の 401 の `resource_metadata` → RFC 9728 → RFC 8414・OIDC）、DCR を送る。登録の中身は `client_name: "Open WebUI"`、戻り先 `{WEBUI_URL}/oauth/clients/mcp:{接続の ID}/callback`、`grant_types: [authorization_code, refresh_token]`、`application_type: native`。FastMCP が相手だと `token_endpoint_auth_method` は `none` になる。結果は暗号化した `oauth_client_info` として返り、まだ保存されない。`POST /api/v1/configs/tool_servers` で接続先に入れて保存する（一覧を全部置き換える）（`routers/configs.py:182-322`、`utils/oauth.py:426-675`） |
| 利用者ごとの認可 | 利用者がツールを有効にすると `{WEBUI_URL}/oauth/clients/mcp:{ID}/authorize` から始まる。PKCE は S256。`resource` は既定で送る。Open WebUI のサーバーは認可の URL を自分で一度 GET して確かめ、400 以上で `invalid_client` などなら DCR をやり直す。`state` と PKCE の値は Cookie の `owui-session` に入るので、開始から戻り先まで同じ Cookie を持ち回す（`main.py:2890-2948`、`utils/oauth.py:985-1057, 1239-1375`） |
| トークンの更新と保管 | 期限の 5 分前を切ると、リフレッシュトークンで更新する。失敗すると保管したトークンを消し、利用者はもう一度認可する。保管は DB の `oauth_session`（利用者 × 接続ごと、Fernet で暗号化）。鍵は `OAUTH_SESSION_TOKEN_ENCRYPTION_KEY`、無ければ `WEBUI_SECRET_KEY`。クライアントの情報の鍵は `OAUTH_CLIENT_INFO_ENCRYPTION_KEY`、無ければ `WEBUI_SECRET_KEY`。鍵を変えると全部読めなくなる（`utils/oauth.py:301-315, 1086-1237`、`main.py:681-686`） |
| 戻り先の制約 | FastMCP は native の登録で `http://` の戻り先をループバックだけ許す。`WEBUI_URL` は `https://`（またはループバック）が必須（実測：`http://open-webui:8080/...` は 400） |
| サーバー証明書 | 通信ごとに使う HTTP クライアントが違い、2 系統の設定が要る。aiohttp（メタデータ、DCR、認可の URL の確認、更新、言語モデル）と httpx2（MCP の通信）は `AIOHTTP_CLIENT_SSL_CERT_FILE`。authlib（認可の開始のメタデータ、コードとトークンの交換）は `SSL_CERT_FILE`・`SSL_CERT_DIR` だけを見る。`AIOHTTP_CLIENT_SSL_CERT_FILE` だけだと認可で 500（`CERTIFICATE_VERIFY_FAILED`、実測）。`SSL_CERT_FILE` は certifi の代わりになるので、公開の認証局と社内（mock では手元）の認証局をまとめたファイルを渡す（`env.py:560-707`） |
| 環境変数 | 7 章 |

## 3. オペレーション一覧

本システム（初期設定の手順と E2E）が呼ぶもの。連携ライブラリ `../src/openwebui_api/` のメソッドと 1 対 1。

| オペレーション名 | エンドポイント | メソッド | 主要パラメータ | レスポンス概要 |
|---|---|---|---|---|
| 起動の確認 | `/health` | GET | なし | 200 で起動済み |
| ログイン | `/api/v1/auths/signin` | POST | `email`、`password` | トークン、利用者の情報 |
| 利用者自身の登録 | `/api/v1/auths/signup` | POST | `name`、`email`、`password` | 受け付けない設定では 403 |
| 利用者の作成（管理者） | `/api/v1/auths/add` | POST | `name`、`email`、`password`、`role` | 作った利用者 |
| MCP の受け口への DCR（管理者） | `/api/v1/configs/oauth/clients/register?type=mcp` | POST | `url`、`client_id`（接続の ID）、`oauth_scope` | 暗号化した `oauth_client_info` |
| ツールサーバーの一覧 | `/api/v1/configs/tool_servers` | GET | なし | 接続先の一覧 |
| ツールサーバーの保存（管理者） | `/api/v1/configs/tool_servers` | POST | `TOOL_SERVER_CONNECTIONS`（`type: mcp`、`auth_type: oauth_2.1`、`url`、`config.enable`、`config.access_grants`、`info.id`、`info.oauth_client_info`） | 保存した一覧 |
| 使えるツールの一覧 | `/api/v1/tools/` | GET | なし | ツール。MCP の接続先は `authenticated` で認可の状態が分かる |
| 認可の開始 | `/oauth/clients/{mcp:接続の ID}/authorize` | GET | なし | 本システムの OAuth プロキシの `/authorize` への転送 |
| 認可の戻り先 | `/oauth/clients/{mcp:接続の ID}/callback` | GET | `code`、`state` | 307 で `/` へ（サーバー間でトークンを交換して保存する） |
| MCP の接続を切る | `/api/v1/auths/oauth/sessions/{mcp:接続の ID}` | DELETE | なし | — |
| モデルの一覧 | `/api/models` | GET | なし | 使えるモデル。一般の利用者は、公開されたモデルしか見えない |
| モデルの設定の取得（管理者） | `/api/v1/models/model?id=...` | GET | `id` | 設定（公開の範囲を含む）。設定が無ければ 404 |
| モデルの全体の設定（管理者） | `/api/v1/configs/models` | GET・POST | `DEFAULT_MODELS`（新しいチャットの既定のモデル）、`DEFAULT_PINNED_MODELS`、`MODEL_ORDER_LIST` など | 設定。POST は全体を置き換える |
| モデルの設定の更新（管理者） | `/api/v1/models/model/update` | POST | `id`、`base_model_id`、`name`、`meta`、`params` | 更新した設定 |
| モデルの設定の作成（管理者） | `/api/v1/models/create` | POST | `id`、`base_model_id`、`access_grants`、`meta.capabilities` | 作った設定 |
| チャットの作成 | `/api/v1/chats/new` | POST | `chat`（メッセージ ID を含む） | チャットの ID |
| チャットの取得 | `/api/v1/chats/{id}` | GET | なし | 記録。ツールの呼び出しは `output` の `function_call` |
| チャットの削除 | `/api/v1/chats/{id}` | DELETE | なし | — |
| 発言 | `/api/chat/completions` | POST | `model`、`messages`、`chat_id`、`id`、`session_id`、`tool_ids`（`server:mcp:{接続の ID}`）、`stream` | タスクの ID。処理はバックグラウンドで進み、結果はチャットの記録に入る |

公開の範囲：ツールサーバーの接続先もモデルも、`access_grants` が空なら管理者しか使えない。全員に公開するには `[{"principal_type": "user", "principal_id": "*", "permission": "read"}]`、グループに限るなら `principal_type: group`（`utils/access_control/__init__.py:106-213`）。`BYPASS_MODEL_ACCESS_CONTROL=true` でモデルの制限を外す方法もある（実測なし）。

自前のツールの制約（社外の確認で実測、2026-11-01）：自前のツール（カレンダー、現在時刻など）が渡っていると、Claude は依頼に名前の合う自前のカレンダーのツールを選び、M365 のツールを呼ばなかった。モデルの `meta.capabilities.builtin_tools=false` で外すと M365 のツールを使うが、現在時刻のツールも無くなるので、言語モデルは今日の日付を知らない（利用者には日付をはっきり書いてもらう）。

元のモデルの制約（実装時に実測、2026-11-01）：設定（`model` の表の行）の無い元のモデルは管理者だけが使え、それを元にしたモデルの設定を公開しても一般の利用者は使えない（チャットで「Model not found」。`utils/access_control/__init__.py` の `has_base_model_access`）。元のモデルにも設定を作って公開する。また Open WebUI のサーバーのモデルの一覧（`app.state.MODELS`）は `/api/models` を呼んだときに新しくなるので、設定を作った後に一覧を取る。

## 4. 連携先のデータ構造

非 DB 系として扱う（Open WebUI は自分の DB を持つが、本システムは API でだけ触る）。保管の場所は `/app/backend/data`（`webui.db` は SQLite、ほかに `uploads/`、`vector_db/`、埋め込み済みの `cache/`）。イメージにボリュームの宣言は無いので、名前付きボリュームを付ける（ホストのディレクトリを付けると、イメージに埋め込んだモデルが隠れるおそれがある。推定）。

| エンティティ名 | Create | Read（一覧） | Read（詳細） | 検索 | Update | Delete | 備考 |
|---|---|---|---|---|---|---|---|
| アカウント | ○ | ○ | ○ | × | ○ | ○ | 管理者が作る |
| ツールサーバーの接続先 | ○ | ○ | ○ | × | ○ | ○ | 一覧を全部置き換える形で保存する。DCR の結果を含む |
| MCP サーバーのトークン（`oauth_session`） | ○ | × | ○ | × | ○ | ○ | 認可・更新で Open WebUI が書く。暗号化される |
| チャットの記録（`chat`・`chat_message`） | ○ | ○ | ○ | ○ | ○ | ○ | ツールの結果（M365 のデータ）を暗号化せずに持つ。利用者が消せる（`chat.delete` の権限、既定で許可） |
| モデルの設定 | ○ | ○ | ○ | × | ○ | ○ | 公開の範囲を持つ |

## 5. 制限事項

| 項目 | 内容 |
|---|---|
| ツールの一覧の扱い | キャッシュしない。発言のたびに MCP の接続（`initialize` → `tools/list`）をやり直す。ツールの定義は全部そのまま言語モデルに渡り、Open WebUI の自前のツール 29 個も足される（モデルの `meta.capabilities.builtin_tools=false` で外せる）。全部を出す受け口では 1 回の要求が約 945 KB になった（実測。要件で、Open WebUI は探して使う受け口だけにつなぐ） |
| ツールの実行の条件 | チャットの記録（`chat_id`・メッセージ ID・`session_id`）がある要求でだけ実行する。未認可のままツールを選ぶと、通知だけ出てツールなしで続く |
| 時間の上限 | `MCP_INITIALIZE_TIMEOUT`（既定 10 秒、`initialize` と `tools/list`）。ツールの呼び出しは `AIOHTTP_CLIENT_TIMEOUT_TOOL_SERVER`（既定は上限なし。httpx の読み取りの 300 秒はかかる） |
| 付随の要求 | タイトル・タグ・次の質問の候補の生成は、`ENABLE_TITLE_GENERATION`・`ENABLE_TAGS_GENERATION`・`ENABLE_FOLLOW_UP_GENERATION`（既定で有効）で止められる |
| 起動の時間 | 新しい DB で 90〜147 秒（実測 3 回。DB の作成と移行を含む）、既存の DB で 6 秒 |
| 外部への通信 | `OFFLINE_MODE=true` で、モデルの取得、版の更新の確認、依存のインストールを止める。テレメトリはイメージの既定で無効 |
| 接続の確認画面 | 本システムの OAuth プロキシの確認画面に、クライアントの名前「Open WebUI」が出る |
| ライセンス | 「Open WebUI」の名前・ロゴを変えない、消さない。DCR の `client_name` も対象（`utils/oauth.py:574-577`）。表示を変えない構成なら気をつけることは無い |

## 6. モックの説明

- Open WebUI そのものは模擬しない。mock モードでも本物のコンテナを使う。
- 言語モデルは模擬に替える（`external/language-model/mock/`）。Entra ID と Graph は既存の模擬（`external/entra-id/mock/`、`external/microsoft-graph/mock/`）。
- mock モードでも、本システムの OAuth プロキシは TLS が必須（FastMCP は issuer が `https://` でないと起動しない、実測）。Open WebUI には手元の認証局を 2 系統の設定で信頼させる。
- E2E の自動化の手順：ブラウザの自動操作は要らない。Cookie を持ち回す HTTP クライアントだけで進められる（実測）。
  1. Open WebUI を環境変数で起動する（管理者、登録の停止、言語モデルの模擬、オフライン、証明書 2 系統、固定の `WEBUI_SECRET_KEY`、`https://` の `WEBUI_URL`）。
  2. `/health` が 200 になるまで待つ（最大 3 分）。
  3. 管理者でログインし、モデルの設定を作って利用者に公開する。
  4. 管理者が探して使う受け口に DCR で登録し、接続先を保存して利用者に公開する。
  5. 管理者が PoC 参加者のアカウントを作る。利用者自身の登録が 403 になることも確かめる。
  6. 参加者でログインし、`/api/v1/tools/` で未認可を確かめる。
  7. 認可を進める：`/oauth/clients/mcp:{ID}/authorize` から転送を 1 つずつ追う。本システムの接続の確認画面は、HTML のフォームの値（`txn_id`、`csrf_token`）を取って許可を POST する。模擬の Entra ID の認可の URL に `login_hint` を足して画面なしでサインインする。戻り先の後、`/api/v1/tools/` で認可済みを確かめる。
  8. チャットを作り、`CALL <ツール名> <引数>` を含む発言を `chat_id`・`id`・`session_id`・`tool_ids` 付きで送る。
  9. チャットの記録を、アシスタントのメッセージが完了するまで読み直し、ツールの呼び出しが完了したこと、模擬の言語モデルの記録の 2 回目の要求にツールの結果があることを確かめる。
- E2E のクライアントは、Open WebUI を `WEBUI_URL` と同じ origin で呼ぶ。Open WebUI のサーバー自身も、本システムの OAuth プロキシの公開 URL に届く必要がある（compose の中で同じ名前を解決できるようにする）。

## 7. 必要な環境変数

| 変数 | 用途 |
|---|---|
| `WEBUI_URL` | 公開 URL。`https://` にする（OAuth の戻り先の基準） |
| `WEBUI_SECRET_KEY` | ログインのトークンと、保管する OAuth の情報の暗号化の鍵。固定する（秘密情報） |
| `WEBUI_ADMIN_EMAIL`、`WEBUI_ADMIN_PASSWORD`、`WEBUI_ADMIN_NAME` | 起動時に作る管理者（パスワードは秘密情報） |
| `ENABLE_SIGNUP=false`、`DEFAULT_USER_ROLE=user` | 利用者自身の登録を止める。管理者が作る利用者の役割 |
| `OPENAI_API_BASE_URL`、`OPENAI_API_KEY` | 言語モデルの接続先と鍵（`external/language-model/`） |
| `ENABLE_OLLAMA_API=false` | Ollama を使わない |
| `OFFLINE_MODE=true` | 起動時に外部へ取りに行かない |
| `AIOHTTP_CLIENT_SSL_CERT_FILE`、`SSL_CERT_FILE` | 認証局の証明書（2 系統） |
| `ENABLE_TITLE_GENERATION`、`ENABLE_TAGS_GENERATION`、`ENABLE_FOLLOW_UP_GENERATION` | 付随の要求（任意） |
| `MCP_INITIALIZE_TIMEOUT` | MCP の初期化と一覧の取得の時間の上限（任意） |

## 8. 既存ライブラリの選定結果（初期設定と E2E の自動化）

| 項目 | 自作の薄いクライアント（httpx2）＋ Cookie を持ち回す HTTP の要求 | Playwright（ブラウザの自動操作） | Open WebUI の公式の SDK |
|---|---|---|---|
| メンテナンス状況 | 自分で持つ（約 200 行） | 活発 | 公式の Python の SDK は見当たらない |
| 利用実績 | — | 多い | — |
| ライセンス | — | Apache 2.0 | — |
| 必要な機能（管理者の設定、DCR、認可を進める、チャットでツールを実行させる） | すべて満たす（実測。画面を使わずに最後まで通った） | 満たす | — |
| 認証 | ログインのトークンと Cookie | 画面のログイン | — |
| 型定義 | 型ヒントあり | あり | — |
| テスタビリティ | 依存は httpx2 だけ | ブラウザの導入が要り、画面が版で変わると直す必要がある | — |

- 推奨：自作の薄いクライアント（`../src/openwebui_api/`）。ブラウザ無しで最後まで通り、依存が小さいため。
- 不採用の理由：Playwright はブラウザの導入と画面の変化への追従が要り、HTTP だけで足りる。公式の SDK は無い。
- リスク：運用（Open WebUI の API が版で変わると直す必要がある。版を固定する）、法務（なし）、保守（約 200 行を自分で持つ）。
- ユーザーの最終決定：推奨どおり採用する（ユーザー回答、2026-11-01）。

## 9. E2E の 2 モード運用

- mock モード：`../e2e/mock.env`。言語モデルは模擬、Entra ID と Graph も模擬。手順は 6 章のとおり自動で行う。実装時・CI の必須ゴールは mock モードの全件通過。
- real モード：`../e2e/real.env`。社外は模擬の Entra ID・Graph と Claude の API、社内は PoC 用テナントと社内の言語モデルの接続先。手動実行だけを必須にする。
- 切り替え：テスト実行コマンドに渡す環境ファイルと、docker compose のプロファイル（詳細設計で定義）。

## 10. 確かめられなかったこと

- 実際の ms-365-mcp-server を本システムの OAuth プロキシの後ろに置いた構成での、Open WebUI からの通し（今回の OAuth の実測は、試験用の FastMCP のサーバーで行った）。
- 本システムの OAuth プロキシのクライアントの記録が消えたとき（再起動など）に、Open WebUI が DCR を自動でやり直す動き（ソースではやり直す作り）。
- 画面から使うときに、付随の要求を止める設定が効くか。
- `BYPASS_MODEL_ACCESS_CONTROL=true` での公開。
- `/app/backend/data` にホストのディレクトリを付けたときの、埋め込み済みのモデルの扱い。
