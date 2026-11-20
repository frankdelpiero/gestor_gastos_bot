"""Borrado con confirmación. Sin estado en servidor: el token va firmado en el botón."""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

from ..models import Record
from ..sheets.repository import Repository

TTL_SECONDS = 120


@dataclass(frozen=True)
class Prepared:
    record: Record | None
    error: str | None = None


@dataclass(frozen=True)
class Outcome:
    status: str  # deleted | not_found | expired | invalid | cancelled
    record_id: int | None = None


def _sig(secret: str, action: str, record_id: int, ts: int) -> str:
    msg = f"{action}:{record_id}:{ts}".encode()
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()[:10]


def make_token(secret: str, action: str, record_id: int, ts: int) -> str:
    """callback_data: del:<ok|no>:<id>:<ts>:<firma> (≤ 64 bytes)."""
    return f"del:{action}:{record_id}:{ts}:{_sig(secret, action, record_id, ts)}"


def parse_token(secret: str, token: str) -> tuple[str, int, int] | None:
    """Devuelve (acción, id, ts) si la firma es válida; None si no."""
    parts = token.split(":")
    if len(parts) != 5 or parts[0] != "del" or parts[1] not in ("ok", "no"):
        return None
    try:
        record_id, ts = int(parts[2]), int(parts[3])
    except ValueError:
        return None
    if not hmac.compare_digest(parts[4], _sig(secret, parts[1], record_id, ts)):
        return None
    return parts[1], record_id, ts


def prepare(repo: Repository, arg: str | None) -> Prepared:
    """Resuelve `/borrar <ID>` o `/borrar ultimo` sin tocar la hoja."""
    arg = (arg or "").strip().lower()
    if not arg:
        return Prepared(None, "Uso: /borrar <ID> o /borrar ultimo")
    if arg in ("ultimo", "último"):
        record = repo.last_record()
        if record is None:
            return Prepared(None, "❌ No hay registros que borrar.")
        return Prepared(record)
    arg = arg.lstrip("#")
    if not arg.isdigit():
        return Prepared(None, "Uso: /borrar <ID> o /borrar ultimo")
    record = repo.find_by_id(int(arg))
    if record is None:
        return Prepared(None, f"❌ No existe el registro #{int(arg)}.")
    return Prepared(record)


def resolve(repo: Repository, secret: str, token: str, now_ts: int) -> Outcome:
    """Procesa la pulsación de un botón (Confirmar/Cancelar)."""
    parsed = parse_token(secret, token)
    if parsed is None:
        return Outcome("invalid")
    action, record_id, ts = parsed
    if now_ts - ts > TTL_SECONDS or now_ts < ts - 5:
        return Outcome("expired", record_id)
    if action == "no":
        return Outcome("cancelled", record_id)
    # Se vuelve a buscar por ID en el momento de borrar (las filas cambian).
    if repo.delete_by_id(record_id):
        return Outcome("deleted", record_id)
    return Outcome("not_found", record_id)
