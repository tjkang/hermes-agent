"""Tests for config-driven Telegram callback-to-text routes."""

import sys
import types
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

    telegram_mod = types.ModuleType("telegram")
    telegram_mod.Update = object
    telegram_mod.Bot = object
    telegram_mod.Message = object
    telegram_mod.InlineKeyboardButton = object
    telegram_mod.InlineKeyboardMarkup = object

    error_mod = types.ModuleType("telegram.error")
    error_mod.NetworkError = type("NetworkError", (OSError,), {})
    error_mod.TimedOut = type("TimedOut", (OSError,), {})
    error_mod.BadRequest = type("BadRequest", (Exception,), {})
    telegram_mod.error = error_mod

    constants_mod = types.ModuleType("telegram.constants")
    constants_mod.ParseMode = SimpleNamespace(
        MARKDOWN="Markdown",
        MARKDOWN_V2="MarkdownV2",
        HTML="HTML",
    )
    constants_mod.ChatType = SimpleNamespace(
        PRIVATE="private",
        GROUP="group",
        SUPERGROUP="supergroup",
        CHANNEL="channel",
    )
    telegram_mod.constants = constants_mod

    ext_mod = types.ModuleType("telegram.ext")
    ext_mod.Application = object
    ext_mod.CommandHandler = object
    ext_mod.CallbackQueryHandler = object
    ext_mod.MessageHandler = object
    ext_mod.ContextTypes = SimpleNamespace(DEFAULT_TYPE=object)
    ext_mod.filters = object

    request_mod = types.ModuleType("telegram.request")
    request_mod.HTTPXRequest = object

    sys.modules.setdefault("telegram", telegram_mod)
    sys.modules.setdefault("telegram.error", error_mod)
    sys.modules.setdefault("telegram.constants", constants_mod)
    sys.modules.setdefault("telegram.ext", ext_mod)
    sys.modules.setdefault("telegram.request", request_mod)


from gateway.config import PlatformConfig

ROUTES = {
    "log:breakfast:default": "응, 기본 먹었어 ✅",
    "log:breakfast:custom": "다르게 먹었어 ✏️",
}


def _clear_fake_telegram_modules():
    for name in (
        "plugins.platforms.telegram.adapter",
        "telegram",
        "telegram.error",
        "telegram.constants",
        "telegram.ext",
        "telegram.request",
    ):
        module = sys.modules.get(name)
        if module is not None and not hasattr(module, "__file__"):
            sys.modules.pop(name, None)


@pytest.fixture(autouse=True)
def _isolate_telegram_adapter_import():
    _clear_fake_telegram_modules()
    yield
    _clear_fake_telegram_modules()


def _make_adapter(routes=ROUTES):
    _ensure_telegram_mock()
    from plugins.platforms.telegram.adapter import TelegramAdapter

    extra = {"callback_text_routes": routes} if routes is not None else {}
    config = PlatformConfig(enabled=True, token="test-token", extra=extra)
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
        text="아침 기본 세트 먹었어?",
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
async def test_routed_callback_injects_mapped_text_with_full_context(monkeypatch):
    monkeypatch.setenv("GATEWAY_ALLOW_ALL_USERS", "true")
    adapter = _make_adapter()
    update, query = _make_callback("log:breakfast:default")

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
async def test_routed_callback_strips_buttons_and_shows_choice(monkeypatch):
    monkeypatch.setenv("GATEWAY_ALLOW_ALL_USERS", "true")
    adapter = _make_adapter()
    update, query = _make_callback("log:breakfast:custom")

    await adapter._handle_callback_query(update, None)

    kwargs = query.edit_message_text.call_args.kwargs
    assert kwargs["reply_markup"] is None
    assert "TJ" in kwargs["text"]
    assert "다르게 먹었어" in kwargs["text"]


@pytest.mark.asyncio
async def test_unknown_callback_data_is_not_routed(monkeypatch):
    monkeypatch.setenv("GATEWAY_ALLOW_ALL_USERS", "true")
    adapter = _make_adapter()
    update, query = _make_callback("log:unknown:choice")

    await adapter._handle_callback_query(update, None)

    handle_message = cast(AsyncMock, adapter.handle_message)
    handle_message.assert_not_awaited()
    query.answer.assert_not_awaited()
    query.edit_message_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_unauthorized_user_is_rejected(monkeypatch):
    monkeypatch.delenv("GATEWAY_ALLOW_ALL_USERS", raising=False)
    adapter = _make_adapter()
    adapter._is_callback_user_authorized = MagicMock(return_value=False)
    update, query = _make_callback("log:breakfast:default")

    await adapter._handle_callback_query(update, None)

    handle_message = cast(AsyncMock, adapter.handle_message)
    handle_message.assert_not_awaited()
    answer_kwargs = query.answer.call_args.kwargs
    assert "not authorized" in answer_kwargs.get("text", "")


@pytest.mark.asyncio
async def test_edit_failure_still_routes_text(monkeypatch):
    monkeypatch.setenv("GATEWAY_ALLOW_ALL_USERS", "true")
    adapter = _make_adapter()
    update, query = _make_callback("log:breakfast:default")
    query.edit_message_text.side_effect = RuntimeError("message too old")

    await adapter._handle_callback_query(update, None)

    handle_message = cast(AsyncMock, adapter.handle_message)
    handle_message.assert_awaited_once()
    event = handle_message.call_args.args[0]
    assert event.text == "응, 기본 먹었어 ✅"


@pytest.mark.asyncio
async def test_legacy_callback_key_routes_when_configured(monkeypatch):
    monkeypatch.setenv("GATEWAY_ALLOW_ALL_USERS", "true")
    adapter = _make_adapter(routes={"haru_log:breakfast:default": "응, 기본 먹었어 ✅"})
    update, query = _make_callback("haru_log:breakfast:default")

    await adapter._handle_callback_query(update, None)

    handle_message = cast(AsyncMock, adapter.handle_message)
    handle_message.assert_awaited_once()
    assert handle_message.call_args.args[0].text == "응, 기본 먹었어 ✅"


def test_invalid_routes_config_is_ignored():
    adapter = _make_adapter(routes="not-a-mapping")
    assert adapter._callback_text_routes == {}


def test_oversized_and_empty_entries_are_dropped():
    adapter = _make_adapter(
        routes={
            "k" * 65: "over the 64-byte callback_data limit",
            "log:empty": "   ",
            "log:ok": "fine",
            42: "non-string key",
        }
    )
    assert adapter._callback_text_routes == {"log:ok": "fine"}
