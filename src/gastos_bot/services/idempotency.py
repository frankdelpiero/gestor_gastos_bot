"""Idempotencia por update_id (estado guardado en la hoja _Meta, no en memoria)."""
from __future__ import annotations

from ..sheets.repository import Repository


def already_processed(repo: Repository, update_id: int) -> bool:
    return repo.update_seen(update_id)


def mark_processed(repo: Repository, update_id: int) -> None:
    repo.mark_update(update_id)
