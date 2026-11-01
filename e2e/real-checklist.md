# real モードの手作業の確認（チェックリスト）

mock モードの自動の E2E（`bash e2e/run.sh mock`）が全件通ってから行う。費用がかかる手順（言語モデルの API）は数百〜数千トークン。

## 社外の確認（Claude の API と、Entra ID・Graph の模擬）

手元の PC で行う。`.env` に `OPENWEBUI_LLM_BASE_URL`・`OPENWEBUI_LLM_API_KEY`・`OPENWEBUI_LLM_MODEL`（Claude の API）を書いておく。人がブラウザと AI ツールで、接続の確認画面と Entra ID の模擬のサインイン画面まで操作する。

- 公開のホスト名は `gateway.localhost`、Entra ID の模擬は `entra.localhost:9443`（`e2e/compose.offsite.yaml`）。macOS とブラウザは `*.localhost` を手元に向け、ブラウザはプロキシに通さないので、hosts の書き換えは要らない。
- 証明書は手元の認証局（`e2e/.work/certs/ca.crt`）が発行したもの。ブラウザでは 3 か所（`gateway.localhost:8443`、`gateway.localhost`、`entra.localhost:9443`）で警告が出るので、承知のうえで進めるか、キーチェーンでこの認証局を信頼させる。
- Entra ID の模擬のサインイン画面では利用者を選ぶ。`Alice Mock`・`Bob Mock` は通常の利用者、`Carol Mock` は割り当ての無い利用者（AADSTS50105 で拒否される）、`Dave Mock` は OBO が失敗する利用者（ツールの呼び出しが失敗する）。

1. 起動する。Open WebUI の初期設定と、確認用の参加者のアカウントの作成までが自動で行われる（M365 のツールの認可はしない）。

   ```bash
   bash e2e/run.sh real-offsite
   ```

2. Open WebUI で確かめる。
   1. `https://gateway.localhost:8443` を開き、起動の表示に出た参加者（`offsite@example.test`）でログインする。
   2. 新しいチャットでモデルが「PoC アシスタント」になっていることを確かめ、ツールのボタンで「Microsoft 365」を有効にする。
   3. 認可を求める表示に従って進める。本システムの「接続の確認」画面で「Open WebUI」を許可し、Entra ID の模擬で `Alice Mock` を選ぶ。Open WebUI に戻ったら、ツールが有効になっていることを確かめる。
   4. 次を依頼する。言語モデルは今日の日付を知らない（Open WebUI の自前のツールを外しているため）ので、日付ははっきり書く。

      | 依頼 | 確かめること |
      |---|---|
      | 「2026 年 11 月 2 日〜8 日の予定を一覧にして」 | 言語モデルが「ツールを探す」でカレンダーのツールを探し、「引数を調べる」の後に「実行する」で予定の一覧のツールを呼ぶ。模擬の予定（2 件）が返る |
      | 「2026 年 11 月 2 日 10 時（日本時間）に 30 分の打ち合わせを入れて」 | 予定を作るツールが呼ばれ、作成の結果（模擬の `mock-event-created`）が返る。模擬は状態を持たず決まった応答（11 月 4 日の「作成した予定」）を返すので、言語モデルが内容の食い違いを指摘しても問題ではない |
      | （確認）チャットのモデルとツール | 既定のモデルが「PoC アシスタント」で、チャットの中のツールの呼び出しが `m365_` で始まる（Open WebUI の自前のカレンダーのツールではない） |

3. Claude Code で確かめる（`docs/connect/claude-code.md` の手順を、社外の確認の値で行う）。
   1. 新しい作業用のディレクトリで、手元の認証局を信頼させて受け口を登録する。

      ```bash
      export NODE_EXTRA_CA_CERTS=<このリポジトリ>/e2e/.work/certs/ca.crt
      claude mcp add --transport http --scope local m365-full https://gateway.localhost/full/mcp
      claude mcp add --transport http --scope local m365 https://gateway.localhost/discovery/mcp
      claude
      ```

   2. Claude Code の中で `/mcp` を開き、`m365-full` と `m365` のそれぞれで認証を始める。ブラウザで「接続の確認」画面を許可し、Entra ID の模擬で `Alice Mock` を選ぶ。
   3. 「M365 の自分のプロフィールを取得して」と頼み、`Alice Mock` のプロフィールが返ることを確かめる（探して使う受け口では、探す → 引数を調べる → 実行するの順に呼ぶ）。
   4. 終わったら `claude mcp remove m365-full` と `claude mcp remove m365` で登録を消す。

