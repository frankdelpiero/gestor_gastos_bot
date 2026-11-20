from __future__ import annotations

from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from .bot import handlers
from .bot.handlers import Deps


def build_application(deps: Deps, *, updater: bool = False) -> Application:
    builder = Application.builder().token(deps.settings.telegram_token)
    if not updater:
        builder = builder.updater(None)  # webhook propio: sin Updater
    app = builder.build()
    app.bot_data["deps"] = deps
    app.add_handler(CommandHandler(["start", "ayuda"], handlers.on_start))
    app.add_handler(CommandHandler("resumen", handlers.on_resumen))
    app.add_handler(CommandHandler("grafico", handlers.on_grafico))
    app.add_handler(CommandHandler("ultimos", handlers.on_ultimos))
    app.add_handler(CommandHandler("borrar", handlers.on_borrar))
    app.add_handler(CallbackQueryHandler(handlers.on_delete_callback, pattern=r"^del:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.on_text))
    return app
