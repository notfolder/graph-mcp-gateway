# Microsoft Entra ID の模擬

E2E の mock モードで、Entra ID の代わりにサインイン・トークンの発行・OBO を行う。方式はローカル HTTP サーバー方式（Python で自作）。

## ファイル

| ファイル | 役割 |
|---|---|
| `mock_entra.py` | 模擬サーバー本体（Starlette）。パスは Entra ID の v2 と同じ形（`/{tenant}/oauth2/v2.0/authorize`、`/token`、`/{tenant}/discovery/v2.0/keys`、`/{tenant}/v2.0/.well-known/openid-configuration`） |
| `users.json` | 模擬の利用者 |

## 利用者

| ID | 割り当て | 同意済みの Graph のスコープ | 使うシナリオ |
|---|---|---|---|
| `alice` | あり | 依頼資料 P-5 のすべて | 通常の操作 |
| `bob` | あり | 依頼資料 P-5 のすべて | 利用者ごとのデータの分離（2 人目） |
| `carol` | **なし** | なし | 割り当ての無い利用者（サインインの開始で AADSTS50105 の 403 を返す） |
| `dave` | あり | `User.Read` だけ | OBO の失敗（`User.Read` 以外で AADSTS65001 を返す） |

## 起動のしかた

1. `external/entra-id/e2e/make-certs.sh <出力先> mock-entra mcp-server` で、手元の認証局とサーバー証明書を作る。
2. FastMCP と同じ依存（starlette、uvicorn、PyJWT、cryptography）がある Python で、`python mock_entra.py` を実行する。次の環境変数を渡す。
   - `MOCK_TLS_CERT` と `MOCK_TLS_KEY`：上で作った `mock-entra.crt` と `mock-entra.key`
   - `MOCK_PORT`：既定は 8443
3. MCP サーバーの側では、Entra ID の接続先（`base_authority`）を `mock-entra:8443` にする。テナント ID・クライアント ID・シークレットは、`e2e/mock.env` の模擬用の値にする。
4. MCP サーバーのコンテナに、手元の認証局（`ca.crt`）を `update-ca-certificates` で入れる。FastMCP の httpx2 と、OBO で使う aiohttp は、どちらも OS の証明書ストアを読む。
5. ブラウザを使わない E2E では、AI ツールの代わりのクライアントが、認可の要求に `login_hint=<利用者 ID>` を付ける。ブラウザで試すときは、利用者を選ぶ画面が出る。`MOCK_AUTO_LOGIN_USER` を設定すると、画面を出さずにその利用者でサインインする。

## 手元で確かめたこと（2026-10-31）

次を、通信先をこの模擬サーバーにして確かめた。FastMCP 4.1.4、azure-identity 1.27.0、Python 3.14。

- 発行したアクセストークンを、FastMCP の `AzureProvider`（`base_authority` を模擬のホストにしたもの）の検証が受け付ける
- リフレッシュトークンで更新できる
- azure-identity の非同期版の `OnBehalfOfCredential`（FastMCP の `EntraOBOToken` が使うもの）で、手を加えずに Graph 用のトークンを得られる
- `carol` は AADSTS50105 で止まり、`dave` の OBO は AADSTS65001 で失敗する

## 限界

- 状態（認可コード、リフレッシュトークン）はメモリにあり、再起動で消える。署名鍵も、`MOCK_SIGNING_KEY_FILE` を渡さないと再起動のたびに変わる。
- 条件付きアクセス、多要素認証、`prompt` の各値の動き（`select_account` など）は再現しない。
- `client_info`、`ext_expires_in` などの細かい項目は、本物と同じではない。
