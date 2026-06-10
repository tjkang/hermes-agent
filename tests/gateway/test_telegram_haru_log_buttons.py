"""Tests for Harunyang recurring-log inline Telegram buttons."""

import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest

_repo = str(Path(__file__).resolve().parents[2])
if _repo not in sys.path:
    sys.path.insert(0, _repo)


def _ensure_telegram_mock():
    if "telegram" in sys.modules and hasattr(sys.modules["telegram"], "__file__"):
        return

    mod = MagicMock()
    mod.ext.ContextTypes.DEFAULT_TYPE = type(None)
    mod.constants.ParseMode.MARKDOWN = "Markdown"
    mod.constants.ParseMode.MARKDOWN_V2 = "MarkdownV2"
    mod.constants.ParseMode.HTML = "HTML"
    mod.constants.ChatType.PRIVATE = "private"
    mod.constants.ChatType.GROUP = "group"
    mod.constants.ChatType.SUPERGROUP = "supergroup"
    mod.constants.ChatType.CHANNEL = "channel"
    mod.error.NetworkError = type("NetworkError", (OSError,), {})
    mod.error.TimedOut = type("TimedOut", (OSError,), {})
    mod.error.BadRequest = type("BadRequest", (Exception,), {})

    for name in ("telegram", "telegram.ext", "telegram.constants", "telegram.request"):
        sys.modules.setdefault(name, mod)
    sys.modules.setdefault("telegram.error", mod.error)


_ensure_telegram_mock()

from gateway.config import PlatformConfig
from plugins.platforms.telegram.adapter import TelegramAdapter


def _make_adapter():
    config = PlatformConfig(enabled=True, token="test-token", extra={})
    adapter = TelegramAdapter(config)
    adapter._bot = AsyncMock()
    adapter._app = MagicMock()
    adapter.handle_message = AsyncMock()
    return adapter


def _make_callback(data: str):
    chat = SimpleNamespace(
        id=12345,
        type="private",
        title=None,
        full_name="TJ",
        is_forum=False,
    )
    prompt_message = SimpleNamespace(
        chat=chat,
        chat_id=12345,
        text="아침 기본 세트 먹었어? 😺",
        message_id=777,
        message_thread_id=None,
        is_topic_message=False,
    )
    from_user = SimpleNamespace(id="49334209", first_name="TJ", full_name="TJ")
    query = AsyncMock()
    query.data = data
    query.message = prompt_message
    query.from_user = from_user
    return SimpleNamespace(callback_query=query), query


@pytest.mark.asyncio
async def test_haru_breakfast_default_inline_callback_routes_as_text(monkeypatch):
    monkeypatch.setenv("GATEWAY_ALLOW_ALL_USERS", "true")
    adapter = _make_adapter()
    update, query = _make_callback("haru_log:breakfast:default")

    await adapter._handle_callback_query(update, None)

    query.answer.assert_awaited_once()
    query.edit_message_text.assert_awaited_once()
    handle_message = cast(AsyncMock, adapter.handle_message)
    handle_message.assert_awaited_once()
    event = handle_message.call_args.args[0]
    assert event.text == "응, 기본 먹었어 ✅"
    assert event.source.chat_id == "12345"
    assert event.source.user_id == "49334209"


@pytest.mark.asyncio
async def test_haru_breakfast_custom_inline_callback_routes_as_text(monkeypatch):
    monkeypatch.setenv("GATEWAY_ALLOW_ALL_USERS", "true")
    adapter = _make_adapter()
    update, query = _make_callback("haru_log:breakfast:custom")

    await adapter._handle_callback_query(update, None)

    query.answer.assert_awaited_once()
    handle_message = cast(AsyncMock, adapter.handle_message)
    handle_message.assert_awaited_once()
    event = handle_message.call_args.args[0]
    assert event.text == "다르게 먹었어 ✏️"


@pytest.mark.asyncio
async def test_haru_log_callback_strips_buttons_without_reply_keyboard(monkeypatch):
    monkeypatch.setenv("GATEWAY_ALLOW_ALL_USERS", "true")
    adapter = _make_adapter()
    update, query = _make_callback("haru_log:breakfast:default")

    await adapter._handle_callback_query(update, None)

    kwargs = query.edit_message_text.call_args.kwargs
    assert kwargs["reply_markup"] is None
    assert "TJ" in kwargs["text"]
