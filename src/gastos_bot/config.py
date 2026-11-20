"""Configuración leída exclusivamente de variables de entorno."""
from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigError(RuntimeError):
    pass


def _required(env: dict, name: str) -> str:
    value = (env.get(name) or "").strip()
    if not value:
        raise ConfigError(f"Falta la variable de entorno obligatoria: {name}")
    return value


@dataclass(frozen=True)
class Settings:
    telegram_token: str
    allowed_user_id: int
    spreadsheet_id: str
    service_account_json: str
    webhook_secret: str
    mode: str = "polling"
    webhook_url: str = ""
    port: int = 8080
    timezone: str = "Europe/Madrid"

    @classmethod
    def from_env(cls, env: dict | None = None) -> "Settings":
        env = os.environ if env is None else env
        try:
            user_id = int(_required(env, "ALLOWED_USER_ID"))
        except ValueError as exc:
            raise ConfigError("ALLOWED_USER_ID debe ser un entero") from exc
        mode = (env.get("MODE") or "polling").strip().lower()
        if mode not in ("polling", "webhook"):
            raise ConfigError("MODE debe ser 'polling' o 'webhook'")
        settings = cls(
            telegram_token=_required(env, "TELEGRAM_TOKEN"),
            allowed_user_id=user_id,
            spreadsheet_id=_required(env, "SPREADSHEET_ID"),
            service_account_json=_required(env, "GOOGLE_SERVICE_ACCOUNT_JSON"),
            webhook_secret=_required(env, "WEBHOOK_SECRET"),
            mode=mode,
            webhook_url=(env.get("WEBHOOK_URL") or "").strip(),
            port=int(env.get("PORT") or 8080),
            timezone=(env.get("TIMEZONE") or "Europe/Madrid").strip(),
        )
        return settings
