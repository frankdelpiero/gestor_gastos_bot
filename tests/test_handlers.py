"""Flujo del bot con un repositorio en memoria y objetos Telegram simulados."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from gastos_bot.bot import handlers
from gastos_bot.bot.handlers import Deps
from gastos_bot.config import Settings
from gastos_bot.sheets.client import SheetsUnavailable
from gastos_bot.sheets.repository import InMemoryRepository

NOW = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
SETTINGS = Settings("t", 42, "sid", "{}", "secret")


def make(text=None, user_id=42, update_id=1, args=None, callback_data=None):
    repo = InMemoryRepository()
    return repo, *build(repo, text, user_id, update_id, args, callback_data)


def build(repo, text=None, user_id=42, update_id=1, args=None, callback_data=None):
    msg = SimpleNamespace(text=text, date=NOW, reply_text=AsyncMock(), reply_photo=AsyncMock())
    query = None
    if callback_data is not None:
        query = SimpleNamespace(data=callback_data, answer=AsyncMock(), edit_message_text=AsyncMock())
    update = SimpleNamespace(
        update_id=update_id, effective_message=msg, callback_query=query,
        effective_user=SimpleNamespace(id=user_id, full_name="Yo"),
    )
    deps = Deps(SETTINGS, repo, now=lambda: NOW)
    ctx = SimpleNamespace(application=SimpleNamespace(bot_data={"deps": deps}), args=args or [])
    return update, ctx


async def test_registers_and_echoes():
    repo, update, ctx = make("Cena -32,5")
    await handlers.on_text(update, ctx)
    assert repo.records[0].id == 1
    echo = update.effective_message.reply_text.call_args[0][0]
    assert "#1" in echo and "-32,50 €" in echo and "18/11/2026" in echo


async def test_invalid_format_shows_help():
    repo, update, ctx = make("hola")
    await handlers.on_text(update, ctx)
    assert not repo.records
    assert "Formato" in update.effective_message.reply_text.call_args[0][0]


async def test_other_user_is_ignored():
    repo, update, ctx = make("Cena -5", user_id=999)
    await handlers.on_text(update, ctx)
    assert not repo.records
    update.effective_message.reply_text.assert_not_called()


async def test_resent_update_does_not_duplicate():
    repo, update, ctx = make("Cena -5", update_id=7)
    await handlers.on_text(update, ctx)
    update2, ctx2 = build(repo, "Cena -5", update_id=7)
    await handlers.on_text(update2, ctx2)
    assert len(repo.records) == 1


async def test_sheets_failure_gives_clear_message():
    repo, update, ctx = make("Cena -5")
    repo.fail_next = SheetsUnavailable("boom")
    await handlers.on_text(update, ctx)
    assert "Google Sheets" in update.effective_message.reply_text.call_args[0][0]
    assert not repo.records


async def test_delete_flow_confirm_and_cancel():
    repo, update, ctx = make("Cena -5")
    await handlers.on_text(update, ctx)

    upd, ctx = build(repo, update_id=2, args=["1"])
    await handlers.on_borrar(upd, ctx)
    kb = upd.effective_message.reply_text.call_args.kwargs["reply_markup"]
    cancel, confirm = kb.inline_keyboard[0][1].callback_data, kb.inline_keyboard[0][0].callback_data
    assert "Cena" in upd.effective_message.reply_text.call_args[0][0]

    upd, ctx = build(repo, update_id=3, callback_data=cancel)
    await handlers.on_delete_callback(upd, ctx)
    assert len(repo.records) == 1
    assert upd.callback_query.edit_message_text.call_args.kwargs["reply_markup"] is None

    upd, ctx = build(repo, update_id=4, callback_data=confirm)
    await handlers.on_delete_callback(upd, ctx)
    assert repo.records == []


async def test_delete_unknown_id_message():
    repo, upd, ctx = make(args=["99"])
    await handlers.on_borrar(upd, ctx)
    assert "No existe" in upd.effective_message.reply_text.call_args[0][0]


async def test_summary_and_last():
    repo, update, ctx = make("Nómina 1500")
    await handlers.on_text(update, ctx)
    upd, ctx = build(repo, "Cena -50", update_id=2)
    await handlers.on_text(upd, ctx)
    upd, ctx = build(repo, update_id=3)
    await handlers.on_resumen(upd, ctx)
    text = upd.effective_message.reply_text.call_args[0][0]
    assert "1.500,00 €" in text and "-50,00 €" in text and "1.450,00 €" in text
    upd, ctx = build(repo, update_id=4, args=["2"])
    await handlers.on_ultimos(upd, ctx)
    assert upd.effective_message.reply_text.call_args[0][0].count("#") == 2


async def test_chart_sends_photo_or_notice():
    repo, upd, ctx = make()
    await handlers.on_grafico(upd, ctx)
    assert "No hay movimientos" in upd.effective_message.reply_text.call_args[0][0]
    pytest.importorskip("matplotlib")
    upd, ctx = build(repo, "Cena -5")
    await handlers.on_text(upd, ctx)
    upd, ctx = build(repo, update_id=5)
    await handlers.on_grafico(upd, ctx)
    upd.effective_message.reply_photo.assert_called_once()
