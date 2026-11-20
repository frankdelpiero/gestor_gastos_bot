from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


@dataclass(frozen=True)
class Movement:
    """Resultado de parsear un mensaje (aún sin ID)."""

    concept: str
    amount: Decimal
    date: date


@dataclass(frozen=True)
class Record:
    """Fila del Registro."""

    id: int
    date: date
    concept: str
    amount: Decimal
    category: str
    user: str
    created: datetime | None = None
