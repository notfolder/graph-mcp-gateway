# 要件整合確認レポート：Microsoft Entra ID

- 確認日：2026-10-31
- 調査レポート：`external/entra-id/docs/research.md`

## 1. 入力した要件

`docs/requirements.md`（新規の要件定義書。isdd 形式、整合チェック合格済み）

## 2. 一致している要件

| RQ-ID | 確認した内容 |
|---|---|
| `RQ-EX-SIGN-IN-WITH-ENTRA-ID`、`RQ-FT-RELAY-SIGN-IN` | FastMCP の `AzureProvider` が、Entra ID の v2 の認可コード＋PKCE を中継する。戻り先は `{base_url}/auth/callback` |
| `RQ-FT-REFRESH-TOKEN` | `AzureProvider` が `offline_access` を自動で足し、Entra のリフレッシュトークンで更新する |
| `RQ-EX-EXCHANGE-TOKEN-WITH-ENTRA-OBO`、`RQ-FT-EXCHANGE-GRAPH-TOKEN` | `EntraOBOToken` が azure-identity の非同期版で OBO を行う。得られるトークンに同意済みのスコープがすべて入るという注記も、Entra ID の仕様と合う |
| `RQ-FT-ISSUE-PROXY-TOKEN`、`RQ-NF-NO-TOKEN-EXPOSURE` | FastMCP は AI ツールに自分のトークンだけを発行し、Entra のトークンは暗号化して保管する |
| `RQ-NF-TOKEN-VALIDATION` | FastMCP の `JWTVerifier` が、署名（RS256、テナントの公開鍵）・発行者・宛先・スコープを確かめる |
| `RQ-NF-SINGLE-TENANT` | 発行者に特定のテナント ID が入るので、他のテナントのトークンは検証で落ちる（`common` の拒否は本システムの起動時の検査で行う） |
| `RQ-NF-SINGLE-REDIRECT-URI` | Entra ID に登録する戻り先は 1 件で、AI ツールの戻り先は FastMCP の中だけで扱う |
| `RQ-FT-REGISTER-AI-TOOL` | DCR は FastMCP が常に有効にする。CIMD は `enable_cimd` で切り替えられる（既定は有効）。Claude Code・Codex・OpenCode とも DCR に対応し、Claude Code と Codex は CIMD にも対応する |
| `RQ-EX-USE-LOCAL-HTTP-MOCK` | 非同期版の OBO は接続先の検証をしないので、`base_authority` を模擬のホストに向けるだけで動く（実測）。テスト用に OBO の処理を差し替える必要は無い |
| `RQ-TS-VERIFY-UNASSIGNED-USER-REJECTED`、`RQ-TS-VERIFY-ERROR-MESSAGES` | 自作の模擬サーバーで、AADSTS50105 と AADSTS65001 を mock モードでも再現できる |

## 3. 不整合な要件（不足・矛盾・過剰）

| 種類 | 要件 | 内容 |
|---|---|---|
| 不足 | 技術制約（1-1） | `EntraOBOToken` は aiohttp が必須だが、`fastmcp[azure]` の依存に含まれない。要件に書かれていないと、OBO が実行時に `ImportError` で失敗する |
| 不足 | 接続手順書（6 章） | AI ツールによって、社内の認証局を信頼させる方法が違う（Claude Code は OS の証明書ストアも見るが、Codex は `CODEX_CA_CERTIFICATE`、OpenCode は `NODE_EXTRA_CA_CERTS` が要る場合がある）。手順書の内容に書かれていない |
| 矛盾 | 無し | — |
| 過剰 | 無し | — |

## 4. 修正方針

ユーザーの確認を得て（2026-10-31、回答 7）、要件定義書を次のように直した。

| 要件 | 修正後 |
|---|---|
| 技術制約（1-1）の「実装の方式」 | 「`EntraOBOToken` は azure-identity の非同期版を使うため aiohttp が要る（`fastmcp[azure]` には含まれないので、別に依存へ足す）」を足す |
| 接続手順書 | 「AI ツールごとに、社内の認証局を信頼させる設定（Claude Code と OpenCode は `NODE_EXTRA_CA_CERTS`、Codex は `CODEX_CA_CERTIFICATE`）も載せる」を足す |

## 5. 修正後の確認結果

- `rq_integrity_checker.py docs/requirements.md` が合格（RQ-* 88 件、BK 対応の欠落 0、孤立した BK 0、書式違反 0）。
- 3 章の不整合は、4 章の修正ですべて解消した。
- 実テナントでしか分からない点（`research.md` の「未確認の項目」）は、real モード（PoC 用テナント）で確かめる。

## 6. 設計に進めるかの判定

**進める。** 未解消の不整合は無い。
