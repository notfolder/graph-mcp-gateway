# tasks.md：ms-365-mcp-server を中継する共有 MCP サーバーの実装

- 入力：`docs/requirements.md`（2026-11-01 改訂）、`docs/detail_design.md`（2026-11-01 作り直し）
- 実装スキル（isdd-traceable-coding）は上から順に実行する。各タスクの設計 ID は、実装時に `docs/trace_map.md` に登録する行の手がかり。
- 旧版の tasks.md（ツールを自作する前提）は 2026-11-01 に消した。

---

## 実装開始前の必須固定タスク

### 0. isdd-setup の導入確認

- 内容：`scripts/isdd/check.sh` が無ければ `isdd-setup` を実行して、対応表チェックを導入する。渡す値は、実行形態「コンテナ（docker compose）」、認証「あり（Entra ID の SSO を OAuth プロキシで中継。Open WebUI は自分のアカウント）」、外部連携「あり（Entra ID、ms-365-mcp-server、Microsoft Graph、言語モデル）」、ソースのディレクトリ `src` と `external/open-webui/src`。
- 完了条件：`bash scripts/isdd/check.sh` が実行でき、`scripts/isdd/completeness.json` の実行形態・認証・外部連携が詳細設計書と一致している。
- 検証：`bash scripts/isdd/check.sh` を実行し、`scripts/isdd/completeness.json` を設計書の第 1・6 章と見比べる。

---

## 実装タスク

### 1. プロジェクトの骨組みとイメージ

- 設計 ID：`DS-MD-PACKAGE-OP-DOCKER-COMPOSE-STARTUP`、`DS-OP-CONTAINER-IMAGES-NF-PINNED-VERSIONS-WITH-MS365-AND-OPEN-WEBUI`、`DS-OP-ENV-SETTINGS-NF-CONFIGURABLE-SETTINGS-WITH-RELAY`
- 内容：
  - `pyproject.toml`（Python 3.14、`fastmcp[azure]==4.1.4`、aiohttp、py-key-value-aio の Redis の追加分。開発用に pytest 9.2.0、pytest-asyncio 1.4.1）と `uv.lock`。`external/open-webui/src/openwebui_api` をパッケージに含める。
  - `Dockerfile`（設計書 9-1 のとおり。runtime 段と test 段、root でない利用者、`FASTMCP_HOME=/data`）。
  - `src/graph_mcp_gateway/__init__.py`（空）。
  - `.env.sample` に、設計書 9-3 の秘密情報と必須の値の名前を、説明とダミーの値で足す（言語モデルの 3 つは既にある）。
- 完了条件：`docker build --target runtime .` と `docker build --target test .` が通る。`uv.lock` がある。`.env.sample` に 9-3 の必須の名前がすべてある。
- 検証：上の 2 つの build を実行する。`.env.sample` と 9-3 の表を見比べる。

### 2. 設定

- 設計 ID：`DS-MD-CONFIG-NF-CONFIGURABLE-SETTINGS-WITH-RELAY`、`DS-CL-SETTINGS-NF-CONFIGURABLE-SETTINGS-WITH-RELAY`、`DS-FN-SETTINGS-FROM-ENV-NF-CONFIGURABLE-SETTINGS-WITH-RELAY`
- 内容：`src/graph_mcp_gateway/config.py` に `Settings` と `from_env` を、設計書 9-3 の「中継」の表の規則どおりに作る。単体テスト（設計書 8-1 の「設定」の行）を `tests/unit/` に書く。
- 完了条件：8-1 の「設定」の確かめることを、すべて単体テストで確かめて通る。
- 検証：`docker compose --profile test run --rm unit`（タスク 7 の前は `uv run pytest tests/unit`）。

### 3. 認証と保管先の組み立て

- 設計 ID：`DS-MD-AUTH-FT-RELAY-SIGN-IN`、`DS-FN-BUILD-AUTH-PROVIDER-FT-RELAY-SIGN-IN`、`DS-FN-BUILD-CLIENT-STORAGE-DT-AUTH-STATE-STORAGE`、`DS-SC-OAUTH-PROXY-STATE-DT-AUTH-STATE-STORAGE`
- 内容：`src/graph_mcp_gateway/auth.py` に `build_auth_provider` と `build_client_storage` を作る（設計書 5-2）。保管先は Redis の URL があるときだけ、受け口ごとの前置きと Fernet の暗号化で包む。単体テスト（8-1 の「認証」）を書く。
- 完了条件：8-1 の「認証」の確かめることが通る。
- 検証：単体テストを実行する。

