from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from ..services.deletion import make_token


def confirm_keyboard(secret: str, record_id: int, ts: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Confirmar", callback_data=make_token(secret, "ok", record_id, ts)),
        InlineKeyboardButton("✖ Cancelar", callback_data=make_token(secret, "no", record_id, ts)),
    ]])
