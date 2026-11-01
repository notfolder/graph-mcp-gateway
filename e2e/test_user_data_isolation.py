"""利用者ごとにデータが分かれる（利用者 A のトークンで B のデータを取れない）。"""

from __future__ import annotations

import os
import re

import pytest
from conftest import mode
from support.mcp_client import McpOAuthClient


def _targets() -> list[tuple[str, dict[str, str]]]:
    if mode() == "real":
        drive, _, item = os.environ.get("E2E_REAL_OTHER_USER_DRIVE_ITEM_ID", ":").partition(":")
        return [
            ("get-mail-message", {"messageId": os.environ.get("E2E_REAL_OTHER_USER_MESSAGE_ID", "")}),
            ("get-calendar-event", {"eventId": os.environ.get("E2E_REAL_OTHER_USER_EVENT_ID", "")}),
            ("list-chat-messages", {"chatId": os.environ.get("E2E_REAL_OTHER_USER_CHAT_ID", "")}),
            ("list-folder-files", {"driveId": drive, "driveItemId": item}),
        ]
    other = "mock-other-user"
    return [
        ("get-mail-message", {"messageId": other}),
        ("get-calendar-event", {"eventId": other}),
        ("list-chat-messages", {"chatId": other}),
        ("list-folder-files", {"driveId": other, "driveItemId": "root"}),
    ]


@pytest.mark.parametrize("index", range(4), ids=["mail", "event", "chat", "drive"])
async def test_other_users_data_is_not_returned(alice: McpOAuthClient, index: int) -> None:
    tool, arguments = _targets()[index]
    if not all(arguments.values()):
        pytest.skip("利用者 B のデータの ID が .env にありません")
    is_error, text = await alice.execute(tool, arguments)
    assert is_error, text
    assert re.search(r"\b(403|404)\b", text), text
