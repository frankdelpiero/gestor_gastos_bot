from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from ..categories import Categorizer
from ..models import Movement, Record
from ..sheets.repository import Repository, month_totals


def register(repo: Repository, movement: Movement, user: str, now: datetime) -> Record:
    """Asigna ID, categoriza y guarda el movimiento."""
    category = Categorizer(repo.category_rules() or None).categorize(movement.concept, movement.amount)
    record = Record(
        id=repo.reserve_id(), date=movement.date, concept=movement.concept,
        amount=movement.amount, category=category, user=user, created=now,
    )
    repo.add_record(record)
    return record


def last_records(repo: Repository, n: int = 10) -> list[Record]:
    return repo.list_last(max(1, min(n, 50)))


def monthly_summary(repo: Repository, year: int, month: int) -> tuple[Decimal, Decimal]:
    return month_totals(repo.month_records(year, month))
