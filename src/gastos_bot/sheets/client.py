"""Cliente gspread con cuenta de servicio y reintentos con backoff."""
from __future__ import annotations

import json
import logging
import os
from functools import wraps

import gspread
import requests
from google.oauth2.service_account import Credentials
from tenacity import (
    Retrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class SheetsUnavailable(RuntimeError):
    """La API de Sheets falló tras agotar los reintentos."""


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, gspread.exceptions.APIError):
        code = getattr(exc.response, "status_code", 0)
        return code == 429 or code >= 500
    return isinstance(exc, (requests.exceptions.ConnectionError, requests.exceptions.Timeout))


def with_retries(attempts: int = 4, max_wait: float = 8.0):
    """Reintenta errores transitorios (429/5xx/red) con backoff exponencial y jitter."""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            retrying = Retrying(
                retry=retry_if_exception(_is_transient),
                stop=stop_after_attempt(attempts),
                wait=wait_exponential_jitter(initial=1, max=max_wait),
                reraise=True,
            )
            try:
                return retrying(fn, *args, **kwargs)
            except Exception as exc:  # noqa: BLE001
                if _is_transient(exc):
                    log.error("Sheets no disponible tras %s intentos: %s", attempts, exc)
                    raise SheetsUnavailable(str(exc)) from exc
                raise

        return wrapper

    return decorator


def _load_credentials(value: str) -> Credentials:
    value = value.strip()
    info = json.loads(value) if value.startswith("{") else json.load(open(os.path.expanduser(value), encoding="utf-8"))
    return Credentials.from_service_account_info(info, scopes=SCOPES)


def open_spreadsheet(service_account_json: str, spreadsheet_id: str) -> gspread.Spreadsheet:
    client = gspread.authorize(_load_credentials(service_account_json))
    return client.open_by_key(spreadsheet_id)
