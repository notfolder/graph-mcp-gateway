# 対応表（設計 ID とコード）

設計 ID（`docs/detail_design.md`）と、それを実現するコードの対応。書式は isdd の対応表のルールに従う。運用（`DS-OP-*`）・テスト（`DS-TS-*`）・データ（`DS-SC-*`）の設計 ID は、compose・設定・手順書・テストで実現し、この表には載せない。

| DS-ID | 修飾名 | 備考 |
|---|---|---|
| `DS-MD-PACKAGE-OP-DOCKER-COMPOSE-STARTUP` | `src/graph_mcp_gateway/__init__.py` | パッケージの目印 |
| `DS-MD-MAIN-OP-DOCKER-COMPOSE-STARTUP` | `src/graph_mcp_gateway/__main__.py` | 起動 |
| `DS-FN-MAIN-OP-DOCKER-COMPOSE-STARTUP` | `src/graph_mcp_gateway/__main__.py::main` | 関数 |
| `DS-MD-CONFIG-NF-CONFIGURABLE-SETTINGS-WITH-RELAY` | `src/graph_mcp_gateway/config.py` | 設定 |
| `DS-CL-SETTINGS-NF-CONFIGURABLE-SETTINGS-WITH-RELAY` | `src/graph_mcp_gateway/config.py::Settings` | クラス |
| `DS-FN-SETTINGS-FROM-ENV-NF-CONFIGURABLE-SETTINGS-WITH-RELAY` | `src/graph_mcp_gateway/config.py::Settings.from_env` | メソッド |
| `DS-MD-AUTH-FT-RELAY-SIGN-IN` | `src/graph_mcp_gateway/auth.py` | 認証と保管先の組み立て |
| `DS-FN-BUILD-AUTH-PROVIDER-FT-RELAY-SIGN-IN` | `src/graph_mcp_gateway/auth.py::build_auth_provider` | 関数 |
| `DS-FN-BUILD-CLIENT-STORAGE-DT-AUTH-STATE-STORAGE` | `src/graph_mcp_gateway/auth.py::build_client_storage` | 関数 |
| `DS-MD-RELAY-FT-RELAY-MCP-REQUESTS` | `src/graph_mcp_gateway/relay.py` | Graph 用のトークンの交換と中継のクライアント |
| `DS-CL-GRAPH-TOKEN-EXCHANGER-FT-EXCHANGE-GRAPH-TOKEN-FOR-RELAY` | `src/graph_mcp_gateway/relay.py::GraphTokenExchanger` | クラス |
| `DS-FN-EXCHANGE-GRAPH-TOKEN-FT-EXCHANGE-GRAPH-TOKEN-FOR-RELAY` | `src/graph_mcp_gateway/relay.py::GraphTokenExchanger.exchange` | メソッド |
| `DS-CL-RELAY-CLIENT-FACTORY-FT-RELAY-MCP-REQUESTS` | `src/graph_mcp_gateway/relay.py::RelayClientFactory` | クラス（`__call__` が DS-FN-CREATE-RELAY-CLIENT を実現する） |
| `DS-FN-CREATE-RELAY-CLIENT-FT-RELAY-MCP-REQUESTS` | `src/graph_mcp_gateway/relay.py::RelayClientFactory` | `__call__` はダンダーメソッドで載せられないため、クラスに対応付ける |
| `DS-IF-MS365-MCP-SERVER-EX-RELAY-TO-MS365-MCP-SERVER` | `src/graph_mcp_gateway/relay.py::RelayClientFactory` | ms-365-mcp-server への中継の口 |
| `DS-IF-ENTRA-OBO-EX-EXCHANGE-TOKEN-WITH-ENTRA-OBO` | `src/graph_mcp_gateway/relay.py::GraphTokenExchanger.exchange` | OBO の口 |
| `DS-MD-SERVER-UI-MCP-FULL-ENDPOINT` | `src/graph_mcp_gateway/server.py` | サーバーの組み立て |
| `DS-FN-CREATE-SERVER-UI-MCP-FULL-ENDPOINT` | `src/graph_mcp_gateway/server.py::create_server` | 関数 |
| `DS-IF-MCP-FULL-ENDPOINT-UI-MCP-FULL-ENDPOINT` | `src/graph_mcp_gateway/server.py::create_server` | 全部を出す受け口（設定で決まる） |
| `DS-IF-MCP-DISCOVERY-ENDPOINT-UI-MCP-DISCOVERY-ENDPOINT` | `src/graph_mcp_gateway/server.py::create_server` | 探して使う受け口（設定で決まる） |
| `DS-IF-OAUTH-ENDPOINTS-UI-OAUTH-ENDPOINTS-BY-MCP-ENDPOINT` | `src/graph_mcp_gateway/auth.py::build_auth_provider` | 受け口ごとの OAuth の受け口（AzureProvider） |
| `DS-MD-OPEN-WEBUI-SETUP-OP-OPEN-WEBUI-SETUP` | `src/graph_mcp_gateway/openwebui_setup.py` | Open WebUI の初期設定 |
| `DS-FN-CONFIGURE-OPEN-WEBUI-OP-OPEN-WEBUI-SETUP` | `src/graph_mcp_gateway/openwebui_setup.py::configure_open_webui` | 関数 |
| `DS-FN-ADD-OPEN-WEBUI-USERS-FT-MANAGE-OPEN-WEBUI-ACCOUNTS` | `src/graph_mcp_gateway/openwebui_setup.py::add_open_webui_users` | 関数 |
| `DS-FN-SETUP-MAIN-OP-OPEN-WEBUI-SETUP` | `src/graph_mcp_gateway/openwebui_setup.py::main` | 関数 |
| `DS-MD-OPEN-WEBUI-API-PACKAGE-FT-PROVIDE-POC-OPEN-WEBUI` | `external/open-webui/src/openwebui_api/__init__.py` | 連携ライブラリの公開インターフェース |
| `DS-MD-OPEN-WEBUI-API-CLIENT-FT-PROVIDE-POC-OPEN-WEBUI` | `external/open-webui/src/openwebui_api/client.py` | 連携ライブラリの本体 |
| `DS-CL-OPEN-WEBUI-CLIENT-FT-PROVIDE-POC-OPEN-WEBUI` | `external/open-webui/src/openwebui_api/client.py::OpenWebUIClient` | クラス |
| `DS-IF-OPEN-WEBUI-API-FT-PROVIDE-POC-OPEN-WEBUI` | `external/open-webui/src/openwebui_api/client.py::OpenWebUIClient` | Open WebUI の API の口 |
| `DS-CL-OPEN-WEBUI-ERROR-FT-PROVIDE-POC-OPEN-WEBUI` | `external/open-webui/src/openwebui_api/client.py::OpenWebUIError` | クラス |
| `DS-FN-OPEN-WEBUI-API-METHODS-FT-PROVIDE-POC-OPEN-WEBUI` | `external/open-webui/src/openwebui_api/client.py::OpenWebUIClient.request` | メソッド |
| `DS-FN-OPEN-WEBUI-API-METHODS-FT-PROVIDE-POC-OPEN-WEBUI` | `external/open-webui/src/openwebui_api/client.py::OpenWebUIClient.aclose` | メソッド |
| `DS-FN-OPEN-WEBUI-API-METHODS-FT-PROVIDE-POC-OPEN-WEBUI` | `external/open-webui/src/openwebui_api/client.py::OpenWebUIClient.token` | プロパティ |
| `DS-FN-OPEN-WEBUI-API-METHODS-FT-PROVIDE-POC-OPEN-WEBUI` | `external/open-webui/src/openwebui_api/client.py::OpenWebUIClient.health` | メソッド |
| `DS-FN-OPEN-WEBUI-API-METHODS-FT-PROVIDE-POC-OPEN-WEBUI` | `external/open-webui/src/openwebui_api/client.py::OpenWebUIClient.signin` | メソッド |
| `DS-FN-OPEN-WEBUI-API-METHODS-FT-PROVIDE-POC-OPEN-WEBUI` | `external/open-webui/src/openwebui_api/client.py::OpenWebUIClient.signup` | メソッド |
| `DS-FN-OPEN-WEBUI-API-METHODS-FT-PROVIDE-POC-OPEN-WEBUI` | `external/open-webui/src/openwebui_api/client.py::OpenWebUIClient.add_user` | メソッド |
| `DS-FN-OPEN-WEBUI-API-METHODS-FT-PROVIDE-POC-OPEN-WEBUI` | `external/open-webui/src/openwebui_api/client.py::OpenWebUIClient.register_oauth_client` | メソッド |
| `DS-FN-OPEN-WEBUI-API-METHODS-FT-PROVIDE-POC-OPEN-WEBUI` | `external/open-webui/src/openwebui_api/client.py::OpenWebUIClient.get_tool_servers` | メソッド |
| `DS-FN-OPEN-WEBUI-API-METHODS-FT-PROVIDE-POC-OPEN-WEBUI` | `external/open-webui/src/openwebui_api/client.py::OpenWebUIClient.set_tool_servers` | メソッド |
| `DS-FN-OPEN-WEBUI-API-METHODS-FT-PROVIDE-POC-OPEN-WEBUI` | `external/open-webui/src/openwebui_api/client.py::OpenWebUIClient.list_tools` | メソッド |
| `DS-FN-OPEN-WEBUI-API-METHODS-FT-PROVIDE-POC-OPEN-WEBUI` | `external/open-webui/src/openwebui_api/client.py::OpenWebUIClient.start_mcp_authorization` | メソッド |
| `DS-FN-OPEN-WEBUI-API-METHODS-FT-PROVIDE-POC-OPEN-WEBUI` | `external/open-webui/src/openwebui_api/client.py::OpenWebUIClient.finish_mcp_authorization` | メソッド |
| `DS-FN-OPEN-WEBUI-API-METHODS-FT-PROVIDE-POC-OPEN-WEBUI` | `external/open-webui/src/openwebui_api/client.py::OpenWebUIClient.delete_oauth_session` | メソッド |
| `DS-FN-OPEN-WEBUI-API-METHODS-FT-PROVIDE-POC-OPEN-WEBUI` | `external/open-webui/src/openwebui_api/client.py::OpenWebUIClient.list_models` | メソッド |
| `DS-FN-OPEN-WEBUI-API-METHODS-FT-PROVIDE-POC-OPEN-WEBUI` | `external/open-webui/src/openwebui_api/client.py::OpenWebUIClient.get_model` | メソッド |
| `DS-FN-OPEN-WEBUI-API-METHODS-FT-PROVIDE-POC-OPEN-WEBUI` | `external/open-webui/src/openwebui_api/client.py::OpenWebUIClient.create_model` | メソッド |
| `DS-FN-OPEN-WEBUI-API-METHODS-FT-PROVIDE-POC-OPEN-WEBUI` | `external/open-webui/src/openwebui_api/client.py::OpenWebUIClient.create_chat` | メソッド |
| `DS-FN-OPEN-WEBUI-API-METHODS-FT-PROVIDE-POC-OPEN-WEBUI` | `external/open-webui/src/openwebui_api/client.py::OpenWebUIClient.get_chat` | メソッド |
| `DS-FN-OPEN-WEBUI-API-METHODS-FT-PROVIDE-POC-OPEN-WEBUI` | `external/open-webui/src/openwebui_api/client.py::OpenWebUIClient.delete_chat` | メソッド |
| `DS-FN-OPEN-WEBUI-API-METHODS-FT-PROVIDE-POC-OPEN-WEBUI` | `external/open-webui/src/openwebui_api/client.py::OpenWebUIClient.chat_completions` | メソッド |
