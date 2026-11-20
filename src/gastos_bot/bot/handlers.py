from __future__ import annotations

import asyncio
import io
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from telegram import Update
from telegram.ext import ContextTypes

from ..charts import render_month_chart
from ..config import Settings
from ..formatting import fmt_echo, fmt_money, fmt_record_line, fmt_date, fmt_summary
from ..parser import FORMAT_HELP, ParseError, parse_message, parse_month_year, to_local
from ..services import deletion, idempotency, records
from ..sheets.client import SheetsUnavailable
from ..sheets.repository import Repository
from .auth import authorized
from .keyboards import confirm_keyboard

log = logging.getLogger(__name__)

SHEETS_DOWN = "⚠️ No he podido conectar con Google Sheets. No se ha hecho ningún cambio; inténtalo de nuevo en un rato."


@dataclass
class Deps:
    settings: Settings
    repo: Repository
    now: Callable[[], datetime] = field(default=lambda: datetime.now(timezone.utc))


def _deps(context: ContextTypes.DEFAULT_TYPE) -> Deps:
    return context.application.bot_data["deps"]


async def _run(fn, *args):
    return await asyncio.to_thread(fn, *args)


def _user_label(update: Update) -> str:
    u = update.effective_user
    return u.full_name if u and u.full_name else str(u.id)


def guarded(handler):
    """Captura fallos de Sheets y avisa al usuario con un mensaje claro."""

    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            return await handler(update, context)
        except SheetsUnavailable:
            target = update.effective_message
            if update.callback_query:
                await update.callback_query.answer("Error con Google Sheets", show_alert=True)
            if target:
                await target.reply_text(SHEETS_DOWN)

    wrapper.__name__ = handler.__name__
    return wrapper


@authorized
@guarded
async def on_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        FORMAT_HELP + "\n\nComandos: /resumen [mes] [año] · /grafico [mes] [año] · "
        "/ultimos [n] · /borrar <ID> · /borrar ultimo"
    )


@authorized
@guarded
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    deps = _deps(context)
    msg = update.effective_message
    if await _run(idempotency.already_processed, deps.repo, update.update_id):
        return
    try:
        movement = parse_message(msg.text or "", msg.date, deps.settings.timezone)
    except ParseError as exc:
        await msg.reply_text(f"❌ {exc}\n\n{FORMAT_HELP}")
        await _run(idempotency.mark_processed, deps.repo, update.update_id)
        return
    record = await _run(records.register, deps.repo, movement, _user_label(update),
                        to_local(msg.date, deps.settings.timezone).replace(tzinfo=None))
    await msg.reply_text(fmt_echo(record))
    await _run(idempotency.mark_processed, deps.repo, update.update_id)


def _month_args(update, context, deps):
    today = to_local(update.effective_message.date, deps.settings.timezone).date()
    return parse_month_year(list(context.args or []), today)


@authorized
@guarded
async def on_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    deps = _deps(context)
    try:
        year, month = _month_args(update, context, deps)
    except ParseError as exc:
        await update.effective_message.reply_text(f"❌ {exc}")
        return
    income, expenses = await _run(records.monthly_summary, deps.repo, year, month)
    await update.effective_message.reply_text(fmt_summary(year, month, income, expenses))


@authorized
@guarded
async def on_grafico(update: Update, context: ContextTypes.DEFAULT_TYPE):
    deps = _deps(context)
    try:
        year, month = _month_args(update, context, deps)
    except ParseError as exc:
        await update.effective_message.reply_text(f"❌ {exc}")
        return
    month_records = await _run(deps.repo.month_records, year, month)
    png = await _run(render_month_chart, month_records, year, month)
    if png is None:
        await update.effective_message.reply_text("No hay movimientos en ese mes.")
        return
    await update.effective_message.reply_photo(io.BytesIO(png))


@authorized
@guarded
async def on_ultimos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    deps = _deps(context)
    arg = (context.args or ["10"])[0]
    if not arg.isdigit() or int(arg) < 1:
        await update.effective_message.reply_text("Uso: /ultimos [n]")
        return
    items = await _run(records.last_records, deps.repo, int(arg))
    text = "\n".join(fmt_record_line(r) for r in items) or "Aún no hay registros."
    await update.effective_message.reply_text(text)


@authorized
@guarded
async def on_borrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    deps = _deps(context)
    arg = (context.args or [None])[0]
    prepared = await _run(deletion.prepare, deps.repo, arg)
    if prepared.record is None:
        await update.effective_message.reply_text(prepared.error)
        return
    r = prepared.record
    ts = int(deps.now().timestamp())
    await update.effective_message.reply_text(
        f"¿Borrar este registro?\n\nID: #{r.id}\nConcepto: {r.concept}\n"
        f"Importe: {fmt_money(r.amount)}\nFecha: {fmt_date(r.date)}\n\n(Caduca en 2 minutos)",
        reply_markup=confirm_keyboard(deps.settings.webhook_secret, r.id, ts),
    )


@authorized
@guarded
async def on_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    deps = _deps(context)
    query = update.callback_query
    if await _run(idempotency.already_processed, deps.repo, update.update_id):
        await query.answer()
        return
    outcome = await _run(deletion.resolve, deps.repo, deps.settings.webhook_secret,
                         query.data or "", int(deps.now().timestamp()))
    texts = {
        "deleted": f"🗑️ Registro #{outcome.record_id} borrado.",
        "cancelled": "Cancelado. No se ha borrado nada.",
        "expired": "⌛ La confirmación ha caducado. Vuelve a usar /borrar.",
        "not_found": f"Ya no existe el registro #{outcome.record_id}.",
        "invalid": "Botón no válido.",
    }
    await query.answer()
    # editar el mensaje quita los botones: un segundo clic ya no tiene efecto
    await query.edit_message_text(texts[outcome.status], reply_markup=None)
    await _run(idempotency.mark_processed, deps.repo, update.update_id)
