"""本人の権限での中継が全領域で通る（両方の受け口）。mock モードは模擬の ID のつながりを使う。"""

from __future__ import annotations

import json

import pytest
from support.mcp_client import McpOAuthClient

pytestmark = pytest.mark.mock_only

MAIL_BODY_MARKER = "e2e-mail-body-7f3a9c"
SEARCH_MARKER = "e2e-search-term-5b1d"


async def _ok(client: McpOAuthClient, tool: str, arguments: dict | None = None) -> dict:
    is_error, text = await client.execute(tool, arguments)
    assert not is_error, f"{tool}: {text}"
    return json.loads(text) if text.strip().startswith(("{", "[")) else {"text": text}


async def test_profile(alice: McpOAuthClient) -> None:
    assert (await _ok(alice, "get-current-user"))["displayName"] == "Alice Mock"


async def test_mail_list_and_send(alice: McpOAuthClient) -> None:
    listed = await _ok(alice, "list-mail-messages", {"top": 10})
    assert listed["value"]
    await _ok(alice, "list-mail-messages", {"search": SEARCH_MARKER})
    await _ok(
        alice,
        "send-mail",
        {
            "body": {
                "message": {
                    "subject": "E2E",
                    "body": {"contentType": "Text", "content": MAIL_BODY_MARKER},
                    "toRecipients": [{"emailAddress": {"address": "bob@contoso.test"}}],
                },
                "saveToSentItems": False,
            }
        },
    )


async def test_calendar_view_and_create(alice: McpOAuthClient) -> None:
    view = await _ok(
        alice, "get-calendar-view", {"startDateTime": "2026-11-02T00:00:00Z", "endDateTime": "2026-11-09T00:00:00Z"}
    )
    assert view["value"]
    created = await _ok(
        alice,
        "create-calendar-event",
        {
            "body": {
                "subject": "E2E meeting",
                "start": {"dateTime": "2026-11-02T10:00:00", "timeZone": "Asia/Tokyo"},
                "end": {"dateTime": "2026-11-02T10:30:00", "timeZone": "Asia/Tokyo"},
            }
        },
    )
    assert created["id"] == "mock-event-created"


async def test_onedrive_list_and_upload(alice: McpOAuthClient) -> None:
    drives = await _ok(alice, "list-drives")
    drive_id = drives["value"][0]["id"]
    root = await _ok(alice, "get-drive-root-item", {"driveId": drive_id})
    children = await _ok(alice, "list-folder-files", {"driveId": drive_id, "driveItemId": root["id"]})
    assert children["value"]
    uploaded = await _ok(
        alice, "upload-file-content", {"driveId": drive_id, "driveItemId": "root:/e2e-upload.txt:", "body": "hello"}
    )
    assert "mock-item-uploaded" in json.dumps(uploaded)


async def test_sharepoint_list_items_and_create(alice: McpOAuthClient) -> None:
    sites = await _ok(alice, "search-sharepoint-sites", {"search": "mock"})
    site_id = sites["value"][0]["id"]
    lists = await _ok(alice, "list-sharepoint-site-lists", {"siteId": site_id})
    list_id = lists["value"][0]["id"]
    items = await _ok(alice, "list-sharepoint-site-list-items", {"siteId": site_id, "listId": list_id, "expand": ["fields"]})
    assert items["value"]
    await _ok(alice, "create-sharepoint-list-item", {"siteId": site_id, "listId": list_id, "body": {"fields": {"Title": "E2E"}}})


async def test_teams_list_and_post(alice: McpOAuthClient) -> None:
    chats = await _ok(alice, "list-chats")
    chat_id = chats["value"][0]["id"]
    await _ok(alice, "send-chat-message", {"chatId": chat_id, "body": {"body": {"content": "E2E"}}})


async def test_excel_get_and_update(alice: McpOAuthClient) -> None:
    sheets = await _ok(alice, "list-excel-worksheets", {"driveId": "mock-drive-onedrive", "driveItemId": "mock-item-workbook"})
    sheet_id = sheets["value"][0]["id"]
    target = {"driveId": "mock-drive-onedrive", "driveItemId": "mock-item-workbook", "workbookWorksheetId": sheet_id}
    got = await _ok(alice, "get-excel-range", {**target, "address": "A1:B2"})
    assert got["values"]
    await _ok(alice, "update-excel-range", {**target, "address": "A1:B2", "body": {"values": [[1, 2], [3, 4]]}})
