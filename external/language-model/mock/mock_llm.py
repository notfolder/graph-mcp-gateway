"""決まった応答を返す、OpenAI 互換のチャットの API の模擬。

E2E の mock モードで、Open WebUI がつなぐ言語モデルの代わりに使う。
Python の標準ライブラリだけで動く。

応答の決め方:
    - 最後の利用者の発言に ``CALL <ツール名> <JSON の引数>`` の行があり、
      まだツールの結果を受け取っていなければ、そのツールを呼ぶ応答を返す。
      ツール名は、要求に含まれるツールの名前の末尾が一致するものを選ぶ
      （Open WebUI はツール名の前に接続の ID を付けるため）。
    - ツールの結果（role が tool のメッセージ）を受け取っていれば、
      ``TOOL_RESULT: <結果の先頭>`` を本文とする応答を返す。
    - どちらでもなければ ``OK`` を返す（タイトルの生成などの付随の要求を含む）。

起動:
    python3 mock_llm.py [--port 8080] [--log <要求の記録を書くファイル>]
"""

from __future__ import annotations

import argparse
import json
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

MODEL_ID = "mock-model"
CALL_PATTERN = re.compile(r"^CALL\s+(\S+)\s*(.*)$", re.MULTILINE)


def build_reply(request: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """要求から、返すメッセージと終了の理由を決める。

    Args:
        request: チャットの API の要求の本文。

    Returns:
        返すメッセージ（role は assistant）と、finish_reason の組。
    """
    messages = request.get("messages") or []
    tools = request.get("tools") or []
    tool_results = [m for m in messages if m.get("role") == "tool"]
    if tool_results:
        content = str(tool_results[-1].get("content"))[:500]
        return {"role": "assistant", "content": "TOOL_RESULT: " + content}, "stop"

    last_user = next((m for m in reversed(messages) if m.get("role") == "user"), None)
    match = CALL_PATTERN.search(_text_of(last_user)) if last_user else None
    if match and tools:
        wanted, raw_args = match.group(1), match.group(2).strip() or "{}"
        name = next(
            (t["function"]["name"] for t in tools if t["function"]["name"].endswith(wanted)),
            None,
        )
        if name is not None:
            call = {
                "id": "call_1",
                "type": "function",
                "function": {"name": name, "arguments": raw_args},
            }
            return {"role": "assistant", "content": None, "tool_calls": [call]}, "tool_calls"
    return {"role": "assistant", "content": "OK"}, "stop"


def _text_of(message: dict[str, Any]) -> str:
    """メッセージの本文を文字列で取り出す（本文が部品の配列の場合も扱う）。"""
    content = message.get("content")
    if isinstance(content, list):
        return "\n".join(str(part.get("text", "")) for part in content if isinstance(part, dict))
    return str(content or "")


class MockHandler(BaseHTTPRequestHandler):
    """``/v1/models`` と ``/v1/chat/completions`` だけを受ける。"""

    protocol_version = "HTTP/1.1"
    log_path: str | None = None

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        """標準の接続のログは出さない。"""

    def do_GET(self) -> None:  # noqa: N802
        """モデルの一覧を返す。"""
        if self.path.rstrip("/").endswith("/models"):
            self._send_json(200, {"object": "list", "data": [{"id": MODEL_ID, "object": "model", "owned_by": "mock"}]})
        else:
            self._send_json(404, {"error": {"message": "not found"}})

    def do_POST(self) -> None:  # noqa: N802
        """チャットの要求に、決まった応答を返す。"""
        if not self.path.rstrip("/").endswith("/chat/completions"):
            self._send_json(404, {"error": {"message": "not found"}})
            return
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        request = json.loads(body or b"{}")
        message, finish = build_reply(request)
        self._record(request, len(body), message)
        if request.get("stream"):
            self._send_stream(message, finish)
        else:
            self._send_json(200, {
                "id": "mock-1",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": request.get("model", MODEL_ID),
                "choices": [{"index": 0, "message": message, "finish_reason": finish}],
            })

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_stream(self, message: dict[str, Any], finish: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Connection", "close")
        self.end_headers()
        delta = dict(message)
        if delta.get("tool_calls"):
            delta["tool_calls"] = [dict(delta["tool_calls"][0], index=0)]
        for choice in ({"delta": delta, "finish_reason": None}, {"delta": {}, "finish_reason": finish}):
            chunk = {
                "id": "mock-1",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": MODEL_ID,
                "choices": [dict(choice, index=0)],
            }
            self.wfile.write(f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()
        self.close_connection = True

    def _record(self, request: dict[str, Any], size: int, reply: dict[str, Any]) -> None:
        """要求の要点（大きさ、ツールの数、役割の並び、返した応答）を 1 行の JSON で書く。"""
        if not self.log_path:
            return
        entry = {
            "time": time.time(),
            "bytes": size,
            "stream": bool(request.get("stream")),
            "tool_count": len(request.get("tools") or []),
            "roles": [m.get("role") for m in request.get("messages") or []],
            "tool_results": [str(m.get("content"))[:500] for m in request.get("messages") or [] if m.get("role") == "tool"],
            "reply": reply,
        }
        with open(self.log_path, "a", encoding="utf-8") as fp:
            fp.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main() -> None:
    """引数を読んで、模擬のサーバーを起動する。"""
    parser = argparse.ArgumentParser(description="決まった応答を返す言語モデルの模擬")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--log", default=None, help="要求の記録を追記するファイル")
    args = parser.parse_args()
    MockHandler.log_path = args.log
    ThreadingHTTPServer(("0.0.0.0", args.port), MockHandler).serve_forever()


if __name__ == "__main__":
    main()
