"""Servidor Starlette: procesa el update DENTRO de la petición (CPU solo durante la petición en Cloud Run)."""
from __future__ import annotations

import hmac
import logging
from contextlib import asynccontextmanager

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route
from telegram import Update

log = logging.getLogger(__name__)


def create_web_app(application, secret: str) -> Starlette:
    async def telegram(request: Request):
        header = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not hmac.compare_digest(header, secret):
            return PlainTextResponse("forbidden", status_code=403)
        data = await request.json()
        update = Update.de_json(data, application.bot)
        try:
            await application.process_update(update)
        except Exception:  # noqa: BLE001
            log.exception("Error procesando update %s", data.get("update_id"))
            return JSONResponse({"ok": False}, status_code=500)  # Telegram reintentará; la idempotencia protege
        return JSONResponse({"ok": True})

    async def health(_: Request):
        return PlainTextResponse("ok")

    @asynccontextmanager
    async def lifespan(_: Starlette):
        await application.initialize()
        try:
            yield
        finally:
            await application.shutdown()

    return Starlette(
        routes=[Route("/telegram", telegram, methods=["POST"]), Route("/healthz", health)],
        lifespan=lifespan,
    )
