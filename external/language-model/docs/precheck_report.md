# 事前確認レポート：言語モデル（Open WebUI がつなぐもの）

- 確認日：2026-11-01
- 目的：PoC 専用の Open WebUI がつなぐ言語モデルに接続でき、ツールの呼び出し（function calling）に対応しているかを、変更要件の定義の前に確かめる。
- 背景（ユーザー回答、2026-11-01）：社内では、本番の Open WebUI と同じ社内の言語モデルの接続先（OpenAI 互換の API）を使う。社内の接続情報はまだ受け取っていない。社外でも PoC をできるだけ確かめるために、Claude の API（Claude Console の API キー、使った分だけ払う）を代わりに使う。モデルは Claude Haiku 5.5。

## 1. 連携先の概要

| 項目 | 内容 |
|---|---|
| 名前 | 言語モデル（ディレクトリ名 `language-model`）。接続先は 2 つ：社内の言語モデルの接続先、Claude の API |
| 提供元 | 社内の接続先：社内の担当部署。Claude の API：Anthropic |
| API の種類 | OpenAI 互換のチャットの API（`/chat/completions`）。Claude の API は OpenAI 互換の受け口 `https://api.anthropic.com/v1/` を使う |
| 役割 | Open WebUI から、会話の発言とツールの一覧を受け、応答と使うツールを返す |
| 本システムでの置き方 | 本システムの外にある。Open WebUI から HTTPS で呼ぶ |

## 2. 接続できるかの判定

| 接続先 | 判定 |
|---|---|
| Claude の API | **接続できる**（8 章）。手元の PC から、`.env` の鍵で接続した |
| 社内の言語モデルの接続先 | **未確認**。接続情報を受け取ってから確かめる |

## 3. 認証方式

| 項目 | 内容 |
|---|---|
| 方式 | API キー。OpenAI 互換の受け口では `Authorization: Bearer <鍵>`。Claude の API のモデルの一覧（`/models`）だけは、Anthropic の形（`x-api-key: <鍵>` と `anthropic-version`）が要る |
| Open WebUI での扱い | Open WebUI は接続先の URL に `api.anthropic.com` が含まれると、モデルの一覧を Anthropic の形で取りに行き、チャットの要求にも `anthropic-version` を付ける（`backend/open_webui/utils/anthropic.py`、`routers/openai.py`）。そのため、Open WebUI の設定は OpenAI 互換の接続先と同じ書き方でよい。接続先の設定でモデル名を指定すると、一覧を取りに行かずにそのモデルを使う（`OPENAI_API_CONFIGS` の `model_ids`） |
| 鍵の更新・失効 | Claude Console で発行・失効する。使える金額の上限を Console で設定できる |
| 接続元の制約 | Claude の API はインターネットから使える。社内の接続先は社内ネットワークからの見込み（未確認） |
| 必要な環境変数名 | 7 章 |

## 4. 主な制限

| 項目 | 内容 | 要件定義での扱い |
|---|---|---|
| 費用 | Claude の API は使った分だけ払う。8 章の 3 つの要求で計 446 トークン | 技術制約「ライセンスとコスト」に、社外での確認に限って使ってよいと書いた（ユーザーの選択） |
| OpenAI 互換の受け口の範囲 | `/models` は OpenAI の形では使えず、400（`anthropic-version: header is required`）が返る（実測）。チャットとツールの呼び出しは使える。Anthropic は互換の受け口を主に試用向けとしている | Open WebUI が自動で扱うので、要件の変更は要らない |
| ツールの呼び出しの厳密さ | OpenAI 互換の受け口では `strict` が無視され、ツールの引数が定義どおりの形になる保証は無い（公式ドキュメント） | ツールの引数の確認は ms-365-mcp-server と Graph に任せる（要件の変更なし） |
| 入力できる量 | 全部を出す受け口（ツールの一覧が約 950 KB）をそのまま渡すと、モデルの入力の上限を超えるおそれがある | 詳細調査で、Open WebUI が言語モデルに渡す大きさと合わせて確かめる |
| レート制限 | Claude Console のアカウントの段階に応じた上限がある | PoC の手での確認の量では問題にならない見込み |
| 社内の接続先 | 種類（OpenAI 互換）以外は未確認 | 接続情報を受け取ってから確かめる |

## 5. 後続の isdd-external-research で調べる範囲

1. 全部を出す受け口と探して使う受け口のそれぞれで、Open WebUI が言語モデルに渡す要求の大きさと、モデルの入力の上限との関係。
2. 社内の言語モデルの接続先の、ツールの呼び出しへの対応と入力できる量（接続情報を受け取ってから）。
3. mock モードで使う模擬の言語モデルが返すべき応答の形（Open WebUI の付随の要求を含む）。Open WebUI の詳細調査で扱う。

## 6. 要件定義に進んでよいかの判定

**条件付きで進んでよい。**

Claude の API では、接続・応答・ツールの呼び出しを確かめた。条件は、社内の言語モデルの接続先を、接続情報を受け取ってから確かめること（社内での real モードの確認の前まで）。

## 7. 必要な環境変数名の一覧

値は書かない。プロジェクト直下の `.env` に書き、Open WebUI のコンテナには `OPENAI_API_BASE_URL`・`OPENAI_API_KEY`（とモデル名の指定）として渡す。

| 名前 | 用途 |
|---|---|
| `OPENWEBUI_LLM_BASE_URL` | 言語モデルの接続先（社外は `https://api.anthropic.com/v1/`、社内は社内の接続先） |
| `OPENWEBUI_LLM_API_KEY` | 言語モデルの API キー（秘密情報） |
| `OPENWEBUI_LLM_MODEL` | 使うモデルの名前（社外は `claude-haiku-5-5`） |

## 8. 実接続テストの結果

- 実行日時：2026-11-01 09:15 ごろ（JST）
- 実行環境：手元の PC。Python の標準ライブラリだけの使い捨てのスクリプト（作業領域に置き、終了後に削除）。`.env` の値は画面にもファイルにも出していない。
- 接続先：Claude の API（`api.anthropic.com`）、モデル `claude-haiku-5-5`

| 確かめたこと | 方法 | 結果 |
|---|---|---|
| モデルの一覧（OpenAI の形） | `GET /v1/models`（`Authorization: Bearer`） | 400。`anthropic-version` のヘッダーが要ると返った |
| モデルの一覧（Anthropic の形） | `GET /v1/models`（`x-api-key`、`anthropic-version: 2023-06-01`） | 200。14 個のモデルがあり、`claude-haiku-5-5` も含まれていた |
| 短い発言 | `POST /v1/chat/completions`（「OK とだけ返して」） | 200、約 1.0 秒。「OK」が返った（20 トークン） |
| ツールの呼び出し | 偽のツール 1 つ（指定した都市の天気を調べる）を付けて「東京の天気を調べて」 | 200、約 0.9 秒。`finish_reason` が `tool_calls` で、そのツールを都市「東京」で呼ぶ応答が返った（426 トークン） |

## 9. 取得できるスキーマ（エンティティ一覧）

言語モデルはデータを保管しない。本システムから見たエンティティは「モデル」（`/models` の一覧の各項目）だけで、読み取りだけを行う。