4. 止める。

   ```bash
   bash e2e/run.sh real-offsite stop
   ```

## 社内の確認（PoC 用テナントと社内の言語モデル）

PoC 用テナントの値（アプリ ID、シークレット、テナント ID、API のスコープ名）と社内の認証局の証明書を受け取り、社内サーバーに配備してから行う。

### 準備

- 配備した本システムの `.env` に、受け取った値と社内の言語モデルの接続先を書いて `docker compose up -d --build` する。Open WebUI の初期設定は `docs/operations/open-webui.md` のとおり。
- 手元の `.env` に次を書く（自動の部分を手元から実行するため）。
  - `PUBLIC_HOSTNAME`、`E2E_CA_BUNDLE`（社内の認証局の PEM のパス）
  - 利用者 B のデータの ID：`E2E_REAL_OTHER_USER_MESSAGE_ID`、`E2E_REAL_OTHER_USER_EVENT_ID`、`E2E_REAL_OTHER_USER_CHAT_ID`、`E2E_REAL_OTHER_USER_DRIVE_ITEM_ID`（`<ドライブ ID>:<アイテム ID>` の形）

### 自動の部分

```bash
bash e2e/run.sh real
```

テスト用の MCP クライアントがサインインのたびにブラウザで認可の URL を開くので、利用者 A でサインインする（戻りは手元の 127.0.0.1:33418 で受ける）。故意のエラー（429・503 など）、模擬の ID、ログの確認に頼るシナリオは飛ばされる。

### 手作業の部分

| # | 確認 | 手順 | 期待結果 |
|---|---|---|---|
| 1 | Claude Code（全部を出す受け口・探して使う受け口） | `docs/connect/claude-code.md` のとおりに両方を登録し、プロフィールを取る | 本人のプロフィールが返る |
| 2 | Codex（両方） | `docs/connect/codex.md` のとおり | 同上 |
| 3 | OpenCode（両方） | `docs/connect/opencode.md` のとおり | 同上 |
| 4 | Open WebUI | `docs/connect/open-webui.md` のとおりにログインと認可を行い、「来週の予定を一覧にして」「明日 10 時に打ち合わせを入れて」を依頼する | 社内の言語モデルがツールを探してから呼び、M365 に反映される |
| 5 | Entra ID の戻り先 | 1〜4 の間に Entra ID のアプリの戻り先を変えていないことを確かめる | 戻り先は `https://<公開のホスト名>/full/auth/callback` と `…/discovery/auth/callback` の 2 件のまま |
| 6 | 社内ネットワーク（VPN を含む）からの到達 | 社内の PC と VPN の PC から、両方の受け口の保護リソースのメタデータと Open WebUI の `/health` を開く | 200 |
| 7 | 割り当ての無い利用者 | 割り当ての無いアカウントで 1 のサインインを試す | Entra ID で拒否される |
| 8 | AI ツールの設定ファイルにトークンが残らない | 1〜3 の後に、各 AI ツールの設定ファイルと認証の保存先で JWT の形の文字列を探し、発行者と宛先を読む | 発行者が Entra ID の JWT と、宛先が Graph の JWT が無い（本システムが発行した MCP サーバーのトークンだけ） |
| 9 | 代表のツールの M365 への反映 | 2 つの受け口で、メールの送信、予定の作成、OneDrive へのアップロード、SharePoint のリストの項目の作成、Teams のチャットへの投稿を行う | M365 の画面で反映を確かめる（確かめた後に消す） |

結果は、日付・確認した人・各項目の結果（成功・失敗と理由）を記録する。
