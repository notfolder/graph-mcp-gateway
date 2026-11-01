"""1 台あたりの処理量を測る（e2e/run.sh の手順 6。mock モードの 1 台構成、中継と ms-365-mcp-server は CPU 1 個）。

中継（両方の受け口。alice と bob の MCP サーバーのトークンを混ぜる）と ms-365-mcp-server（両方。期限内の偽の JWT で
直接）のそれぞれについて、同時の呼び出しを 1・2・4・8・16・32・64 と増やし、各段 30 秒、プロフィールのツールを
呼び続ける。段ごとの毎秒の回数・エラーの割合・応答時間（中央値と 95%）と、1 台の処理量を
`<作業ディレクトリ>/capacity-report.md` に書く。ms-365-mcp-server が毎分 120 回を超えても 429 を返さないことも確かめる。
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastmcp import Client  # noqa: E402
from fastmcp.client.transports import StreamableHttpTransport  # noqa: E402
from support.mcp_client import McpOAuthClient, work_dir  # noqa: E402

STAGES = [int(v) for v in os.environ.get("CAPACITY_STAGES", "1,2,4,8,16,32,64").split(",")]
STAGE_SECONDS = float(os.environ.get("CAPACITY_STAGE_SECONDS", "30"))
GROWTH = 0.05


@dataclass
class Target:
    """測る対象。"""

    name: str
    url: str
    discovery: bool
    tokens: list[str] = field(default_factory=list)
    oauth: list[McpOAuthClient] = field(default_factory=list)

    def refresh(self) -> None:
        """中継のトークンを、段の途中で切れないように更新する。"""
        if self.oauth:
            for client in self.oauth:
                client.ensure_fresh(margin=STAGE_SECONDS + 20)
            self.tokens = [c.tokens.access_token for c in self.oauth if c.tokens]


@dataclass
class StageResult:
    """1 段の結果。"""

    concurrency: int
    calls: int
    errors: int
    rate_limited: int
    seconds: float
    latencies: list[float]

    @property
    def rps(self) -> float:
        return (self.calls - self.errors) / self.seconds if self.seconds else 0.0

    @property
    def error_rate(self) -> float:
        return self.errors / self.calls if self.calls else 0.0

    def percentile(self, q: float) -> float:
        if not self.latencies:
            return 0.0
        ordered = sorted(self.latencies)
        return ordered[min(len(ordered) - 1, int(q * len(ordered)))] * 1000


def _fake_graph_jwt() -> str:
    def enc(data: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()

    return f"{enc({'alg': 'none', 'typ': 'JWT'})}.{enc({'exp': int(time.time()) + 7200})}.x"


async def _worker(target: Target, token: str, deadline: float, result: StageResult) -> None:
    transport = StreamableHttpTransport(target.url, headers={"Authorization": f"Bearer {token}"})
    async with Client(transport, timeout=60) as client:
        while time.monotonic() < deadline:
            started = time.monotonic()
            try:
                if target.discovery:
                    response = await client.call_tool(
                        "execute-tool", {"tool_name": "get-current-user", "parameters": {}}, raise_on_error=False
                    )
                else:
                    response = await client.call_tool("get-current-user", {}, raise_on_error=False)
                text = response.content[0].text if response.content else ""
                failed = bool(response.is_error)
                if "429" in text:
                    result.rate_limited += 1
            except Exception:
                failed = True
            result.calls += 1
            if failed:
                result.errors += 1
            else:
                result.latencies.append(time.monotonic() - started)


async def run_stage(target: Target, concurrency: int) -> StageResult:
    """同時に `concurrency` 本で `STAGE_SECONDS` 秒呼び続ける。"""
    target.refresh()
    result = StageResult(concurrency, 0, 0, 0, STAGE_SECONDS, [])
    deadline = time.monotonic() + STAGE_SECONDS
    started = time.monotonic()
    await asyncio.gather(
        *(_worker(target, target.tokens[i % len(target.tokens)], deadline, result) for i in range(concurrency)),
        return_exceptions=True,
    )
    result.seconds = time.monotonic() - started
    return result


def capacity(results: list[StageResult]) -> StageResult | None:
    """エラーが 0 件のまま、毎秒の回数が前の段より 5% 以上増えた最後の段を返す。"""
    best = None
    previous = 0.0
    for stage in results:
        if stage.errors:
            break
        if best is None or stage.rps >= previous * (1 + GROWTH):
            best = stage
        previous = stage.rps
    return best


def report(all_results: dict[str, list[StageResult]]) -> str:
    """報告の Markdown を作る。"""
    lines = [
        "# 1 台あたりの処理量の測定結果（mock モード）",
        "",
        f"- 測定日時：{time.strftime('%Y-%m-%d %H:%M:%S %Z')}",
        f"- 条件：中継と ms-365-mcp-server は CPU 1 個（e2e/compose.capacity.yaml）、各段 {STAGE_SECONDS:.0f} 秒、"
        "プロフィールのツール（get-current-user）を呼び続ける。Graph は Dev Proxy の模擬",
        "- 中継は alice と bob の MCP サーバーのトークンを混ぜ、ms-365-mcp-server には期限内の偽の JWT で直接呼ぶ",
        "",
    ]
    for name, results in all_results.items():
        best = capacity(results)
        lines += [
            f"## {name}",
            "",
            "| 同時の呼び出し | 呼び出し | 毎秒の回数（成功） | エラーの割合 | 429 | 中央値（ms） | 95%（ms） |",
            "|---|---|---|---|---|---|---|",
        ]
        for r in results:
            median = statistics.median(r.latencies) * 1000 if r.latencies else 0.0
            lines.append(
                f"| {r.concurrency} | {r.calls} | {r.rps:.1f} | {r.error_rate:.1%} | {r.rate_limited} | {median:.0f} | {r.percentile(0.95):.0f} |"
            )
        lines += ["", f"1 台の処理量：{f'毎秒 {best.rps:.1f} 回（同時 {best.concurrency}）' if best else '求められませんでした'}", ""]
    lines += [
        "## 台数の見積もり",
        "",
        "台数 ＝ 切り上げ（利用者数 × 同時に使う人の割合 × 1 人の毎秒の呼び出し × 受け口の使い分けの比率 ÷ 1 台の処理量）",
        "",
        "| 仮定 | 値 |",
        "|---|---|",
        "| 利用者数 | 10,000 |",
        "| 同時に使う人の割合 | （記入） |",
        "| 1 人の毎秒の呼び出し | （記入） |",
        "| 受け口の使い分けの比率（全部を出す方 : 探して使う方） | （記入） |",
        "| 1 台の処理量（上の表の中継と ms-365-mcp-server の小さい方） | （記入） |",
        "",
        "- mock モードの Graph は Dev Proxy の決まった応答なので、本物の Graph の応答時間は含まない。",
    ]
    return "\n".join(lines) + "\n"


async def main() -> int:
    host = os.environ.get("E2E_BASE_HOST", "gateway")
    fake = _fake_graph_jwt()
    targets = []
    for endpoint in ("full", "discovery"):
        users = [McpOAuthClient(endpoint=endpoint, name=f"capacity-{endpoint}-{u}") for u in ("alice", "bob")]
        for user, client in zip(("alice", "bob"), users, strict=True):
            client.sign_in(user)
        targets.append(Target(f"中継（{endpoint}）", f"https://{host}/{endpoint}/mcp", endpoint == "discovery", oauth=users))
    for endpoint in ("full", "discovery"):
        targets.append(Target(f"ms-365-mcp-server（{endpoint}）", f"http://ms365-{endpoint}:3000/mcp", endpoint == "discovery", [fake]))

    all_results: dict[str, list[StageResult]] = {}
    for target in targets:
        results = []
        for concurrency in STAGES:
            stage = await run_stage(target, concurrency)
            print(
                f"{target.name} 同時 {concurrency}: {stage.calls} 回、毎秒 {stage.rps:.1f}、エラー {stage.errors}、429 {stage.rate_limited}",
                flush=True,
            )
            results.append(stage)
        all_results[target.name] = results

    path = work_dir() / "capacity-report.md"
    path.write_text(report(all_results), encoding="utf-8")
    print(f"報告を書きました: {path}")

    ms365 = [r for name, rs in all_results.items() if name.startswith("ms-365") for r in rs]
    over_limit = any(r.calls / r.seconds * 60 > 120 for r in ms365)
    if not over_limit:
        print("ms-365-mcp-server に毎分 120 回を超える呼び出しができませんでした", file=sys.stderr)
        return 1
    if any(r.rate_limited for r in ms365):
        print("ms-365-mcp-server が 429 を返しました", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
