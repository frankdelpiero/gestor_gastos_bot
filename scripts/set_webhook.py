"""Registra / consulta / elimina el webhook de Telegram.

Uso:
  python scripts/set_webhook.py set     # usa WEBHOOK_URL (https://xxx.run.app) + /telegram
  python scripts/set_webhook.py info
  python scripts/set_webhook.py delete
Lee TELEGRAM_TOKEN, WEBHOOK_URL y WEBHOOK_SECRET del entorno.
"""
import asyncio
import os
import sys

from telegram import Bot


async def main(action: str) -> None:
    bot = Bot(os.environ["TELEGRAM_TOKEN"])
    async with bot:
        if action == "set":
            url = os.environ["WEBHOOK_URL"].rstrip("/") + "/telegram"
            await bot.set_webhook(
                url, secret_token=os.environ["WEBHOOK_SECRET"], max_connections=1,
                allowed_updates=["message", "callback_query"], drop_pending_updates=True,
            )
            print("Webhook registrado en", url)
        elif action == "delete":
            await bot.delete_webhook(drop_pending_updates=True)
            print("Webhook eliminado")
        info = await bot.get_webhook_info()
        print(f"url={info.url!r} pendientes={info.pending_update_count} último_error={info.last_error_message!r}")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("set", "info", "delete"):
        sys.exit(__doc__)
    asyncio.run(main(sys.argv[1]))
