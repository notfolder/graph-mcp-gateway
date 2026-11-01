# 障害対応

検知の方法は、利用者からの連絡と、`docker compose ps`・`docker compose logs` の確認。ログは一般的な動作ログとエラーログだけで、トークン・ツールの引数・ツールの結果は書かれない。

| 障害 | 検知 | 対応 | 復旧の確認 |
|---|---|---|---|
| 中継が起動しない | `docker compose ps` で `relay-full`・`relay-discovery` が止まっている。ログに設定の誤りの項目名が出る（値は出ない） | `.env` を直して `docker compose up -d` | 両方の受け口のメタデータ（`https://<公開のホスト名>/.well-known/oauth-protected-resource/full/mcp` と `…/discovery/mcp`）が 200 |
| ms-365-mcp-server が止まる | ヘルスチェックの失敗（`docker compose ps` で unhealthy）。ツールの一覧の取得がエラーになる | `docker compose up -d ms365-full ms365-discovery`。続くなら `docker compose logs ms365-full ms365-discovery` を見る | ツールの一覧が取れる |
| Open WebUI が起動しない・ツールが使えない | 画面が開かない。チャットで「Failed to connect to MCP server」 | `docker compose logs open-webui` を見る。証明書の束（`OPENWEBUI_CA_BUNDLE`。社内の認証局と公開の認証局の両方）と `WEBUI_SECRET_KEY`（変えていないか）を確かめる。接続先が壊れたら `docker compose --profile setup run --rm openwebui-setup configure` を実行し直す | 画面が開き、チャットでツールが使える |
| サーバー証明書の期限切れ | AI ツール・ブラウザで証明書のエラー | 新しい証明書を `GATEWAY_CERT_DIR` の `server.crt`（中間証明書を含む）・`server.key` に置き、`docker compose restart gateway` | ブラウザで公開 URL の証明書の期限を見る |
| クライアントシークレットの期限切れ | サインインと OBO が失敗する | 別部署から新しいシークレットを受け取り、`.env` の `APP_CLIENT_SECRET` を直して `docker compose up -d`。署名鍵（`APP_JWT_SIGNING_KEY`）を明示していない場合は全員がサインインし直す | プロフィールのツールが返る |
| Entra ID・Graph・言語モデルの停止、外へ出られない | ツールが Graph のエラーか接続の失敗を返す。Open WebUI が応答しない | Microsoft・言語モデルの提供元の状態のページと社内のネットワーク（社内のプロキシの設定 `HTTPS_PROXY`・`NO_PROXY`）を確かめ、回復を待つ | プロフィールのツールが返る。Open WebUI が応答する |
| ディスク不足 | ログに書き込みの失敗。サインインが失敗する | 不要なイメージ・ログを消す（`docker system prune` は人が消える中身を確かめてから） | サインインが通る |
| Open WebUI の初期設定が 429（API rate limit exceeded）で止まる | 初期設定のスクリプトが 429 を表示する | Open WebUI はログインをメールアドレスごとに 3 分で 15 回までに制限するので、3 分待ってから実行し直す | 初期設定のスクリプトが終了コード 0 で終わる |
| Redis の停止（台数を増やす構成） | サインインとツールの呼び出しが失敗する。`docker compose ps` で `redis` が止まっている | `docker compose up -d redis` | サインインが通る |

## 台数を変えたとき

`.env` の `RELAY_FULL_REPLICAS`・`RELAY_DISCOVERY_REPLICAS`・`MS365_FULL_REPLICAS`・`MS365_DISCOVERY_REPLICAS` を変えて `docker compose up -d` した後は、受け口が新しい台数に振り分けるよう `docker compose restart gateway` を実行する。
