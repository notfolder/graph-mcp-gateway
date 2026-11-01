# Codex からの接続

受け口の違いと共通の流れは [README.md](README.md) を先に読む。

## 1. 社内の認証局を信頼させる

Codex を起動するシェルで、社内の認証局の証明書を読ませる。

```bash
export CODEX_CA_CERTIFICATE=/path/to/company-ca.pem
```

## 2. 受け口を登録する

探して使う受け口の例（全部を出す受け口なら URL の `/discovery/` を `/full/` にする）。

```bash
codex mcp add m365 --url https://<公開のホスト名>/discovery/mcp
```

設定ファイル（`~/.codex/config.toml`）に直接書く場合は次のとおり。

```toml
[mcp_servers.m365]
url = "https://<公開のホスト名>/discovery/mcp"
```

## 3. 認証する

```bash
codex mcp login m365
```

ブラウザが開いたら次の順に進める。

1. 本システムの「接続の確認」画面で、クライアントの名前を確かめて「許可」を押す。
2. Entra ID のサインイン画面で社内アカウントでサインインする。
3. 完了の表示を確かめてブラウザを閉じる。

## 4. 確かめる

Codex に「M365 の自分のプロフィールを取得して」と頼み、本人の表示名とメールアドレスが返ることを確かめる。

## 補足

- 認証の状態を消すときは `codex mcp logout m365`。
- 期限が切れて 401 が続くときは、`codex mcp login m365` をやり直す。
