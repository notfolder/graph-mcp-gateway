# 調査レポート：Microsoft Entra ID

- 確認日：2026-10-31
- 入力：`docs/requirements.md`（3-0 の OAuth の受け口、3-3 の外部連携、5 章の非機能要件）
- 事前確認：`external/entra-id/docs/precheck_report.md`
- 調べ方：FastMCP 4.1.4（`fastmcp_slim` の配布物）、azure-identity 1.27.0、azure-core 1.41.0、msal 1.39.0 をソースで読んだ。非同期版の OBO を、手元の簡易な模擬サーバーに向けて動かして確かめた（サブエージェントの実測）。実テナントへの接続はしていない。

## 1. システム概要

| 項目 | 内容 |
|---|---|
| システム名 | Microsoft Entra ID（ディレクトリ名 `entra-id`） |
| 役割 | 利用者のサインイン、MCP サーバー（API）あてのトークンの発行と更新、OBO による Graph 用のトークンへの交換 |
| API の種類 | OAuth 2.0 / OpenID Connect（v2 エンドポイント） |
| 公式ドキュメント | https://learn.microsoft.com/entra/identity-platform/v2-oauth2-auth-code-flow 、https://learn.microsoft.com/entra/identity-platform/v2-oauth2-on-behalf-of-flow |
| 本システムでの使い方 | FastMCP の `AzureProvider`（OAuth プロキシ）と `EntraOBOToken`（OBO）を通して使う。本システムが直接呼ぶ API は無い |

## 2. 認証・接続情報

| 項目 | 内容 |
|---|---|
| 認証方式 | MCP サーバーは機密クライアント。トークンの発行先への認証は、クライアントシークレット（FastMCP は Basic 認証、azure-identity の OBO はフォームの `client_secret`） |
| ベース URL | `https://{base_authority}/{tenant_id}`（`base_authority` の既定は `login.microsoftonline.com`。FastMCP の `AzureProvider` の引数で変えられる） |
| トークンの検証 | 発行者 `https://{base_authority}/{tenant_id}/v2.0`、公開鍵 `…/discovery/v2.0/keys`、RS256、宛先は `client_id` か `api://{client_id}`、`scp` に要求したスコープが入っていること（FastMCP の `JWTVerifier`） |
| 必要な環境変数 | `APP_CLIENT_ID`、`APP_CLIENT_SECRET`、`APP_TENANT_ID`（`external/entra-id/.env.example`）。mock モードでは、接続先を変える `APP_ENTRA_BASE_AUTHORITY` も使う |
| 依存の注意 | `EntraOBOToken` は azure-identity の非同期版を使い、非同期版は aiohttp が必須。`fastmcp[azure]==4.1.4` の依存には aiohttp が含まれない。無いと `ImportError: aiohttp package is not installed` で失敗する（実測） |
| TLS | 非同期版の OBO は aiohttp を使い、`ssl.create_default_context()`（OS の証明書ストア、`SSL_CERT_FILE` が効く）で検証する。FastMCP の公開鍵の取得とコードの交換は httpx2 を使い、OS の証明書ストアで検証する |

## 3. オペレーション一覧

| オペレーション名 | エンドポイント | メソッド | 主要パラメータ | レスポンス概要 |
|---|---|---|---|---|
| サインインの開始 | `/{tenant}/oauth2/v2.0/authorize` | GET（ブラウザ） | client_id、response_type=code、redirect_uri（`{base_url}/auth/callback`）、scope（API のスコープ＋Graph のスコープ＋offline_access）、state、code_challenge（S256）、prompt=select_account | 302 で redirect_uri へ（code と state）。割り当ての無い利用者は AADSTS50105 のエラー画面で止まる |
| コードの交換 | `/{tenant}/oauth2/v2.0/token` | POST | grant_type=authorization_code、code、redirect_uri、code_verifier、scope（API のスコープと OpenID の基本スコープだけ。資源は 1 つまで：AADSTS28000） | 200 と access_token（v2 の JWT）、refresh_token、expires_in、id_token |
| トークンの更新 | 同上 | POST | grant_type=refresh_token、refresh_token、scope | 200 と新しい access_token と refresh_token |
| OBO | 同上 | POST | grant_type=`urn:ietf:params:oauth:grant-type:jwt-bearer`、requested_token_use=on_behalf_of、assertion（利用者の access_token）、scope（Graph のスコープ）、client_id、client_secret | 200 と Graph あての access_token、expires_in。同意が無いと 400（AADSTS65001、`consent_required`） |
| 公開鍵 | `/{tenant}/discovery/v2.0/keys` | GET | — | 200 と JWKS |
| OpenID の設定 | `/{tenant}/v2.0/.well-known/openid-configuration` | GET | — | 200（非同期版の OBO と FastMCP は使わない。同期版の azure-identity が使う） |

