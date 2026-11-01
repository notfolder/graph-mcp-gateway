# PoC 専用の Open WebUI の運用

## 初期設定（初回と、接続先が壊れたとき）

1. 本システムを起動する。

   ```bash
   docker compose up -d --build
   ```

2. Open WebUI の初期設定を行う。何度実行してもよい（既にあるものは作り直さない）。

   ```bash
   docker compose --profile setup run --rm openwebui-setup configure
   ```

   次を行う。

   - Open WebUI の `/health` が 200 になるまで待つ（最大 3 分）。
   - 管理者（`.env` の `WEBUI_ADMIN_EMAIL`・`WEBUI_ADMIN_PASSWORD`）でログインする。
   - 言語モデル（`.env` の `OPENWEBUI_LLM_MODEL`）と、それを基にしたモデルの設定「PoC アシスタント」を利用者全員に公開する。どちらにも Open WebUI の自前のツール（カレンダー・メモなど）を渡さない設定を入れ、新しいチャットの既定のモデルを「PoC アシスタント」にする。
   - ツールサーバーの接続先「Microsoft 365」（探して使う受け口 `https://<公開のホスト名>/discovery/mcp`）が無ければ、DCR で登録して保存し、利用者全員に公開する。

   失敗したときは、状態コードと理由が表示され、終了コード 1 で止まる。429（API rate limit exceeded）のときは、Open WebUI のログインの回数の制限（メールアドレスごとに 3 分で 15 回）なので、3 分待ってから実行し直す。

## 参加者のアカウントの作成

1. 参加者の CSV を、Git の管理外の場所に作る。1 行目は見出しで、列は `name`・`email`・`password`（初期のパスワード）。

   ```csv
   name,email,password
   山田 太郎,taro.yamada@example.com,<初期のパスワード>
   ```

2. CSV のあるディレクトリをコンテナに読み取り専用で渡して、アカウントを作る。

   ```bash
   docker compose --profile setup run --rm -v <CSV のあるディレクトリ>:/input:ro openwebui-setup add-users /input/<ファイル名>
   ```

   - 役割は `user` で作る。同じメールアドレスが既にあれば飛ばして、その旨を表示する。
   - パスワードは表示しない。

3. 初期のパスワードを、メールとは別の経路で参加者に伝え、最初のログインの後に変えてもらう。
4. 使い終わった CSV は消す。

利用者自身の登録は止めてある（`ENABLE_SIGNUP=false`）。参加者を足すときは、上の手順をもう一度行う。

## PoC の終わりのデータの消去

Open WebUI のアカウント、利用者ごとの MCP サーバーのトークン、チャットの記録（ツールの結果を含む）を消す。

1. Open WebUI を止めて、コンテナを消す。

   ```bash
   docker compose stop open-webui
   docker compose rm -f open-webui
   ```

2. Open WebUI のデータのボリュームを消す（プロジェクト名は既定で `graph-mcp-gateway`）。

   ```bash
   docker volume rm graph-mcp-gateway_openwebui-data
   ```

3. 消えたことを確かめる。次の結果に `graph-mcp-gateway_openwebui-data` が無ければよい。

   ```bash
   docker volume ls
   ```

中継の認証の状態（`relay-full-home`・`relay-discovery-home`、台数を増やす構成では `redis-data`）は、PoC の終わりに本システム全体を片付けるときに `docker compose down -v` で消す。
