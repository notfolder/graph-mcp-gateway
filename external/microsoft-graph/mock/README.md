# Microsoft Graph の模擬（Dev Proxy）

E2E の mock モードで、Microsoft Graph の代わりに応答を返す。方式は既存モックサーバーツール方式（Microsoft Dev Proxy v4.0.0）。

## ファイル

| ファイル | 役割 |
|---|---|
| `devproxyrc.json` | Dev Proxy の設定。MockResponsePlugin を使い、`graph.microsoft.com/v1.0` と模擬のダウンロード先（`mock-download.sharepoint.com`）だけを横取りする。模擬の無い要求は 502 にして、ツールの要求の組み立て間違いに気づけるようにする |
| `mocks.json` | 応答の一覧。上から順に照合し、最初に一致したものを返す。具体的な URL を先に、広い URL を後に並べる。URL はクエリ文字列まで含めて照合するので、末尾に `*` を付ける |

## 起動のしかた

1. Dev Proxy の公式イメージ `ghcr.io/dotnet/dev-proxy:4.0.0` を、このディレクトリを `/config` にマウントして起動する。プロキシは 8000 番で待ち受ける。
2. ルート証明書の置き場所（`/home/devproxy/.config/dev-proxy/rootCert`）を名前付きボリュームにして、起動のたびに証明書が変わらないようにする。
3. MCP サーバーのコンテナに次を設定する。
   - `HTTPS_PROXY=http://devproxy:8000`
   - `NO_PROXY=mock-entra,localhost,127.0.0.1`（模擬 Entra ID への通信は Dev Proxy を通さない）
4. Dev Proxy のルート証明書を、PEM で取り出す。方法は次のどちらか。
   - API：`GET http://devproxy:8897/proxy/rootCertificate?format=crt`。`DEV_PROXY_API_TOKEN` に決めた 32 文字以上の値を Bearer で付ける。
   - ファイル：`rootCert.pfx` を `openssl pkcs12 -in rootCert.pfx -clcerts -nokeys -passin pass:` で変換する。
5. 取り出した証明書を、MCP サーバーのコンテナの `/usr/local/share/ca-certificates/` に置き、`update-ca-certificates` を実行する。httpx2 は Linux では OS の証明書ストアを読むので、これで信頼される。
6. docker compose の定義（サービス名、プロファイル、ボリューム）は、詳細設計で作る。

## 決まった応答を返す ID

E2E のシナリオから、次の ID を使って異常系を起こす。

| 要求 | 応答 | 使うシナリオ |
|---|---|---|
| `GET /me/messages/mock-401…` | 401 `InvalidAuthenticationToken` | エラーの伝え方 |
| `GET /me/messages/mock-403…` | 403 `ErrorAccessDenied` | エラーの伝え方 |
| `GET /me/messages/mock-other-user…`、`/me/events/mock-other-user…`、`/chats/mock-other-user…` | 403 | 利用者ごとのデータの分離（mock モードでの代わりの確認） |
| `GET /me/messages/mock-404…` | 404 `ErrorItemNotFound` | エラーの伝え方 |
| `GET /me/messages/mock-429-then-ok…` | 1 回目だけ 429（`Retry-After: 1`）、2 回目から 200 | 再試行 |
| `GET /me/messages/mock-429-always…` | 毎回 429（`Retry-After: 1`） | 再試行の回数を使い切る |
| `GET /me/messages/mock-503…` | 毎回 503（`Retry-After: 1`） | 再試行 |
| `GET /me/drive/items/mock-file-text/content` | 302 → 模擬のダウンロード先がテキストを返す | ファイルの内容 |
| `GET /me/drive/items/mock-file-large` | 200 KB のテキストの情報 | 内容を返す上限 |
| `GET /me/drive/items/mock-file-binary` | PNG の情報 | テキスト以外の種類 |
| `POST …/items/*/children`（本文に `mock-existing-folder` を含む） | 409 `nameAlreadyExists` | 同じ名前のフォルダーの作成 |
| 一覧（メールフォルダー、メール、予定、ドライブのルート） | 1 ページ目に `@odata.nextLink`、2 ページ目は続き | 一覧の件数と続き |
| `GET /me/joinedTeams` | 3 件を 1 回で返す（Graph は件数を指定できない） | `$top` に対応しない一覧 |

## 限界

- 状態を持たない。作成した項目が一覧に現れるかは確かめられない（real モードで確かめる）。
- 利用者ごとのデータの分離は、決まった ID への 403 で代わりに確かめるだけ。
- nth の回数は Dev Proxy を再起動しないと戻らない。429 の後に成功させる試験は、E2E の 1 回の実行につき 1 度だけ行う。
- 実機での起動は未確認（302 の転送と、転送先の模擬が働くかを含む）。最初に E2E を組むときに確かめる。
