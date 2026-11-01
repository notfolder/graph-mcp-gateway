# ms-365-mcp-server の連携ライブラリ

独自の連携ライブラリは置かない。ms-365-mcp-server への中継は、FastMCP 4.1.4 の次の部品をそのまま使う（`../docs/research.md` 2 章「中継の作り」）。

| 公開インターフェース | 提供元 | 役割 |
|---|---|---|
| `fastmcp.server.providers.proxy.ProxyProvider` | `fastmcp` | 要求ごとにクライアントを作る関数を受け取り、ツールの一覧と呼び出しを中継先へ渡す |
| `fastmcp.server.providers.proxy.ProxyClient` | `fastmcp` | 中継先への MCP のクライアント。受信したヘッダーの転送は止めて使う（`forward_incoming_headers=False`） |
| `fastmcp.client.transports.StreamableHttpTransport` | `fastmcp` | 中継先への Streamable HTTP。利用者の Graph 用のトークンを `headers` の `Authorization` で付ける |
| `fastmcp.server.auth.providers.azure.AzureProvider.get_obo_credential` | `fastmcp[azure]` | 利用者の Entra のトークンから OBO の資格情報を作る |
