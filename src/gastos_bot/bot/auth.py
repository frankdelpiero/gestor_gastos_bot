"""Solo responde al user_id configurado; el resto se ignora en silencio."""
from __future__ import annotations

from functools import wraps


def authorized(handler):
    @wraps(handler)
    async def wrapper(update, context):
        user = update.effective_user
        deps = context.application.bot_data["deps"]
        if user is None or user.id != deps.settings.allowed_user_id:
            return None
        return await handler(update, context)

    return wrapper
