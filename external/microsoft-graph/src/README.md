# Microsoft Graph の連携ライブラリ

独自の連携ライブラリは置かない。2026-11-01 の方針変更で、本システムは Graph を直接呼ばなくなり、Graph を呼ぶのは既製の ms-365-mcp-server になった（`external/ms-365-mcp-server/docs/research.md`）。

ツールを自作する方針のときに作った薄い非同期クライアント（`graph_api/`）は、使わなくなったので 2026-11-01 に消した（ユーザー回答）。中身はコミット `b43a62c` の履歴に残っている。