### 4. 中継（Graph 用のトークンの交換と中継のクライアント）

- 設計 ID：`DS-MD-RELAY-FT-RELAY-MCP-REQUESTS`、`DS-CL-GRAPH-TOKEN-EXCHANGER-FT-EXCHANGE-GRAPH-TOKEN-FOR-RELAY`、`DS-CL-RELAY-CLIENT-FACTORY-FT-RELAY-MCP-REQUESTS`、`DS-FN-EXCHANGE-GRAPH-TOKEN-FT-EXCHANGE-GRAPH-TOKEN-FOR-RELAY`、`DS-FN-CREATE-RELAY-CLIENT-FT-RELAY-MCP-REQUESTS`、`DS-SC-RELAY-MEMORY-ONLY-DT-NO-M365-DATA-RETENTION-IN-RELAY`
- 内容：`src/graph_mcp_gateway/relay.py` に `GraphTokenExchanger` と `RelayClientFactory` を作る（設計書 5-1・5-2）。トークンは transport の `headers` で渡し、`ProxyClient` は受信したヘッダーを転送しない設定にする。中継のデータをファイル・ログに書かない。単体テスト（8-1 の「中継」）を書く。
- 完了条件：8-1 の「中継」の確かめることが通る。
- 検証：単体テストを実行する。

### 5. サーバーの組み立てと起動

- 設計 ID：`DS-MD-SERVER-UI-MCP-FULL-ENDPOINT`、`DS-FN-CREATE-SERVER-UI-MCP-FULL-ENDPOINT`、`DS-MD-MAIN-OP-DOCKER-COMPOSE-STARTUP`、`DS-FN-MAIN-OP-DOCKER-COMPOSE-STARTUP`、`DS-IF-MCP-FULL-ENDPOINT-UI-MCP-FULL-ENDPOINT`、`DS-IF-MCP-DISCOVERY-ENDPOINT-UI-MCP-DISCOVERY-ENDPOINT`、`DS-IF-OAUTH-ENDPOINTS-UI-OAUTH-ENDPOINTS-BY-MCP-ENDPOINT`、`DS-IF-ENTRA-ID-EX-SIGN-IN-WITH-ENTRA-ID`、`DS-IF-ENTRA-OBO-EX-EXCHANGE-TOKEN-WITH-ENTRA-OBO`、`DS-IF-MS365-MCP-SERVER-EX-RELAY-TO-MS365-MCP-SERVER`、`DS-SC-NO-DATABASE-DT-NO-DATABASE-IN-RELAY`
- 内容：`src/graph_mcp_gateway/server.py` に `create_server`（失敗の扱い「raise」、`dereference_schemas` 無効、`mask_error_details` 有効、`ProxyProvider` の一覧のキャッシュ 3600 秒）、`__main__.py` に `main`（JSON の応答、セッションを持たない動作は設定のときだけ）を作る。単体テスト（8-1 の「サーバー・起動」）と、結合テスト（8-1 の「中継」「中継のためのトークンの取得」「2 つの受け口」）を `tests/integration/` に書く。
- 完了条件：8-1 の「サーバー・起動」と結合テストの 3 行がすべて通る。
- 検証：単体・結合テストを実行する。

### 6. Open WebUI の初期設定

- 設計 ID：`DS-MD-OPEN-WEBUI-SETUP-OP-OPEN-WEBUI-SETUP`、`DS-FN-CONFIGURE-OPEN-WEBUI-OP-OPEN-WEBUI-SETUP`、`DS-FN-ADD-OPEN-WEBUI-USERS-FT-MANAGE-OPEN-WEBUI-ACCOUNTS`、`DS-FN-SETUP-MAIN-OP-OPEN-WEBUI-SETUP`、`DS-SC-OPEN-WEBUI-CONNECTION-DT-OPEN-WEBUI-TOOL-SERVER`、`DS-IF-OPEN-WEBUI-API-FT-PROVIDE-POC-OPEN-WEBUI`、`DS-MD-OPEN-WEBUI-API-PACKAGE-FT-PROVIDE-POC-OPEN-WEBUI`、`DS-MD-OPEN-WEBUI-API-CLIENT-FT-PROVIDE-POC-OPEN-WEBUI`、`DS-CL-OPEN-WEBUI-CLIENT-FT-PROVIDE-POC-OPEN-WEBUI`、`DS-CL-OPEN-WEBUI-ERROR-FT-PROVIDE-POC-OPEN-WEBUI`、`DS-FN-OPEN-WEBUI-API-METHODS-FT-PROVIDE-POC-OPEN-WEBUI`
- 内容：`src/graph_mcp_gateway/openwebui_setup.py` に `configure_open_webui`、`add_open_webui_users`、`main` を作る（設計書 4-2・5-2）。連携ライブラリ `external/open-webui/src/openwebui_api/`（作成済み）を使い、足りないメソッドがあれば 1 対 1 の形で足す。単体テスト（8-1 の「Open WebUI の初期設定」「Open WebUI の連携ライブラリ」）と結合テスト（「Open WebUI の初期設定」）を書く。
- 完了条件：8-1 の該当する行がすべて通る。
- 検証：単体・結合テストを実行する。

