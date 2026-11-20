from __future__ import annotations

import logging

from .application import build_application
from .bot.handlers import Deps
from .config import Settings
from .sheets.client import open_spreadsheet
from .sheets.repository import GoogleSheetsRepository


def make_deps(settings: Settings) -> Deps:
    ss = open_spreadsheet(settings.service_account_json, settings.spreadsheet_id)
    return Deps(settings=settings, repo=GoogleSheetsRepository(ss))


def create_asgi_app():
    """Para uvicorn: `uvicorn gastos_bot.main:create_asgi_app --factory`."""
    from .webhook import create_web_app

    settings = Settings.from_env()
    app = build_application(make_deps(settings), updater=False)
    return create_web_app(app, settings.webhook_secret)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = Settings.from_env()
    if settings.mode == "webhook":
        import uvicorn

        uvicorn.run("gastos_bot.main:create_asgi_app", factory=True, host="0.0.0.0", port=settings.port)
    else:
        build_application(make_deps(settings), updater=True).run_polling(
            allowed_updates=["message", "callback_query"]
        )


if __name__ == "__main__":
    main()