- FastMCP は `offline_access` を自動で足す。リフレッシュトークンを得るためで、要件の「トークンの更新」の前提を満たす。
- 非同期版の OBO は、MSAL を使わず、トークンの発行先へ直接 POST する。接続先の検証（instance discovery）と OpenID の設定の取得はしない（azure-identity の `aio/_credentials/on_behalf_of.py` が `AadClient` を使う）。応答に `access_token` と、`expires_in` か `expires_on` が要る。
- OBO で得るトークンには、指定したスコープだけでなく、同意済みの Graph のスコープがすべて入る（Entra ID の仕様。MSAL のドキュメント「resources and scopes」）。

## 4. 連携先のデータ構造

Entra ID は、本システムから見てデータを保管する連携先ではない（DB 系ではない）。やり取りするのはトークンだけ。

| エンティティ名 | Create | Read（一覧） | Read（詳細） | 検索 | Update | Delete | 備考 |
|---|---|---|---|---|---|---|---|
| 利用者のトークン（access_token・refresh_token） | ○ | × | × | × | ○ | × | 作成はコードの交換、更新はリフレッシュ。保管は FastMCP（要件 4-2「利用者のトークンの組」） |
| Graph 用のトークン | ○ | × | × | × | × | × | OBO で作る。メモリ上だけで使う |
| 公開鍵（JWKS） | × | × | ○ | × | × | × | トークンの検証に使う |

## 5. 制限事項

| 項目 | 内容 |
|---|---|
| アクセストークンの期限 | 既定は 60〜90 分の間で、Entra ID が決める。FastMCP のアクセストークンは、既定でこれに合わせる |
| 資源は 1 要求に 1 つ | コードの交換とリフレッシュでは、API のスコープと OpenID の基本スコープだけを送る（AADSTS28000 の回避。FastMCP が行う） |
| 戻り先 | `localhost` 以外は HTTPS が必須。完全一致で照合する |
| クライアントシークレット | 有効期限がある（依頼資料 C-1）。署名鍵を明示していないと、更新したときに全員が再サインインになる（FastMCP の仕様。要件の「未確定の値を設定で変えられる」で扱う） |
| レート制限 | トークンの発行にも制限があるが、FastMCP は利用者ごとに OBO の資格情報をメモリにキャッシュし（1 台あたり最大 128 人分）、azure-identity のトークンキャッシュで交換を減らすので、通常の利用では問題にならない見込み |
| 社内のポリシー | 条件付きアクセスがかかる可能性がある（依頼資料 C-5 で確認中） |

## 6. モックの説明

方式は **ローカル HTTP サーバー方式（方式A）**：Python で小さな模擬 Entra ID を作る（`external/entra-id/mock/`）。認証の流れ（認可コード＋PKCE、リフレッシュ、OBO）を再現する必要があり、Entra 固有のエラー（AADSTS50105、AADSTS65001）も出したいので、方式A を選んだ。

- **作るエンドポイント**：
  - サインインの開始
  - トークンの発行（認可コード・リフレッシュ・OBO の 3 種）
  - 公開鍵
  - OpenID の設定
  - パスは Entra と同じ形にする
- **トークン**：RS256 の JWT。発行者は `https://{模擬のホスト}/{テナント}/v2.0`、宛先は `client_id`、`scp` に API のスコープを入れる。OBO では、宛先を Graph にし、利用者に同意済みの Graph のスコープをすべて入れる。
- **利用者**：設定ファイル（`mock/users.json`）に、利用者ごとの ID・名前・割り当ての有無・同意済みのスコープを書く。
- **異常系**：
  - 割り当ての無い利用者は、サインインの開始で AADSTS50105 のエラー画面を返す。
  - 同意の無いスコープの OBO は、AADSTS65001 の 400 を返す。
  - 署名の不正なトークン、期限切れのトークンでの OBO は、`invalid_grant` を返す。
