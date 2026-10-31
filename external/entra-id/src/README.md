# Entra ID の連携ライブラリ

独自の連携ライブラリは置かない。Entra ID との接続は、FastMCP 4.1.4 の次の部品をそのまま使う。

| 公開インターフェース | 提供元 | 役割 |
|---|---|---|
| `fastmcp.server.auth.providers.azure.AzureProvider` | `fastmcp[azure]` | OAuth プロキシ。サインインの中継、コードの交換、トークンの検証と更新。`base_authority` で接続先のホストを変えられる（mock モードで使う） |
| `fastmcp.server.auth.providers.azure.EntraOBOToken` | `fastmcp[azure]` | ツールの引数で、OBO による Graph 用のトークンを受け取る。中で `azure.identity.aio.OnBehalfOfCredential` を使う |

注意：`EntraOBOToken` が使う azure-identity の非同期版は aiohttp が必須だが、`fastmcp[azure]` の依存には含まれない。プロジェクトの依存に aiohttp を足す（`external/entra-id/docs/research.md` の 2 章）。