### 7. compose と受け口の設定

- 設計 ID：`DS-OP-COMPOSE-STARTUP-OP-DOCKER-COMPOSE-STARTUP`、`DS-OP-INITIALIZATION-OP-DOCKER-COMPOSE-STARTUP`、`DS-OP-GATEWAY-TLS-OP-SERVER-CERTIFICATE`、`DS-OP-GATEWAY-ROUTING-UI-OAUTH-ENDPOINTS-BY-MCP-ENDPOINT`、`DS-OP-MS365-CONTAINERS-FT-EXPOSE-MS365-MCP-TOOLS`、`DS-OP-SCALE-OUT-NF-SCALE-OUT-RELAY-AND-MS365`、`DS-OP-OPEN-WEBUI-CONTAINER-FT-PROVIDE-POC-OPEN-WEBUI`、`DS-OP-LOGGING-OP-NO-PERSONAL-DATA-IN-LOGS`、`DS-SC-OPEN-WEBUI-DATA-DT-OPEN-WEBUI-CHAT-RETENTION`、`DS-SC-M365-RESOURCES-DT-M365-USER-PROFILE`、`DS-IF-MS365-GRAPH-EX-CALL-GRAPH-FROM-MS365-MCP-SERVER`、`DS-IF-LANGUAGE-MODEL-EX-CALL-LANGUAGE-MODEL`
- 内容：`compose.yaml`（設計書 8-3 の `compose.yaml` の行のサービス、9-3 の値、Graph の権限の一覧を 1 か所の YAML のアンカーに、ms-365-mcp-server の共通の定義、台数の変数、ボリューム、ヘルスチェック）と `deploy/nginx/default.conf.template`（9-1 の受け口の振り分けと TLS、8443 番の WebSocket）を作る。
- 完了条件：手元の自己署名の証明書と模擬の値で `docker compose up -d` が通り、両方の受け口の保護リソースのメタデータ（`https://<ホスト>/.well-known/oauth-protected-resource/full/mcp` と `…/discovery/mcp`）と、認可サーバーのメタデータ（`/.well-known/oauth-authorization-server/full` と `…/discovery`）が 200 を返し、`resource` と戻り先が設計書のとおり。ms-365-mcp-server の 3000 番がホストから届かない。
- 検証：上を `curl` で確かめる。`docker compose config` で ms-365-mcp-server の環境変数が 9-3 のとおりであることを見る。

### 8. mock モードの基盤

- 設計 ID：`DS-TS-MOCK-ENTRA-ENV-EX-USE-LOCAL-HTTP-MOCK`、`DS-TS-MOCK-GRAPH-ENV-EX-USE-MOCK-SERVER-TOOL`、`DS-TS-MOCK-LLM-ENV-EX-USE-LOCAL-LANGUAGE-MODEL-MOCK`
- 内容：
  - `external/microsoft-graph/mock/mocks.json` と `devproxyrc.json` に CIMD の文書の応答と監視を足す（設計書 8-4 の表）。
  - `e2e/mocks/` に `external/entra-id/mock`、`external/microsoft-graph/mock`、`external/language-model/mock` へのシンボリックリンクを作る（Git で管理する）。
  - `e2e/mock.env`、`e2e/compose.mock.yaml`（`mock-entra`、`devproxy`、`mock-llm`、`e2e`）、`e2e/compose.limits.yaml`、`e2e/compose.eager.yaml`、`e2e/compose.capacity.yaml`、`e2e/compose.multi.yaml` を作る。
  - `e2e/run.sh`（`mock`・`real`・`real-offsite`。8-4 の手順。証明書の作成と 3 つの束、ログの保存）を作る。
