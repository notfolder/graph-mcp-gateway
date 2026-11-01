# OpenCode からの接続

受け口の違いと共通の流れは [README.md](README.md) を先に読む。

## 1. 社内の認証局を信頼させる

OpenCode を起動するシェルで、社内の認証局の証明書を読ませる。

```bash
export NODE_EXTRA_CA_CERTS=/path/to/company-ca.pem
```

## 2. 受け口を登録する

OpenCode の設定ファイル（プロジェクトの `opencode.json` か、`~/.config/opencode/opencode.json`）に書く。探して使う受け口の例（全部を出す受け口なら URL の `/discovery/` を `/full/` にする）。

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "m365": {
      "type": "remote",
      "url": "https://<公開のホスト名>/discovery/mcp",
      "enabled": true
    }
  }
}
```

## 3. 認証する

```bash
opencode mcp auth m365
```

ブラウザが開いたら次の順に進める。

1. 本システムの「接続の確認」画面で、クライアントの名前を確かめて「許可」を押す。
2. Entra ID のサインイン画面で社内アカウントでサインインする。
3. 完了の表示を確かめてブラウザを閉じる。

## 4. 確かめる

OpenCode に「M365 の自分のプロフィールを取得して」と頼み、本人の表示名とメールアドレスが返ることを確かめる。

## 補足

- 認証の状態を消すときは `opencode mcp logout m365`。
- 期限が切れて 401 が続くときは、`opencode mcp auth m365` をやり直す。
