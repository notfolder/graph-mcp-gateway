# Entra ID の連携ライブラリ

独自の連携ライブラリは置かない。Entra ID との接続は、FastMCP 4.1.4 の次の部品をそのまま使う。

| 公開インターフェース | 提供元 | 役割 |
|---|---|---|
| `fastmcp.server.auth.providers.azure.AzureProvider` | `fastmcp[azure]` | OAuth プロキシ。サインインの中継、コードの交換、トークンの検証と更新。`base_authority` で接続先のホストを変えられる（mock モードで使う） |
| `fastmcp.server.auth.providers.azure.AzureProvider.get_obo_credential` | `fastmcp[azure]` | 中継の関数の中で、利用者の Entra のトークンから OBO の資格情報を作り、Graph 用のトークンを得る（2026-11-01 の方針変更で、ツールの引数の `EntraOBOToken` から置き換え。`external/ms-365-mcp-server/docs/research.md` 2 章）。中で `azure.identity.aio.OnBehalfOfCredential` を使う |

注意：OBO で使う azure-identity の非同期版は aiohttp が必須だが、`fastmcp[azure]` の依存には含まれない。プロジェクトの依存に aiohttp を足す（`external/entra-id/docs/research.md` の 2 章）。