- 完了条件：`bash e2e/run.sh mock` が、手順 3 の起動まで通る（全サービスが起動し、Open WebUI の `/health` と両方の受け口のメタデータが 200）。
- 検証：`bash e2e/run.sh mock` を実行する（シナリオが無い段階では起動の確認で止める引数を用意してよい）。

### 9. E2E の補助の部品

- 設計 ID：`DS-TS-KEYLESS-CONNECTION-E2E-TS-VERIFY-KEYLESS-CONNECTION-FROM-ALL-AI-TOOLS`（基盤）、`DS-TS-OPEN-WEBUI-AUTOMATED-E2E-TS-VERIFY-OPEN-WEBUI-AUTOMATED`（基盤）
- 内容：`e2e/support/` に、テスト用の MCP クライアント（DCR と CIMD の登録、認可、確認画面のフォームの送信、`login_hint`、戻りの受け取り、トークンの取得と更新、記録の保存）と、Open WebUI の認可を HTTP で進める部品を作る（設計書 8-3）。
- 完了条件：補助の部品だけで、両方の受け口でのサインインとプロフィールの取得、Open WebUI での認可の完了が mock モードで通る。
- 検証：タスク 10 の最初のシナリオで確かめる。

### 10. E2E のシナリオ（mock モード）

- 設計 ID：`DS-TS-KEYLESS-CONNECTION-E2E-TS-VERIFY-KEYLESS-CONNECTION-FROM-ALL-AI-TOOLS`、`DS-TS-USER-DATA-ISOLATION-E2E-TS-VERIFY-USER-DATA-ISOLATION`、`DS-TS-UNASSIGNED-USER-REJECTED-E2E-TS-VERIFY-UNASSIGNED-USER-REJECTED`、`DS-TS-TOOL-CATALOG-E2E-TS-VERIFY-TOOL-CATALOG-ON-BOTH-ENDPOINTS`、`DS-TS-REPRESENTATIVE-TOOLS-E2E-TS-VERIFY-REPRESENTATIVE-TOOLS-BY-DOMAIN`、`DS-TS-RESPONSE-SIZE-LIMITS-E2E-TS-VERIFY-RESPONSE-SIZE-LIMITS`、`DS-TS-GRAPH-ERRORS-AND-RETRY-E2E-TS-VERIFY-GRAPH-ERRORS-AND-RETRY`、`DS-TS-INVALID-TOKEN-REJECTED-E2E-TS-VERIFY-INVALID-TOKEN-REJECTED`、`DS-TS-MS365-NOT-REACHABLE-E2E-TS-VERIFY-MS365-NOT-REACHABLE`、`DS-TS-TOKEN-REFRESH-E2E-TS-VERIFY-TOKEN-REFRESH`、`DS-TS-NO-TOKEN-EXPOSURE-E2E-TS-VERIFY-NO-TOKEN-EXPOSURE`、`DS-TS-NO-PERSONAL-DATA-IN-LOGS-E2E-TS-VERIFY-NO-PERSONAL-DATA-IN-LOGS`、`DS-TS-SCALE-OUT-E2E-TS-VERIFY-SCALE-OUT`、`DS-TS-RESTART-KEEPS-SIGN-IN-E2E-TS-VERIFY-RESTART-KEEPS-SIGN-IN`、`DS-TS-OPEN-WEBUI-AUTOMATED-E2E-TS-VERIFY-OPEN-WEBUI-AUTOMATED`、`DS-TS-OFFLINE-UNIT-TESTS-E2E-TS-VERIFY-OFFLINE-UNIT-TESTS`、`DS-TS-INTERNAL-NETWORK-ACCESS-NF-INTERNAL-NETWORK-ACCESS`
- 内容：設計書 8-2 の表の各シナリオを `e2e/` に pytest で書き、`e2e/run.sh mock` の手順に組み込む。
- 完了条件：`bash e2e/run.sh mock` で上のシナリオがすべて通る。
- 検証：`bash e2e/run.sh mock` を実行する。

### 11. 1 台あたりの処理量の測定

