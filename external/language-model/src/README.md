# 言語モデルの連携ライブラリ

独自の連携ライブラリは置かない。言語モデルを呼ぶのは PoC 専用の Open WebUI で、本システムのコードは言語モデルを直接呼ばない。

| 接続先 | Open WebUI での設定 | 備考 |
|---|---|---|
| 社内の言語モデルの接続先 | `OPENAI_API_BASE_URL`・`OPENAI_API_KEY`（OpenAI 互換） | 接続情報を受け取ってから確かめる |
| Claude の API（社外での確認） | 同上。URL は `https://api.anthropic.com/v1/` | Open WebUI は URL に `api.anthropic.com` を含むと、モデルの一覧を Anthropic の形（`x-api-key`、`anthropic-version`）で取る |
| 言語モデルの模擬（mock モード） | 同上。URL は模擬の `http://<ホスト>:<ポート>/v1` | `../mock/` |