- **ログイン画面の自動化**：`login_hint` に利用者 ID を付けた要求か、`MOCK_AUTO_LOGIN_USER` を設定した場合は、画面を出さずに認可コード付きで戻す。それ以外は、利用者を選ぶ簡単なフォームを出す。
- **起動**：MCP サーバーの `base_authority` を模擬のホストに向ける（mock モードの環境ファイル）。TLS の証明書は `external/entra-id/e2e/make-certs.sh` で、手元の認証局から作る。
- **限界**：
  - 条件付きアクセスや、多要素認証は再現しない。
  - トークンの中身は、Entra の主な項目（iss、aud、scp、oid、tid、upn、name、exp、iat、nbf）だけ。

## 7. 既存ライブラリの選定結果

**連携ライブラリ**：FastMCP の `AzureProvider`・`EntraOBOToken`（中で azure-identity を使う）をそのまま使う。

- 要件の技術制約で決まっている。
- Entra ID の API を直接呼ぶ処理は本システムに無いので、独自の連携ライブラリは作らない（`src/README.md`）。
- aiohttp だけは別に依存へ足す。

**模擬サーバーの候補と比較**（確認日 2026-10-31）

| 観点 | Python で自作 | navikt/mock-oauth2-server | navikt/azure-mock | Keycloak |
|---|---|---|---|---|
| 保守状況 | 自分で保守する | 6.1.4（2026-10-28）。活発 | リリースなし。最後の人手のコミットは 2026-06 | 26.8.1（2026-10-13）。非常に活発 |
| 利用規模 | — | stars 439 | stars 0 | stars 37,619 |
| ライセンス | 自由に決められる | MIT | MIT | Apache-2.0 |
| 対象 API のカバレッジ | 要る分だけ作る。Entra と同じパスにできる | 認可コード・リフレッシュ・OBO に対応。パスの形が違い、公開鍵の `/discovery/v2.0/keys` に当たる経路が無い | テナントのパス区切りが無い | パスが `/realms/…` で、OBO は RFC 8693 で Entra と違う |
| 認証方式 | 同上 | OBO で受け取ったトークンを検証しない | 未確認 | Entra の OBO の引数は通らない |
| 型定義 | 自分で書く | —（JVM） | — | — |
| テスタビリティ | Entra 固有のエラーを再現できる。FastMCP の既存の依存（starlette・uvicorn・PyJWT・cryptography）で作れる | 前にリバースプロキシを置いてパスを書き換える必要がある。Entra 固有のエラーは出せない | 不適 | 本物のログイン画面の操作が要る |

**推奨理由**：Python で自作する。

- Entra と同じ形のパスとトークンを出せる。
- 要件のテストシナリオ（割り当ての無い利用者、OBO の失敗）を mock モードで確かめられる。
- 依存も増えない。

**不採用理由**：

- mock-oauth2-server：リバースプロキシでのパスの書き換えが要り、Entra 固有のエラーを出せない。
- azure-mock：パスが合わず、保守も止まっている。
- Keycloak：パス・発行者・OBO の方式が合わない。

**リスク評価**

| 区分 | 内容 |
|---|---|
| 運用 | 模擬サーバーは E2E の mock モードでだけ使い、本番では起動しない |
| 法務 | 自作なので問題なし |
| 保守 | Entra の仕様（トークンの項目、エラーの形）が変わったときは、自分で直す。本物との差は real モードで確かめる |

**ユーザーの最終決定**：Python で自作する（2026-10-31、回答 2A）。

## 8. E2E の 2 モード運用

- **mock モード**：
  - `APP_ENTRA_BASE_AUTHORITY` を模擬 Entra ID のホストに向ける。
  - テナント ID・クライアント ID・シークレットは、模擬用の固定値を使う（`e2e/mock.env`。秘密ではない）。
  - 実装時・CI の必須ゴールは、mock モードでの全件通過。
- **real モード**：
  - `APP_ENTRA_BASE_AUTHORITY` を設定しない（既定の `login.microsoftonline.com`）。
  - 値は `.env` から読む。
  - 手動実行だけを必須にする。
- **切り替え**：テスト実行コマンドに渡す環境ファイル（`e2e/mock.env` か `real.env`）と、docker compose のプロファイルで切り替える。
- **シンボリックリンク**：プロジェクトの `e2e/` から `external/entra-id/mock/` をシンボリックリンクで参照し、リンクも Git で管理する。
- **テスト環境のスクリプト**：証明書の作成は bash（`e2e/make-certs.sh`）で行う。

## 未確認の項目（real モードで確かめる）

- 割り当ての無い利用者が、エラー画面で止まるか、戻り先にエラーで戻されるか
- 社内の条件付きアクセスがサインインと OBO に与える影響（依頼資料 C-5）
- アクセストークンとリフレッシュトークンの実際の期限