- 設計 ID：`DS-TS-MEASURE-CAPACITY-E2E-TS-MEASURE-INSTANCE-CAPACITY`
- 内容：`e2e/capacity/measure.py` を作る（設計書 8-2 の手順と報告の形。テスト用の MCP クライアントを使う）。`e2e/run.sh mock` の手順 6 に組み込む。
- 完了条件：`e2e/.work/capacity-report.md` に、4 つの対象の段ごとの値、1 台の処理量、台数の計算式と仮定を入れる欄が出る。ms-365-mcp-server が毎分 120 回を超えても 429 を返さないことが確かめられる。
- 検証：`bash e2e/run.sh mock` を実行し、報告を読む。

### 12. real モードの手順

- 設計 ID：`DS-TS-OPEN-WEBUI-REAL-LLM-E2E-TS-VERIFY-OPEN-WEBUI-WITH-REAL-LANGUAGE-MODEL`、`DS-TS-KEYLESS-CONNECTION-E2E-TS-VERIFY-KEYLESS-CONNECTION-FROM-ALL-AI-TOOLS`（real の部分）、`DS-TS-INTERNAL-NETWORK-ACCESS-NF-INTERNAL-NETWORK-ACCESS`（real の部分）
- 内容：`e2e/real-checklist.md`（社内：3 つの AI ツールと Open WebUI での確認、社内の言語モデル。社外：Claude の API での Open WebUI の確認）と、`e2e/run.sh real`・`real-offsite` の動きを作る。
- 完了条件：`bash e2e/run.sh real-offsite` で、本物の言語モデル（`.env` の Claude の API）につないだ Open WebUI が起動し、チェックリストの社外の手順を実行できる。社内の手順は、PoC 用テナントの値を受け取ったときに実行できる形で書いてある。
- 検証：`bash e2e/run.sh real-offsite` を実行し、チェックリストの社外の手順を 1 回行う（手動。費用は数百〜数千トークン）。

### 13. 手順書

- 設計 ID：`DS-OP-CONNECTION-GUIDES-OP-CONNECTION-GUIDE-FOR-ALL-AI-TOOLS`、`DS-OP-OPEN-WEBUI-SETUP-PROCEDURE-OP-OPEN-WEBUI-SETUP`、`DS-OP-DELETE-OPEN-WEBUI-DATA-OP-DELETE-OPEN-WEBUI-DATA-AT-POC-END`、`DS-OP-INCIDENT-RESPONSE-OP-DOCKER-COMPOSE-STARTUP`
- 内容：`docs/connect/claude-code.md`・`codex.md`・`opencode.md`・`open-webui.md`（設計書 9-1）、`docs/operations/open-webui.md`（初期設定と PoC の終わりの消去）、障害対応の表（設計書 10-3）を `README.md` か `docs/operations/` に書く。
- 完了条件：設計書 9-1 と 10-3 の項目がすべて書いてある。
- 検証：設計書の該当する行と見比べる。

---

## 実装完了確認の必須固定タスク

### 1. 対応表（docs/trace_map.md）の更新

- 内容：実装したファイル・クラス・公開関数を `docs/trace_map.md` に登録する（書式は対応表のルール）。
- 完了条件：`bash scripts/isdd/check.sh --strict` がエラー 0 件・警告 0 件で通る。

### 2. 起動の確認

- 内容：`compose.yaml` があり、`docker compose up` で全サービス（`gateway`、`relay-full`、`relay-discovery`、`ms365-full`、`ms365-discovery`、`open-webui`）が起動することを確かめる。
- 完了条件：起動がエラーなく完了する。

### 3. 単体テスト・結合テストの全件通過

- 内容：`docker compose --profile test run --rm unit` で全件を実行する。
- 完了条件：FAIL が 0 件。失敗したら直して再実行を繰り返す。

### 4. E2E の全件通過

- 内容：`bash e2e/run.sh mock` で全件を実行する。
- 完了条件：FAIL が 0 件。失敗したら直して再実行を繰り返し、全件通過まで続ける。

### 5. README.md の記載

- 内容：`README.md` に「起動方法」の節を書く。認証があるので「初期ユーザー」の情報（受け口は Entra ID の割り当てで決まり初期ユーザーは無いこと、Open WebUI の管理者は環境変数で作られること、参加者のアカウントの作り方）も書く。
- 完了条件：`README.md` を読むだけで、初回の起動から、受け口へのサインインと Open WebUI の管理者のログインまでが完結できる。

### 6. 実装の完了の確認

- 内容：`python3 scripts/isdd/implementation_completeness_checker.py .` を実行する。あわせて、設計書の第 11 章のすべての設計 ID が、対応表・テスト・設定・手順書のどこかで実現されていることを確かめる。
- 完了条件：全項目が OK。
